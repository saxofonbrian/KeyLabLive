# aaCQ20B

The mixer part of SB Workstation, the rig described in
[MANIFESTO.md](../../MANIFESTO.md): a small Live control surface script that
lets another script control an Allen & Heath CQ20B over NRPN.

It does nothing on its own. It is here for anyone who wants to build their own
mixer control from Live.

## Files

| File | |
|---|---|
| `__init__.py` | how Live loads the script |
| `cq20b_bridge.py` | the bridge: sends NRPN, passes the mixer's replies on |
| `cq20b_addresses.py` | turns `ST1 > Out5`, `MainLR` or `Ip8` into an NRPN address. Plain Python, no Live needed |

## Setup

1. Copy the `aaCQ20B` folder into `User Library/Remote Scripts`.
2. In **Preferences → Link, Tempo & MIDI**, choose `aaCQ20B` in a free Control
   Surface slot, with the CQ20B as Input and Output.
3. Turn on **Remote** for the CQ20B, In and Out.

## Using it from your own script

```python
import sys
from .cq20b_addresses import level_address, mute_address

def bridge():
    reg = sys.modules.get("cq20b_bridge_registry")
    return getattr(reg, "instance", None) if reg is not None else None

b = bridge()
if b is not None:
    msb, lsb = level_address("ST1 > Out5")
    b.send_nrpn(msb, lsb, 100, 0)           # level 0-127, data LSB 0

    msb, lsb = mute_address("Ip8")
    b.send_nrpn(msb, lsb, 0, 1)             # 1 = mute, 0 = unmute

    b.add_listener(on_mixer)                # on_mixer(msb, lsb, data_msb, data_lsb)
    b.request_value(*level_address("ST1 > Out5"))
```

Copy `cq20b_addresses.py` into your own script's folder to import it. A reply
to `request_value` arrives through the listener, and so does any change made on
the mixer itself, so pads and readouts can follow the mixer's own state.

Calls into Live from a listener must be queued for the main thread; see
MANIFESTO.md.

## Addresses

From the Allen & Heath CQ MIDI Protocol V1.2. The formulas are in
`cq20b_addresses.py`.

| Target | Example | Address |
|---|---|---|
| Channel send to Main LR | `Ip3 > MainLR` | `40 02` |
| Channel send to an output | `Ip1 > Out1` | `40 44` |
| | `ST1 > Out5` | `42 68` |
| Output master | `MainLR`, `Out1` | `4F 00`, `4F 01` |
| Mute | `Ip8`, `ST1`, `MainLR`, `FX1` | `00 07`, `00 18`, `00 44`, `00 51` |

Channels: `Ip1`-`Ip16`, `ST1`, `ST2`, `USB`, `BT`. With the outputs linked as
stereo pairs, use Out1, Out3 and Out5. Muting FX1 or FX2 mutes the whole effect
return.
