# beatstep-pro-handler

Created as a way to get around having to use midi control center for config, but it uncovered some interesting things in the process. This started as a part of a larger project and this is me parting it off as tools for the larger community.
I went through and parsed both the midi center communications and the .beatsteppro template files included with it, as well as my own. In poking at it in testing, it was discovered that most options change immediately, opening up rather wild possibilities for contextual remapping, etc.

This tool reads and writes every configuration parameter of the Arturia BeatStep Pro over USB SysEx — global settings, knob/pad/step/channel assignments in control mode, live. The crazy bit is that it also unlocks note & channel changes PER PAD in drum mode, also live. I have only tested this last bit enough to see that it works.

This is part of something I run headless on a pi, controlled by a larger audio/midi brain, so no GUI, but knock yourself out of you want to create one.

Most of the summary from here is Claude, but I read through and changed what I felt needed to be changed:

```bash
bsp read 41 06            # read global param 0x41/0x06 (User Channel)
bsp write 41 06 9         # set it to channel 10 (0-based)
bsp globals               # dump every global setting, with names
```

```python
from beatstep_handler import BeatStepPro, PARAM_GLOBAL
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

See [`beatstep_handler/protocol.py`](beatstep_handler/protocol.py) — pure, dependency-free, and
unit-tested byte for byte.

## Install

```bash
pip install beatstep-pro-handler
```

Works on Windows, macOS, and Linux. Runtime needs only **`python-rtmidi`**
(installed automatically).

Or the latest straight from source:

```bash
pip install git+https://github.com/jamisonx-dev/beatstep-pro-handler.git
```

!!! Everything here is USB only — its configuration SysEx is ignored over DIN!!!


## How it talks to the device

- **Send and capture** via python-rtmidi on the BSP's USB config port. The device
  answers a read with the parameter's current live value.
- The device **drops large request bursts**, so reads are paced in small chunks
  with a bounded retry.
- All verified against real hardware, cross-checked byte-for-byte against a
  reference instrument, and covered by tests.

> **Running alongside another app that owns the BSP?** (e.g. a host program that
> holds the sequencer port.) Pass `BeatStepPro(backend="amidi")` on Linux — it
> sends through ALSA rawmidi (`amidi`, from `alsa-utils`) while still capturing
> replies via rtmidi. Not needed for normal standalone use.

## Friendly names (optional)

`bsp globals` and the library can show human-readable parameter names. A name
table is **bundled**, so it works out of the box. The table is parameter numbers
and value enums (interoperability facts) plus generic, industry-standard labels
and a sensible grouping.

To refresh it from a newer firmware/MCC than the bundled one, regenerate it from
**your own** Arturia MIDI Control Center install:

```bash
python tools/gen_tables.py "/PATH TO YOUR OWN FILE/BeatStepPro.json" -o beatstep_handler/data/beatstep_tables.json
```

> This project does **not** redistribute Arturia's MIDI Control Center device
> dictionary, templates, or firmware. The generator reads the copy you already
> have from installing MCC.

## Scope

- **Globals** (95 settable) and **per-control assignments** — full read/write.
- **Project-scope** sequencer scalars are reachable by the same frame.


Per-sequencer/per-step pattern data is out of scope — sorry, mane... this is just about making it hotmappable and exposing otherwise-hidden device options


## Tests

```bash
python -m pytest        # or: python tests/test_protocol.py
```

## License

MIT — see [LICENSE](LICENSE). "BeatStep Pro" and "Arturia" are trademarks of
Arturia; this project is independent and not affiliated with or endorsed by them.
