# fakelive

Run KeyLabLive — or your own KeyLab script — without Live and without the
keyboard. A fake Live, a fake clock, and a decoder that turns the SysEx the
script sends back into a picture of the KeyLab's screen.

```
cd extras/fakelive
python3 test_keylablive.py
```

`KeyLabLive: all checks passed` and exit code 0 means the basic moves work:
arm, preset list, chapters, hot-swap, song list, stop before the next locator,
faders, touch readouts and Cycle. A failed check prints the screen as it was.

Python 3, nothing to install.

## Files

| File | |
|---|---|
| `Live.py`, `_Framework/` | stand-ins for the modules Live gives a script |
| `model.py` | song, tracks, devices, parameters, locators, browser — with listeners |
| `rig.py` | loads a script, presses buttons, turns the wheel, moves faders, runs the clock |
| `screen.py` | decodes outgoing SysEx into screen buttons, LEDs, the list and popups |
| `keylablive_set.py` | a small set: four tracks, five locators, a 'Presets' Collection |
| `test_keylablive.py` | the checks |

## Using it

```python
from rig import Rig
import keylablive_set

rig = Rig("../../KeyLabLive", lambda: keylablive_set.build("../../KeyLabLive"))
rig.hold(49, 0.6)              # hold screen button 1
rig.wheel(2)                   # two clicks clockwise
rig.press(21)                  # Play
print(rig.screen.render())     # the screen, as text
print(rig.errors())            # anything the script asked of Live that the model lacks
```

`rig.press(cc)`, `rig.hold(cc, seconds)`, `rig.cc(cc, value)`, `rig.pad(1-12)`,
`rig.wheel(steps)` and `rig.wait(seconds)` drive it. `rig.song`, `rig.app.browser`
and `rig.screen` are there to assert on.

## What it does and does not tell you

- The script is copied to a temporary folder first, so files it writes never
  touch your real ones.
- Timers and `time` are replaced by a fake clock: a long press takes no time.
- When a script asks for something the model does not have, it is listed by
  `rig.errors()`. Scripts often catch `AttributeError` themselves, and without
  this list a gap would pass silently. Add what is missing to `model.py`.
- It does not prove the hardware agrees. It catches logic errors, missing
  listeners and broken files before a test on the keyboard, not instead of one.
