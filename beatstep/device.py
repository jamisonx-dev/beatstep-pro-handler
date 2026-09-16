"""
beatstep.device -- read and write BeatStep Pro parameters over USB SysEx.

    from beatstep import BeatStepPro, PARAM_GLOBAL
    bsp = BeatStepPro()
    print(bsp.read(PARAM_GLOBAL, 0x06))     # global User Channel
    bsp.write(PARAM_GLOBAL, 0x06, 9)        # set User Channel to 10 (0-based)

HOW IT TALKS TO THE DEVICE (the hard-won part)
==============================================
The BSP answers a read with the parameter's current LIVE value. Two mechanics,
both learned on real hardware, matter:

  * SEND via ALSA rawmidi (`amidi -S`). A pure python-rtmidi *send* does NOT
    reliably reach the device's config endpoint; the rawmidi path does.
  * CAPTURE via python-rtmidi co-subscribed to the BSP's config output port.
    ALSA seq allows this even while another program also holds the device.

The device also DROPS large request bursts, so reads are paced in small chunks
with a bounded retry. This class reproduces the approach proven in the
reference instrument.

Config SysEx is USB-ONLY -- the BSP ignores it over DIN. Connect via USB.

Platform: the send path uses `amidi` (ALSA), so this is Linux-oriented (a
Raspberry Pi, a Linux laptop). Capture uses python-rtmidi (cross-platform).
"""
import os
import re
import subprocess
import tempfile
import time

from . import protocol

_AMIDI_NAME = "BeatStep Pro Arturia Be"   # the config (hw:X,0,0) endpoint
_RTMIDI_HINTS = ("arturia be", "beatstep")


class BeatStepNotFound(RuntimeError):
    pass


class BeatStepPro:
    def __init__(self, amidi_port=None, verbose=False):
        self.verbose = verbose
        self._amidi_port = amidi_port or self._find_amidi_port()
        if not self._amidi_port:
            raise BeatStepNotFound(
                "BeatStep Pro not found via `amidi -l` (is it connected by USB?)")
        self._mi = self._open_capture()
        if self._mi is None:
            raise BeatStepNotFound(
                "BeatStep Pro config input port not found via python-rtmidi")

    # -- discovery ---------------------------------------------------------- #

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

    def _open_capture(self):
        import rtmidi
        mi = rtmidi.MidiIn()
        ports = mi.get_ports()
        pick = None
        for hint in _RTMIDI_HINTS:
            for i, name in enumerate(ports):
                if hint in name.lower():
                    pick = i
                    break
            if pick is not None:
                break
        if pick is None:
            return None
        if self.verbose:
            print(f"[beatstep] capture port: {ports[pick]}")
        mi.open_port(pick)
        mi.ignore_types(sysex=False, timing=True, active_sense=True)
        return mi

    # -- low-level send/collect (mirrors the proven reference approach) ------ #

    def _send(self, data):
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
        """Read many (param_id, item_id) pairs. Returns {(pid,item): value}.
        Missing pairs are simply absent from the dict."""
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

    def read(self, param_id, item_id, timeout=1.0):
        """Read a single parameter's live value, or None if no reply."""
        return self.read_many([(param_id, item_id)]).get((int(param_id), int(item_id)))

    def write(self, param_id, item_id, value, verify=False):
        """Write a value. If verify=True, read it back and return whether the
        device now reports the written value."""
        self._send(protocol.write_frame(param_id, item_id, value))
        if not verify:
            return True
        time.sleep(0.05)
        return self.read(param_id, item_id) == value

    def close(self):
        try:
            self._mi.close_port()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
