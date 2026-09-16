"""
beatstep.tables -- optional friendly names for BeatStep Pro parameters.

A name table maps parameter/value numbers to human-readable labels (functional,
industry-standard terminology). One is bundled so the library and `bsp globals`
show names out of the box. To refresh it from a newer Arturia MIDI Control
Center install, regenerate with tools/gen_tables.py and pass the path to load().

The library and protocol work WITHOUT any table -- it only adds names.
"""
import json
import os

try:
    from importlib.resources import files as _res_files
except Exception:  # pragma: no cover
    _res_files = None

_BUNDLED = os.path.join(os.path.dirname(__file__), "data", "beatstep_tables.json")


def load(path=None):
    """Load a name table. Default: the bundled one. Pass a path to use your own
    (e.g. regenerated from your MCC install via tools/gen_tables.py)."""
    if path:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    if _res_files is not None:
        try:
            txt = _res_files("beatstep").joinpath("data/beatstep_tables.json").read_text(encoding="utf-8")
            return json.loads(txt)
        except Exception:
            pass
    with open(_BUNDLED, encoding="utf-8") as f:
        return json.load(f)


def global_params(tables=None):
    """Flatten the global section to {globalParamId: param_dict}."""
    t = tables or load()
    out = {}
    for sec in t["params"]["sections"]:
        for p in sec["params"]:
            out[p["gp"]] = p
    return out


def label_for(param, value, tables=None):
    """Human label for a global param's current value, or '' if unknown."""
    p = global_params(tables).get(param)
    if not p:
        return ""
    for o in p.get("options", []):
        if o["v"] == value:
            return o["label"]
    return ""
