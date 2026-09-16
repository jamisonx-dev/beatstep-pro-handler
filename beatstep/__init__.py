"""
beatstep -- read and write every Arturia BeatStep Pro configuration parameter
over USB SysEx: global settings and per-control (knob/pad/step) assignments.

    from beatstep import BeatStepPro, PARAM_GLOBAL
    bsp = BeatStepPro()
    print(bsp.read(PARAM_GLOBAL, 0x06))   # global User Channel

The `protocol` submodule is pure (no I/O, no deps) -- the SysEx frame builders
and the hardware's parameter/control semantics, usable with any MIDI stack.
"""
from . import protocol, tables
from .device import BeatStepPro, BeatStepNotFound
from .protocol import (
    write_frame, read_frame, read_frames, parse_message,
    PARAM_GLOBAL,
    PARAM_CTRL_MODE, PARAM_CTRL_CHANNEL, PARAM_CTRL_DATA, PARAM_CTRL_MIN,
    PARAM_CTRL_MAX, PARAM_CTRL_OPTION, PARAM_CTRL_ACCEL, PARAM_CTRL_PORTS,
    KNOB_ITEMS, PAD_ITEMS, STEP_ITEMS,
    CHANNEL_USER, CHANNEL_ALL, CHANNEL_DRUM,
)

__version__ = "0.1.0"

__all__ = [
    "BeatStepPro", "BeatStepNotFound", "protocol", "tables",
    "write_frame", "read_frame", "read_frames", "parse_message",
    "PARAM_GLOBAL",
    "PARAM_CTRL_MODE", "PARAM_CTRL_CHANNEL", "PARAM_CTRL_DATA", "PARAM_CTRL_MIN",
    "PARAM_CTRL_MAX", "PARAM_CTRL_OPTION", "PARAM_CTRL_ACCEL", "PARAM_CTRL_PORTS",
    "KNOB_ITEMS", "PAD_ITEMS", "STEP_ITEMS",
    "CHANNEL_USER", "CHANNEL_ALL", "CHANNEL_DRUM",
]
