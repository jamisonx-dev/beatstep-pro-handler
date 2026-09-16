"""
beatstep_handler.cli -- a command-line tool for the BeatStep Pro.

    bsp read 41 06                 # read global param 0x41/0x06 (User Channel)
    bsp write 41 06 9              # set it to 9 (channel 10, 0-based)
    bsp write 41 06 9 --verify     # ...and read it back to confirm
    bsp globals                    # dump every global setting
    bsp globals --tables t.json    # ...with friendly names from your MCC table

Parameters are addressed by their hex ids (see the README / beatstep_handler.protocol).
A name table built by tools/gen_tables.py from your own MCC install is optional
and only adds human-readable names to `globals`.
"""
import argparse
import json
import os

from . import protocol
from .device import BeatStepPro, BeatStepNotFound


def _hex(s):
    return int(s, 16)


def _load_tables(path):
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def cmd_read(bsp, args):
    v = bsp.read(_hex(args.param), _hex(args.item))
    if v is None:
        print("no reply (parameter not readable, or device dropped it)")
        return 1
    print(v)
    return 0


def cmd_write(bsp, args):
    ok = bsp.write(_hex(args.param), _hex(args.item), int(args.value),
                   verify=args.verify)
    if args.verify:
        print("ok" if ok else "MISMATCH (device did not take the value)")
        return 0 if ok else 1
    print("sent")
    return 0


def cmd_globals(bsp, args):
    # Default to the bundled name table; --tables overrides with your own.
    from . import tables as _tables
    try:
        meta = _tables.global_params(_load_tables(args.tables))
    except Exception:
        meta = {}
    if meta:
        gps = list(meta.keys())
    else:
        gps = list(range(2, 125))   # a broad sweep when we have no table
    pairs = [(protocol.PARAM_GLOBAL, gp) for gp in gps]
    found = bsp.read_many(pairs)
    for gp in gps:
        v = found.get((protocol.PARAM_GLOBAL, gp))
        if v is None:
            continue
        m = meta.get(gp)
        if m:
            label = ""
            for o in m.get("options", []):
                if o["v"] == v:
                    label = f"  ({o['label']})"
                    break
            print(f"  {gp:>3} 0x{gp:02X}  {m['name']:<28} = {v}{label}")
        else:
            print(f"  {gp:>3} 0x{gp:02X}  = {v}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="bsp", description="Control an Arturia BeatStep Pro over USB SysEx.")
    ap.add_argument("--amidi-port", help="override the amidi rawmidi port (hw:X,0,0)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("read", help="read a parameter (hex param + item)")
    r.add_argument("param"); r.add_argument("item")

    w = sub.add_parser("write", help="write a parameter (hex param + item, decimal value)")
    w.add_argument("param"); w.add_argument("item"); w.add_argument("value")
    w.add_argument("--verify", action="store_true", help="read back and confirm")

    g = sub.add_parser("globals", help="dump global settings")
    g.add_argument("--tables", help="beatstep_tables.json from tools/gen_tables.py")

    args = ap.parse_args(argv)
    try:
        bsp = BeatStepPro(amidi_port=args.amidi_port)
    except BeatStepNotFound as e:
        print(f"error: {e}")
        return 2
    try:
        return {"read": cmd_read, "write": cmd_write, "globals": cmd_globals}[args.cmd](bsp, args)
    finally:
        bsp.close()


if __name__ == "__main__":
    raise SystemExit(main())
