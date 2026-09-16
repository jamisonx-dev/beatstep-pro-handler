"""Correctness tests for beatstep_handler.protocol -- the SysEx wire format, proven
byte for byte with no hardware and no dependencies.

Run: python -m pytest   (or: python tests/test_protocol.py)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from beatstep_handler import protocol as P  # noqa: E402


def test_write_frame_exact():
    # global User Channel (paramId 0x41, item 0x06) := 9
    assert P.write_frame(0x41, 0x06, 9) == bytes(
        [0xF0, 0x00, 0x20, 0x6B, 0x7F, 0x42, 0x02, 0x00, 0x41, 0x06, 0x09, 0xF7])


def test_read_frame_exact():
    assert P.read_frame(0x41, 0x06) == bytes(
        [0xF0, 0x00, 0x20, 0x6B, 0x7F, 0x42, 0x01, 0x00, 0x41, 0x06, 0xF7])


def test_read_frames_concat():
    a = P.read_frame(0x41, 0x06)
    b = P.read_frame(0x03, 0x20)
    assert P.read_frames([(0x41, 0x06), (0x03, 0x20)]) == a + b


def test_parse_value_reply_with_wrapper():
    reply = bytes([0xF0, 0x00, 0x20, 0x6B, 0x7F, 0x42, 0x02, 0x00,
                   0x41, 0x06, 13, 0xF7])
    assert P.parse_message(reply) == ("value", 0x41, 0x06, 13)


def test_parse_value_reply_without_wrapper():
    # python-rtmidi often hands you the data already unwrapped
    reply = [0x00, 0x20, 0x6B, 0x7F, 0x42, 0x02, 0x00, 0x03, 0x20, 74]
    assert P.parse_message(reply) == ("value", 0x03, 0x20, 74)


def test_parse_ack():
    ack = bytes([0xF0, 0x00, 0x20, 0x6B, 0x7F, 0x42, 0x1C, 0x00, 0xF7])
    assert P.parse_message(ack) == ("ack",)


def test_parse_rejects_foreign():
    # a non-Arturia sysex
    assert P.parse_message([0xF0, 0x7D, 0x01, 0x02, 0xF7]) is None
    assert P.parse_message([]) is None


def test_write_frame_is_shaped_like_a_value_reply():
    # a write frame and a value reply share the same body, so parse round-trips
    assert P.parse_message(P.write_frame(0x41, 0x06, 5)) == ("value", 0x41, 0x06, 5)


def test_range_validation():
    for bad in (-1, 128, 200):
        try:
            P.write_frame(0x41, 0x06, bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"value {bad} should have raised")


def test_control_item_ranges():
    assert P.KNOB_ITEMS == tuple(range(32, 48))
    assert P.PAD_ITEMS == tuple(range(112, 128))
    assert P.STEP_ITEMS == tuple(range(48, 64))
    assert len(P.all_control_items()) == 48


def test_channel_specials():
    assert P.CHANNEL_USER == 0x41
    assert P.CHANNEL_ALL == 0x7E
    assert P.CHANNEL_DRUM == 0x42


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} passed")
