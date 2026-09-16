# beatstep-pro

Read and write **every** configuration parameter of the Arturia **BeatStep Pro**
over USB SysEx — global settings and per-control (knob / pad / step) assignments —
headless, from Python or the command line. No MIDI Control Center, no GUI.

```bash
bsp read 41 06            # read global param 0x41/0x06 (User Channel)
bsp write 41 06 9         # set it to channel 10 (0-based)
bsp globals               # dump every global setting, with names
```

```python
from beatstep import BeatStepPro, PARAM_GLOBAL
with BeatStepPro() as bsp:
    print(bsp.read(PARAM_GLOBAL, 0x06))       # -> current User Channel
    bsp.write(PARAM_GLOBAL, 0x06, 9, verify=True)
```

## The protocol (the whole thing)

One uniform SysEx frame reads or writes any parameter:

```
WRITE:  F0 00 20 6B 7F 42 02 00 <paramId> <itemId> <value> F7
READ:   F0 00 20 6B 7F 42 01 00 <paramId> <itemId>         F7
  reply:F0 00 20 6B 7F 42 02 00 <paramId> <itemId> <value> F7   (+ ack 1C)
```

- `00 20 6B` = Arturia, `7F 42` = BeatStep Pro, `02`/`01` = write/read.
- **paramId `0x41`** = the global bank; `itemId` = the global's id.
- **paramId `0x01`–`0x08`** = per-control fields (Mode / Channel / Data / Min /
  Max / Option / Acceleration / Ports); which field a shared id means depends on
  the control's Mode.
- Control itemIds: **knobs 32–47, pads 112–127, steps 48–63**.
- Channel specials: **User `0x41`, All `0x7E`, Drum `0x42`**.
- LIST values are **non-contiguous** (a knob's Mode uses 0,1,4,12,13,14,15) —
  send the value the device expects, not an index.

See [`beatstep/protocol.py`](beatstep/protocol.py) — pure, dependency-free, and
unit-tested byte for byte.

## Install

```bash
pip install beatstep-pro
```

Runtime needs **`python-rtmidi`** (installed automatically) and the ALSA
**`amidi`** command-line tool (`sudo apt install alsa-utils`).

**Platform:** Linux (a Raspberry Pi, a Linux laptop). The device is driven
through ALSA rawmidi. **Connect the BSP by USB — its configuration SysEx is
ignored over DIN** (real-time MIDI over DIN works fine, that's just not what this
tool does).

## How it talks to the device (hard-won)

- **Send** via ALSA rawmidi (`amidi -S`). A plain rtmidi *send* does not reliably
  reach the config endpoint; the rawmidi path does.
- **Capture** replies via python-rtmidi co-subscribed to the BSP's config port —
  works even while another program also holds the device.
- The device **drops large request bursts**, so reads are paced in small chunks
  with a bounded retry.

All verified against real hardware, cross-checked byte-for-byte against a
reference instrument, and covered by tests.

## Friendly names (optional)

`bsp globals` and the library can show human-readable parameter names. A name
table is **bundled**, so it works out of the box. The table is parameter numbers
and value enums (interoperability facts) plus generic, industry-standard labels
and a sensible grouping.

To refresh it from a newer firmware/MCC than the bundled one, regenerate it from
**your own** Arturia MIDI Control Center install:

```bash
python tools/gen_tables.py "/path/to/your/BeatStepPro.json" -o beatstep/data/beatstep_tables.json
```

> This project does **not** redistribute Arturia's MIDI Control Center device
> dictionary, templates, or firmware. The generator reads the copy you already
> have from installing MCC.

## Scope

- **Globals** (95 settable) and **per-control assignments** — full read/write.
- **Project-scope** sequencer scalars are reachable by the same frame.
- **Per-sequencer / per-step pattern data is out of scope** — the device
  addresses it per-pattern in a bulk frame this uniform frame can't carry, so
  writes to it don't take. This tool never pretends to set something it can't.

## Tests

```bash
python -m pytest        # or: python tests/test_protocol.py
```

## License

MIT — see [LICENSE](LICENSE). "BeatStep Pro" and "Arturia" are trademarks of
Arturia; this project is independent and not affiliated with or endorsed by them.
