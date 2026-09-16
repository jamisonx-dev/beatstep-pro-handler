"""
beatstep.device -- read and write BeatStep Pro parameters over USB SysEx.

    from beatstep import BeatStepPro, PARAM_GLOBAL
    bsp = BeatStepPro()
    print(bsp.read(PARAM_GLOBAL, 0x06))     # global User Channel
    bsp.write(PARAM_GLOBAL, 0x06, 9)        # set User Channel to 10 (0-based)

CROSS-PLATFORM. The default backend uses python-rtmidi for both sending and
capturing, so this runs on Windows, macOS, and Linux -- connect the BSP by USB
and go. (Configuration SysEx is USB-only; the BSP ignores it over DIN.)

HOW IT TALKS TO THE DEVICE
==========================
The BSP answers a read with the parameter's current LIVE value. This class
sends a read/write frame and captures the reply on the same port. The device
DROPS large request bursts, so reads are paced in small chunks with a bounded
retry (reproducing the approach proven on real hardware).

Backends:
  * "rtmidi" (default) -- python-rtmidi for send AND capture. Cross-platform.
    Use this for normal standalone control.
  * "amidi" (Linux only, opt-in) -- send via ALSA `amidi -S`, capture via
    python-rtmidi. Only needed when ANOTHER program already holds the device's
    sequencer port (e.g. running alongside a host app that owns the BSP); in
    that contended case a second rtmidi output may not reach the device, but a
    co-subscribed rtmidi *input* still sees the replies. Requires alsa-utils.
"""
import os
import re
import subprocess
import tempfile
import time

from . import protocol

_PORT_HINTS = ("arturia be", "beatstep")   # config endpoint, most specific first
_AMIDI_NAME = "BeatStep Pro Arturia Be"


class BeatStepNotFound(RuntimeError):
    pass


class BeatStepPro:
    def __init__(self, port_name=None, backend="rtmidi", amidi_port=None,
                 verbose=False):
        import rtmidi
        self.backend = backend
        self.verbose = verbose

        # Capture (input) is always python-rtmidi -- it co-subscribes cleanly.
        self._mi = rtmidi.MidiIn()
        ii = self._pick(self._mi.get_ports(), port_name)
        if ii is None:
            raise BeatStepNotFound(
                "BeatStep Pro input port not found "
                f"(ports={self._mi.get_ports()!r}; is it connected by USB?)")
        if self.verbose:
            print(f"[beatstep] capture port: {self._mi.get_ports()[ii]}")
        self._mi.open_port(ii)
        self._mi.ignore_types(sysex=False, timing=True, active_sense=True)

        self._mo = None
        self._amidi_port = None
        if backend == "rtmidi":
            self._mo = rtmidi.MidiOut()
            oi = self._pick(self._mo.get_ports(), port_name)
            if oi is None:
                raise BeatStepNotFound("BeatStep Pro output port not found")
            if self.verbose:
                print(f"[beatstep] send port: {self._mo.get_ports()[oi]}")
            self._mo.open_port(oi)
        elif backend == "amidi":
            self._amidi_port = amidi_port or self._find_amidi_port()
            if not self._amidi_port:
                raise BeatStepNotFound("BeatStep Pro not found via `amidi -l`")
        else:
            raise ValueError(f"unknown backend {backend!r} (use 'rtmidi' or 'amidi')")

    # -- discovery ---------------------------------------------------------- #

    @staticmethod
    def _pick(ports, port_name):
        hints = ((port_name.lower(),) if port_name else ()) + _PORT_HINTS
        for hint in hints:
            for i, name in enumerate(ports):
                if hint in name.lower():
                    return i
        return None

    @staticmethod
    def _find_amidi_port():
        try:
            out = subprocess.run(["amidi", "-l"], capture_output=True,
                                 text=True, timeout=4).stdout
        except Exception:
            return None
        for line in out.splitlines():
            if _AMIDI_NAME in line:
                m = re.search(r'(hw:\d+,\d+,\d+)', line)
                if m:
                    return m.group(1)
        return None

    # -- low-level send / collect ------------------------------------------ #

    def _send(self, data):
        if self.backend == "rtmidi":
            self._mo.send_message(list(data))
            return
        # amidi backend: write a .syx and shoot it via ALSA rawmidi
        with tempfile.NamedTemporaryFile(suffix=".syx", delete=False) as f:
            f.write(bytes(data))
            path = f.name
        try:
            subprocess.run(["amidi", "-p", self._amidi_port, "-s", path],
                           capture_output=True, text=True, timeout=6)
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    def _drain(self):
        while self._mi.get_message():
            pass

    def _collect(self, wanted, window):
        found = {}
        t0 = time.time()
        while time.time() - t0 < window:
            m = self._mi.get_message()
            if not m:
                time.sleep(0.002)
                continue
            parsed = protocol.parse_message(m[0])
            if parsed and parsed[0] == "value":
                key = (parsed[1], parsed[2])
                if key in wanted:
                    found[key] = parsed[3]
                    if len(found) >= len(wanted):
                        break
        return found

    # -- public API --------------------------------------------------------- #

    def read_many(self, pairs, chunk=6, retries=3, budget=6.0):
        """Read many (param_id, item_id) pairs. Returns {(pid,item): value};
        missing pairs are simply absent."""
        pairs = [(int(p), int(i)) for p, i in pairs]
        time.sleep(0.15)
        self._drain()
        found = {}
        for c in range(0, len(pairs), chunk):
            grp = pairs[c:c + chunk]
            self._send(protocol.read_frames(grp))
            found.update(self._collect(set(grp), window=0.13))
        deadline = time.time() + budget
        for _ in range(retries):
            missing = [pr for pr in pairs if pr not in found]
            if not missing or time.time() > deadline:
                break
            for c in range(0, len(missing), chunk):
                if time.time() > deadline:
                    break
                grp = missing[c:c + chunk]
                self._send(protocol.read_frames(grp))
                found.update(self._collect(set(grp), window=0.12))
        return found

    def read(self, param_id, item_id):
        """Read a single parameter's live value, or None if no reply."""
        return self.read_many([(param_id, item_id)]).get((int(param_id), int(item_id)))

    def write(self, param_id, item_id, value, verify=False):
        """Write a value. With verify=True, read it back and return whether the
        device now reports the written value."""
        self._send(protocol.write_frame(param_id, item_id, value))
        if not verify:
            return True
        time.sleep(0.05)
        return self.read(param_id, item_id) == value

    def close(self):
        for port in (self._mi, self._mo):
            try:
                if port is not None:
                    port.close_port()
            except Exception:
                pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
