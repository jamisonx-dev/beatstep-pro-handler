"""Read a few global settings from a connected BeatStep Pro."""
from beatstep import BeatStepPro, PARAM_GLOBAL

with BeatStepPro(verbose=True) as bsp:
    # (paramId, itemId) pairs. 0x41 = the global bank; item = the global's id.
    vals = bsp.read_many([
        (PARAM_GLOBAL, 0x06),   # User Channel
        (PARAM_GLOBAL, 0x02),   # Pad Poly Aftertouch
        (PARAM_GLOBAL, 0x10),   # Sync / clock source
    ])
    for (param, item), v in vals.items():
        print(f"0x{param:02X}/0x{item:02X} = {v}")
