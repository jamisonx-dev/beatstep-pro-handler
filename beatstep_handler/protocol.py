"""
beatstep_handler.protocol -- the Arturia BeatStep Pro configuration SysEx protocol.

Pure data + byte builders. No I/O, no third-party dependencies. This is the
correctness-critical core and is unit-tested off-hardware.

THE WHOLE PROTOCOL
==================
One uniform SysEx frame reads or writes every configurable parameter:

    WRITE:  F0 00 20 6B 7F 42 02 00 <paramId> <itemId> <value> F7
    READ:   F0 00 20 6B 7F 42 01 00 <paramId> <itemId>         F7
      reply:F0 00 20 6B 7F 42 02 00 <paramId> <itemId> <value> F7
      (+ an ack: F0 00 20 6B 7F 42 1C 00 F7)

  * 00 20 6B  = Arturia manufacturer id
  * 7F 42     = BeatStep Pro
  * 02 / 01   = write / read command; 1C = ack
  * paramId 0x41 (65)   -> the GLOBAL parameter bank; itemId = the global's id
  * paramId 0x01..0x08  -> per-control ControllerMap fields (meaning below)
  * paramId 0x50..0x6F  -> sequencer/pattern/project data (only PROJECT-scope
                           scalars are reachable by this frame; see notes)

IMPORTANT (verified on hardware):
  * Configuration SysEx is USB-ONLY. The BSP IGNORES these frames over DIN
    (real-time MIDI -- clock/transport/notes -- over DIN works fine).
  * LIST parameter values are NON-CONTIGUOUS (e.g. a knob's Mode uses the
    values 0,1,4,12,13,14,15). Send the value the device expects, not an index.

These are interoperability facts about the hardware's wire behavior. The
human-readable NAMES of Arturia's parameters are NOT here -- build a named layer
from your own Arturia MIDI Control Center install with tools/gen_tables.py.
"""

# --------------------------------------------------------------------------- #
# Frame constants                                                             #
# --------------------------------------------------------------------------- #
MANUFACTURER = (0x00, 0x20, 0x6B)   # Arturia
DEVICE = (0x7F, 0x42)               # BeatStep Pro
HEADER = MANUFACTURER + DEVICE      # what follows F0

CMD_READ = 0x01
CMD_WRITE = 0x02
CMD_ACK = 0x1C

SYSEX_START = 0xF0
SYSEX_END = 0xF7

# --------------------------------------------------------------------------- #
# Parameter banks (paramId)                                                    #
# --------------------------------------------------------------------------- #
PARAM_GLOBAL = 0x41   # global settings bank; itemId = the global's globalParamId

# Per-control ControllerMap field ids. Which physical field a shared paramId
# addresses depends on the control's Mode (paramId 1), per Arturia's dictionary.
PARAM_CTRL_MODE = 0x01        # Off / CC / Note / Program Change / ...
PARAM_CTRL_CHANNEL = 0x02     # MIDI channel
PARAM_CTRL_DATA = 0x03        # CC# / Note# / Program# / MMC / Data
PARAM_CTRL_MIN = 0x04         # Min / Off value / Bank LSB / Min velocity
PARAM_CTRL_MAX = 0x05         # Max / On value / Bank MSB / Max velocity
PARAM_CTRL_OPTION = 0x06      # Option / Play mode / Loop
PARAM_CTRL_ACCEL = 0x07       # Acceleration
PARAM_CTRL_PORTS = 0x08       # MIDI ports

# --------------------------------------------------------------------------- #
# Physical control itemId ranges (verified on hardware)                        #
# --------------------------------------------------------------------------- #
KNOB_ITEMS = tuple(range(32, 48))     # the 16 user knobs
PAD_ITEMS = tuple(range(112, 128))    # the 16 pads
STEP_ITEMS = tuple(range(48, 64))     # the 16 step buttons

# --------------------------------------------------------------------------- #
# MIDI channel special values                                                  #
# --------------------------------------------------------------------------- #
# A channel field is 0..15 for channels 1..16, plus these specials:
CHANNEL_USER = 0x41    # follow the global User Channel
CHANNEL_ALL = 0x7E     # send on all channels
CHANNEL_DRUM = 0x42    # the drum channel


# --------------------------------------------------------------------------- #
# Frame builders                                                               #
# --------------------------------------------------------------------------- #

def _check7(name, v):
    if not (0 <= v <= 127):
        raise ValueError(f"{name} must be 0..127, got {v}")


def write_frame(param_id, item_id, value):
    """Full SysEx bytes (incl. F0/F7) to WRITE a value to (param_id, item_id)."""
    _check7("param_id", param_id)
    _check7("item_id", item_id)
    _check7("value", value)
    return bytes([SYSEX_START, *HEADER, CMD_WRITE, 0x00,
                  param_id, item_id, value, SYSEX_END])


def read_frame(param_id, item_id):
    """Full SysEx bytes (incl. F0/F7) to REQUEST the value of (param_id, item_id)."""
    _check7("param_id", param_id)
    _check7("item_id", item_id)
    return bytes([SYSEX_START, *HEADER, CMD_READ, 0x00,
                  param_id, item_id, SYSEX_END])


def read_frames(pairs):
    """One bytes buffer of concatenated read requests for a list of
    (param_id, item_id) pairs -- how the device is polled in a paced burst."""
    buf = bytearray()
    for pid, item in pairs:
        buf += read_frame(pid, item)
    return bytes(buf)


def parse_message(data):
    """Interpret one SysEx message (with or without the F0/F7 wrappers).

    Returns:
        ("value", param_id, item_id, value)   -- a read reply / value frame
        ("ack",)                               -- the device's ack
        None                                   -- not a BSP config message
    """
    d = list(data)
    if d and d[0] == SYSEX_START:
        d = d[1:]
    if d and d[-1] == SYSEX_END:
        d = d[:-1]
    # d now: HEADER(5) + cmd + 00 + ...
    if len(d) < 7 or tuple(d[:5]) != HEADER:
        return None
    cmd, sub = d[5], d[6]
    if cmd == CMD_WRITE and sub == 0x00 and len(d) >= 10:
        return ("value", d[7], d[8], d[9])
    if cmd == CMD_ACK and sub == 0x00:
        return ("ack",)
    return None


def all_control_items():
    """Every physical control's itemId, as (kind, item_id) pairs."""
    out = []
    for i in KNOB_ITEMS:
        out.append(("knob", i))
    for i in PAD_ITEMS:
        out.append(("pad", i))
    for i in STEP_ITEMS:
        out.append(("step", i))
    return out
