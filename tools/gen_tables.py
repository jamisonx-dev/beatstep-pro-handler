#!/usr/bin/env python3
"""Generate a friendly BeatStep Pro parameter table from YOUR OWN copy of
Arturia's MIDI Control Center device dictionary.

    python tools/gen_tables.py "/path/to/BeatStepPro.json" -o beatstep_tables.json

WHY THIS IS A GENERATOR, NOT SHIPPED DATA
-----------------------------------------
The BeatStep Pro's parameter *numbers* and value *enums* are interoperability
facts (this library speaks them in beatstep/protocol.py). But the friendly
parameter NAMES ("Pad Poly Aftertouch", "User Knob Acceleration", ...) are
Arturia's, and live in their MIDI Control Center dictionary. Rather than
redistribute Arturia's data, this tool builds the named table from the copy you
already have if you've installed MCC. Find it at (typical locations):

    Windows: C:\\ProgramData\\Arturia\\... or the MCC "Resources" folder
    macOS:   /Applications/... MIDI Control Center .../Resources/BeatStepPro.json

The output `beatstep_tables.json` is for your own use. The library and CLI work
without it (you address parameters by number); the table just adds names.

The parsing + generation logic here is the reproducible source proven against
real hardware; only the input/output paths differ from the reference tool.
"""
import argparse
import json
import os
import re


def load_mcc(path):
    """Parse Arturia's lenient JSON: strip comments, trailing commas, leading
    zeros. (Do NOT strip `//` after a colon -- that could be inside a URL.)"""
    txt = open(path, encoding="utf-8").read()
    txt = re.sub(r'/\*.*?\*/', '', txt, flags=re.S)
    txt = re.sub(r'(?<!:)//[^\n]*', '', txt)
    txt = re.sub(r',(\s*[}\]])', r'\1', txt)
    txt = re.sub(r'(:\s*)0+(\d)', r'\1\2', txt)
    return json.loads(txt)


GLOBAL_GROUPS = [
    ("Behavior",                 [2, 4, 6, 7, 11, 12, 13, 23]),
    ("Clock & Sync",             [16, 17, 18, 20, 21, 22]),
    ("Touch Strip",              [41, 40]),
    ("Transposition",            [8, 9, 10]),
    ("Metronome",                [32, 33, 34, 35, 36, 37]),
    ("Sequencer MIDI Channels",  [64, 65, 66, 67, 68, 69]),
    ("CV / Gate Outputs",        [70, 71, 74, 76, 78, 92, 72, 73, 75, 77, 79, 93]),
    ("Transport Output",         [96, 97, 98, 99, 100, 101, 102]),
    ("Drums",                    [38, 39]),
    ("Drum Pad Notes",           list(range(48, 64))),
    ("Drum Pad Channels",        [117, 118, 119, 120, 121, 122, 123, 124,
                                  109, 110, 111, 112, 113, 114, 115, 116]),
    ("User Scale",               [81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91]),
]
CH_USER = {8, 35, 65, 67, 69, 97, 98, 99}
CH_ALL = {8, 65, 67, 69}
CH_DRUM = set(range(109, 125))


def kind_of(x):
    t = x["type"]
    if t == "CHANNEL":
        return "channel"
    if t == "NOTE":
        return "note"
    if t == "CC_NUM":
        return "range"
    if t in ("RANGE", "RANGE_HORIZONTAL"):
        return "range"
    if t == "LIST":
        return "toggle" if [o["val"] for o in x.get("list", [])] == [0, 127] else "list"
    if t == "MMC":
        return "mmc"
    return "other"


def gen_params(d):
    F = {x.get("globalParamId"): x for x in d["fields"] if x.get("paramId") == 65}
    out = []
    for title, gps in GLOBAL_GROUPS:
        sec = {"group": title, "params": []}
        for gp in gps:
            x = F[gp]
            name = f"Pad #{gp - 47} Note" if 48 <= gp <= 63 else x["name"]
            p = {"gp": gp, "hex": f"{gp:02X}", "name": name,
                 "kind": kind_of(x), "default": x.get("defaultValue", 0)}
            if x.get("conditions"):
                c = x["conditions"][0]
                p["cond"] = {"gp": c["paramId"], "vals": c["values"]}
            k = p["kind"]
            if k == "list":
                p["options"] = [{"v": o["val"], "label": o["str"]} for o in x["list"]]
            elif k == "range":
                p["min"] = x.get("minValue") or 0
                p["max"] = x.get("maxValue") or 127
            elif k == "channel":
                p["user"] = gp in CH_USER
                p["all"] = gp in CH_ALL
                p["drum"] = gp in CH_DRUM
            sec["params"].append(p)
        out.append(sec)
    return {"sysex_prefix": "F0 00 20 6B 7F 42 02 00 41",
            "note": "global params paramId 65; value follows globalParamId",
            "sections": out}


def gen_controls(d):
    fields = {x["id"]: x for x in d["fields"]}

    def field_entry(fid):
        x = fields[fid]
        p = {"paramId": x["paramId"], "phex": f"{x['paramId']:02X}",
             "name": x["name"], "kind": kind_of(x)}
        if x.get("conditions"):
            p["conds"] = [{"p": c["paramId"], "vals": c["values"]} for c in x["conditions"]]
        k = p["kind"]
        if k in ("list", "mmc"):
            p["options"] = [{"v": o["val"], "label": o["str"]} for o in x.get("list", [])]
        elif k == "range":
            p["min"] = x.get("minValue") or 0
            p["max"] = x.get("maxValue") or 127
            p["default"] = x.get("defaultValue") or 0
        elif k == "note":
            p["default"] = x.get("defaultValue") or 60
        elif k == "channel":
            p["user"] = True
        return p

    TYPES = {}
    default_mode = {"knob": 1, "pad": 9, "step": 9}
    for tid in ("knob", "pad", "step"):
        t = next(x for x in d["itemTypes"] if x["id"] == tid)
        flds = [field_entry(fid) for fid in t["fields"]]
        mode = next(f for f in flds if f["paramId"] == 1)
        TYPES[tid] = {"modeParam": 1, "modeParamHex": "01",
                      "modeOptions": mode["options"],
                      "defaultMode": default_mode[tid], "fields": flds}

    CONTROLS = {}
    for tid in ("knob", "pad", "step"):
        items = []
        for c in d["controls"]:
            it = c["items"][0]
            if it.get("type") == tid:
                items.append({"itemId": it["id"], "ihex": f"{it['id']:02X}", "name": it["name"]})
        CONTROLS[tid] = sorted(items, key=lambda z: z["itemId"])

    return {"note": "per-control ControllerMap. SysEx: F0 00 20 6B 7F 42 02 00 "
                    "<paramId> <itemId> <value> F7",
            "types": TYPES, "controls": CONTROLS}


def main():
    ap = argparse.ArgumentParser(description="Build a BeatStep Pro name table from your MCC dictionary.")
    ap.add_argument("mcc", help="path to your Arturia MCC BeatStepPro.json")
    ap.add_argument("-o", "--out", default="beatstep_tables.json",
                    help="output path (default: beatstep_tables.json)")
    args = ap.parse_args()
    if not os.path.exists(args.mcc):
        ap.error(f"MCC dictionary not found: {args.mcc}")
    d = load_mcc(args.mcc)
    tables = {"params": gen_params(d), "controls": gen_controls(d)}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(tables, f, indent=1)
    np = sum(len(s["params"]) for s in tables["params"]["sections"])
    nc = sum(len(v) for v in tables["controls"]["controls"].values())
    print(f"wrote {args.out}  ({np} global params, {nc} controls)")


if __name__ == "__main__":
    main()
