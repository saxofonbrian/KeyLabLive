# AGENTS.md

Context for AI coding assistants working on this repository, or building a
similar Ableton Live control surface for the Arturia KeyLab mk3. Read this
before writing code. It records what has been measured on real hardware and
what has already been tried and failed.

Humans: the same facts, explained, are in README.md and MANIFESTO.md.

---

## Where the truth is

| Topic | Source |
|---|---|
| KeyLab mk3 SysEx: screen, LEDs, lists, modes | [keylab-mk3-sysex](https://github.com/saxofonbrian/keylab-mk3-sysex), `keylab-mk3-sysex.md`. Markers: `[measured]` > `[code]` > `[unverified]` > `[guess]`; `[rejected]` = proven wrong |
| KeyLab mk3 MIDI map and packet builders, as used | `KeyLabLive/keylab_screen.py` |
| Working script: arm, presets, song list, clip grid | `KeyLabLive/keylab_live.py` and the other modules in `KeyLabLive/` |
| User settings | `KeyLabLive/keylab_config.py` (imports nothing) |
| Live API behaviour found the hard way | MANIFESTO.md, section "Live's Python API" |
| Allen & Heath CQ20B over NRPN | `extras/aaCQ20B/` |
| Running a script without Live or hardware | `extras/fakelive/` |
| Design rules for the stage | MANIFESTO.md, "What it is meant to do" |

If this file and the code disagree, the code was tested on hardware; trust it
and fix this file.

---

## Environment

- Ableton Live 12.4 on macOS. Live's embedded Python 3. Scripts use
  `_Framework` (`ControlSurface`, `ButtonElement`).
- Script = a folder in `~/Music/Ableton/User Library/Remote Scripts/` with an
  `__init__.py` exposing `create_instance(c_instance)`.
- Live's log: `~/Library/Preferences/Ableton/Live <version>/Log.txt`.
  `self.log_message()` writes there. Read it yourself before asking the user to.
- KeyLab 61 and 88 mk3 are identical in SysEx; only the port name differs.
- The keyboard must be in DAW mode (Prog + screen button 6). This cannot be
  switched from software.

---

## Hard rules

### Live API

1. Only Live's main thread may touch Live. Timers (`threading.Timer`) may only
   put a callable in a queue; drain the queue in `update_display()`
   (~10 Hz, main thread).
2. Inside a listener callback you may read, but not set another parameter.
   Queue the write.
3. A new `ButtonElement` listener needs a full restart of Live. Re-selecting the
   script in Preferences is not enough.
4. A script can send MIDI only out of its own Output port. For a second device,
   use a second script in another Control Surface slot; share state through a
   module in `sys.modules`.
5. Python cannot send MIDI into a track. Program Change goes through a Max for
   Live device on a relay track whose parameters the script writes (see
   MANIFESTO.md, "Program Change without clips"). Live only notifies on
   value *changes*: pair the value with a trigger parameter that flips.
6. Never fire a clip to send a message. Firing a clip starts the transport.
7. MIDI routed into an un-armed track with Monitor on Auto does not reach the
   instrument. Send CC64 = 0 *before* un-arming, then un-arm a tick later
   (`schedule_message(1, ...)`).
8. Hot-swap order: select track and device → `browser.hotswap_target = device`
   → confirm `song.view.selected_track` is the target → `browser.load_item()`
   → `hotswap_target = None`. Without the selection, Live inserts a new device
   on whatever track is selected.
9. Collections are browser root `colors/<name>`. Build the browser index after
   startup, retrying from `update_display()`; during set load it comes back
   empty.
10. Persist per-set state with `song().set_data(key, value)` /
    `song().get_data(key, default)`.
11. Time long presses with your own clock or `threading.Timer`, not with
    `schedule_message` delays.

### KeyLab mk3

1. Send each SysEx packet as one message. Byte-by-byte loses 2-4 % of packets.
2. Text: ASCII 32-126 only. Transliterate everything else.
3. Fader/encoder readouts are triggered by the capacitive touch sensor (touch
   CCs 28-31/33-37 and 8-15/38). No skin contact, no readout. Not fixable in
   code.
4. Fader popup layout `0x1D` only renders while a fader is physically touched.
   Use the pad popup `0x1E` for text from the script.
5. Lists: use title `0x14`. With `0x28` and items without an icon field, every
   changing fader readout pauses the keyboard's MIDI for ~60 ms per ~100 ms.
6. A `0x14` list line shows 34 characters. Footer labels: ~12.
7. Cursor packet: send the absolute index of the line in the whole list. The
   firmware places the box itself.
8. Do not send ~36 LED packets in one burst; the keyboard freezes and needs a
   power cycle.
9. Families `00 02 04` (DAW) and `00 01 04` (Analog Lab) are isolated; a page
   from one ignores packets from the other.
10. Colours are 0-127 per channel, not 0-255. Screen buttons have no LED id;
    their light is the colour field in the footer packet.

### Plugins and routing

1. Do not drive plugins with Program Change as VST3 in Live: VST3 does not
   treat Program Change as MIDI, and Live writes back a 0, causing a second,
   wrong program change. Use the AU version.
2. To reach a plugin inside an Instrument Rack, point the relay's MIDI To at
   the plugin inside the rack, not at the rack, or the rack's key zones filter
   notes.
3. Keep Max for Live devices out of the instrument tracks' signal path. A
   `midiin → midiparse → midiformat → midiout` chain there once latched shut
   after a burst of 48 CCs and stayed shut until the set was reloaded.

---

## Already tried — do not retry

| Idea | Result |
|---|---|
| Show text with fader popup `0x1D` from software | Never renders without touch |
| Encoder layout `0x1C` for fader readouts | More lag, more missing updates |
| Throttle or dedupe screen updates to fix missing readouts | Cause is touch, not rate |
| Throttle screen updates to fix MIDI timing | Rate made no difference; cause was list title `0x28` |
| Relative (pickup) faders | Rejected; faders must be absolute |
| Instrument Rack + Chain Selector for presets | Rejected by the author; no CPU saving with third-party plugins |
| Clips holding CC64 = 0 or Program Change | Start the transport |
| Relay MIDI into an un-armed track as panic | Blocked by Monitor Auto |
| `device.is_active` off/on as panic | Plugin keeps its held notes |
| Live's Stop as panic for every plugin | Dexed ignores it; needs CC64 = 0 |
| Read the current preset from an M4L numbox at startup | Unreliable; store it with `set_data` |
| `21 11 40 02 00 <n>` (KeyLab Essential mk3) to switch mode | Does nothing on mk3 |
| Writing `.amxd` files with a script | Cables from js outlets > 0 were lost on load. Hand the user patcher JSON to paste instead |
| Yamaha FC7 expression pedal | Wrong taper/impedance for the KeyLab. M-Audio EX-P works |

---

## How the author works

- The hardware decides. A clean measurement that contradicts the model means the
  model is wrong — not that more data is needed.
- Cheap checks before expensive ones: a file listing or a test against a fake
  Live before asking for a hardware test.
- One change at a time. If a change did not help, remove it before the next one.
- Logging: only when something is missing or fails. No status lines for things
  that work. No debug code left behind.
- Comments and README describe what the code does now. No history of attempts,
  no hedging.
- Everything a musician may change goes in `keylab_config.py` or a plain text
  file, never in the logic.
- No light fully dark; arming always works; nothing may start the transport by
  accident.

---

## Testing without Live

`extras/fakelive/` is a fake Live: stand-ins for `Live` and `_Framework`, an
observable object model, a fake clock replacing `threading.Timer` and `time`,
and a decoder that renders the SysEx sent to the KeyLab as text.

```
cd extras/fakelive && python3 test_keylablive.py
```

Run it after every change, before asking for a test on hardware. When adding a
feature, add a check to `test_keylablive.py`. When `rig.errors()` reports a
missing attribute, add it to `model.py` with the behaviour Live has.

---

## Not in this repository

The author's full rig (SB Workstation) adds Multis (save presets, volumes and
arms to a pad from the keyboard), setlists in text files, fader/encoder banks in
a text file with a latching shift, mixer mute pads that follow the mixer's
state, Hammond drawbar presets and Leslie control. Its code is private;
MANIFESTO.md describes each feature and its file format precisely enough to
rebuild it on top of KeyLabLive.
