# Notes from a live rig

KeyLabLive is the shareable part of the rig I play gigs with, called SB
Workstation: a KeyLab 88 mk3, Ableton Live 12, Pianoteq, Hammond B-3X,
Omnisphere, a few Live instruments, and an Allen & Heath CQ20B mixer, all run
from the keyboard by a Python control surface script.

That script is too tied to my own gear to publish. This page describes how it
is set up and what it took to make it work, for anyone building something
similar.

---

## What it is meant to do

- The keyboard works without looking at the computer.
- A screen button arms its track, whatever is on the screen.
- No light goes fully dark. Off is dim.
- Things stay where they are. A preset list does not reorder itself, and the
  piano is always on button 1.
- No button starts playback by accident.
- Everything a musician might change lives in text files, not in the code.

---

## Overview

| Control | What it does |
|---|---|
| Screen buttons 1-4 and 8 | Arm one instrument track each. Hold: open that track's preset list |
| Screen button 5 | Next fader/encoder bank. Hold: list of banks |
| Screen button 6 | Shift (latching) for the bank |
| Screen button 7 | Multi list. Hold it and tap a pad: save the current state to that pad |
| Faders 1-9, encoders 1-9 | Whatever the active bank says: mixer level, mixer send, Live volume, Live parameter |
| Pads | 1-4 mixer mutes, 5-8 Pianoteq presets, 9-12 Hammond drawbars (a bank can make them mutes). While a list is open: pick line 1-12 |
| Wheel, Play, Back, Forward | Move in the song list or preset list, and pick |
| Stop | Stop, or close a list without picking |
| Tap, Metro, sustain pedal | Leslie slow/fast, brake, fast while the pedal is down |
| Save | Show the active bank on screen instead of the song list |
| Redo | Reset volumes and arms, reload presets, banks and setlist |

---

## Setting it up

### Live

The script is a folder in `User Library/Remote Scripts`. Live loads it through
`__init__.py`:

```python
from .keylab_workstation import KeylabWorkstation

def create_instance(c_instance):
    return KeylabWorkstation(c_instance)
```

In **Preferences → Link, Tempo & MIDI**:

| Control Surface | Input | Output |
|---|---|---|
| the main script | KeyLab DAW port | KeyLab DAW port |
| the mixer script | CQ20B | CQ20B |

Turn on **Remote** for both ports, In and Out. With two KeyLabs on the same
computer, set the slot of the one that is not plugged in to None.

### The KeyLab

The keyboard has to be in **DAW mode**: Prog, then screen button 6. The script
sends `F0 00 20 6B 7F 42 00 02 05 01 F7` at start and `... 05 00 F7` at the end.
That is a handshake inside DAW mode, not a switch to it.

### The tracks in the set

```
KlvRhd      Pianoteq                 fixed, presets by Program Change
Juno        free place               any preset from the 'Presets' Collection
Hammond     B-3X in an Instrument Rack  fixed, Program Change
Dexed       free place
Omnis       Omnisphere               fixed, Program Change
Relays      group track, folded
  Relay 1   MIDI From: No Input   MIDI To: KlvRhd
  Relay 3   MIDI To: the B-3X inside the rack, not the rack itself
  Relay 5   MIDI To: Omnis
```

- The instrument tracks have **Monitor on Auto**, so arming is what decides
  whether the keyboard plays them.
- Each relay track carries a small Max for Live device, **Preset Bridge**
  (below). It sends Program Change into the instrument through the relay's own
  MIDI routing.
- On the Hammond, MIDI To must point at the plugin inside the rack
  (`Instrument Rack | Hammond B-3X | 1-Hammond B-3X`). Pointed at the rack, the
  rack's key zones filter the notes.

---

## The KeyLab mk3's MIDI in DAW mode

Everything on channel 1 except the pads (channel 10). Read the tables — none of
the rows run in a straight line.

**Screen buttons** (footer id = button number)

| Button | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| CC | 49 | 50 | 51 | 52 | 45 | 46 | 47 | 48 |

Buttons 1-4 are the bottom row, 5-8 the top row.

**Transport row**, left to right

| | Tap | Rec | Play | Stop | Cycle | Back | Fwd | Metro | Redo | Undo | Quant | Save |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CC | 23 | 22 | 21 | 20 | 24 | 25 | 26 | 27 | 44 | 43 | 42 | 41 |
| LED id | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 |

**Faders and encoders** — each has one CC for movement and one for touch

| | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|---|---|---|---|---|---|---|---|---|---|
| Fader move | 105 | 106 | 107 | 108 | 109 | 110 | 111 | 112 | 113 |
| Fader touch | 28 | 29 | 30 | 31 | 33 | 34 | 35 | 36 | 37 |
| Encoder move | 91 | 92 | 94 | 95 | 96 | 97 | 102 | 103 | 104 |
| Encoder touch | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 38 |

Faders send their position, 0-127. Encoders send relative steps around 64.
Touch is 127 on contact and 0 on release.

**Wheel**: CC 116, relative around 64. Click: CC 117. Use only the sign, one
step per message, or a fast turn runs away.

**Pads**: notes 0-11 on channel 10. LED ids 82-93.

### Screen and LEDs

All packets start `F0 00 20 6B 7F 42` and end `F7`.

```
LED:     00 02 03 <id> <r> <g> <b> 00                 colour 0-127, not 0-255
Button:  00 02 04 <id> 00 <03 lit|02 unlit> 00  03 00 00  04 <r> <g> <b> 00  05 <text> 00
Popup:   00 02 04 1E 00 <value> 00 01 <name> 00 02 <bar 0-127> 00 04 7F 7F 7F 00
```

The screen buttons have no LED id; their light is the colour in the button
packet. Lists, cursors and the rest are in
**[keylab-mk3-sysex](https://github.com/saxofonbrian/keylab-mk3-sysex)**.

Things that matter in practice:

- **Send each packet as one message.** Sent byte by byte, a few percent are lost.
- **Plain ASCII 32-126 only.** Anything else costs the character or the whole
  packet. Write æ as ae.
- **Fader readouts need skin contact.** The touch CC comes from a capacitive
  sensor. Push a fader with a fingernail and the value is sent but no readout
  appears. Nothing in code changes that.
- **The fader readout (`1D`) only shows while a fader is touched.** For text
  from the script, use the popup (`1E`).
- **Use list title `14`.** With `28` and no icon on the list items, every
  changing fader readout pauses the keyboard's MIDI for about 60 ms.
- **A list line holds 34 characters, a button label about 12.**
- **36 LED packets in one go freezes the keyboard.** Send them in smaller
  groups.

---

## Live's Python API: what is not in the documentation

### Only the main thread may touch Live

A long press needs a timer, and a timer runs on its own thread. So the timer
only puts the action in a queue. The queue is emptied in `update_display()`,
which Live calls on the main thread about ten times a second.

```python
class LongPress(object):
    def press(self):
        self.cancel()
        self._fired = False
        self._timer = threading.Timer(0.4, self._worker)
        self._timer.daemon = True
        self._timer.start()

    def release(self):
        """True if the press was short."""
        self.cancel()
        return not self._fired

    def _worker(self):
        self._fired = True
        self._surface.enqueue_action(self._on_long)
```

The same queue is needed in a parameter listener: inside the notification you
may read, but not write to another parameter.

### New MIDI listeners need a restart

A new `ButtonElement` is only wired up after Live is restarted. Choosing the
script again in Preferences is not enough.

### A script sends MIDI out of its own port only

The main script's Output is the KeyLab. To reach the mixer, a second, small
script sits in its own Control Surface slot with the CQ20B as Input and Output.
The two find each other through a shared module:

```python
def registry():
    reg = sys.modules.get("cq20b_bridge_registry")
    if reg is None:
        reg = types.ModuleType("cq20b_bridge_registry")
        reg.instance = None
        sys.modules["cq20b_bridge_registry"] = reg
    return reg
```

The mixer script puts itself in `reg.instance`; the main script looks it up when
it needs it. If it is not there, the mixer controls do nothing and everything
else works.

### Program Change without clips

Python cannot send MIDI into a track, and firing a clip that holds a Program
Change also starts playback. The Preset Bridge device does it instead:

```
[live.numbox  pc]       [live.numbox  trigger]
        |                        |
        +------> [js keylab_preset_bridge.js] (inlets 0 and 1)
                         |
                 [midiformat]  (4th inlet, "program")
                         |
                 [midiout]
```

Both numboxes are Live parameters, named `pc` and `trigger`, so the script finds
them in `device.parameters`. The script writes the program number to `pc`, then
flips `trigger` between its min and max. Live only reports a parameter when its
value changes, so without `trigger` picking the same preset twice would do
nothing. The js sends the stored `pc` whenever `trigger` moves:

```js
var lastPc = -1;
function msg_float(v) {
    if (inlet === 0) { lastPc = Math.round(v); return; }
    if (inlet === 1 && lastPc >= 0) outlet(0, lastPc);
}
```

The preset file is indexed by the program number, not by line, so the file can
be ordered freely.

### A held pedal survives un-arm

Un-arm a track with the sustain pedal down and the notes hang, and MIDI routed
into an un-armed track on Monitor Auto is blocked. Preset Bridge has a third
parameter, `cc64off`, that sends CC64 = 0. The script toggles it while the track is still
armed and un-arms one tick later:

```python
def unarm(self):
    toggle(cc64_off_param)
    self._surface.schedule_message(1, self._finish_unarm)

def _finish_unarm(self):
    self.track.arm = False
```

### Loading a preset into a free place

A free place loads presets from a Collection with `browser.load_item()`. To
**replace** the instrument rather than add a new one, the order matters:

1. Select the track (`song.view.selected_track`) and its device
   (`song.view.select_device`).
2. Set `browser.hotswap_target = device`.
3. Check that the selected track is still the one you meant.
4. `browser.load_item(item)`.
5. Set `browser.hotswap_target = None`.

Skip step 1 and Live accepts the hot-swap target but does not use it:
`load_item` then inserts a new device on whatever track happens to be selected.

Collections are found under `colors/<name>` in the browser. Build the browser
index a moment after startup, not during it: while Live is still scanning, the
index comes back empty.

### Stop before the next song, not on it

Stopping exactly on the next locator now and then lets a fragment of the next
song through. The script stops 200 ms early, converted to beats at the current
tempo:

```python
def poll(self):                          # called from update_display()
    song = self._surface.song()
    lead_beats = 200 / 1000.0 * song.tempo / 60.0
    if song.current_song_time >= self._boundary_time - lead_beats:
        song.stop_playing()
        self.move_cursor(1)
```

### Saving state with the set

The active bank, the chosen setlist and the preset on each track are stored in
the Live set:

```python
self.song().set_data("keylab_bank", name)
name = self.song().get_data("keylab_bank", None)
```

Open the set and the keyboard is where it was left.

---

## The text files

All files sit in the script folder. Redo reloads the presets, the banks and the setlist.

### Presets for the fixed tracks

```
KlvRhd
Klaver, 1
Rhodes, 2
PhaserRhd, 4

Hammond
SB1airy, 1
```

A line without a comma is a track name. `Name, PC` is a preset. The PC number
is also its line on screen.

### Banks

```
JM2
farve, 60 127 60
fader 1, KlvRhd, vol KlvRhd
fader 5, Trax, ST2 > Out5
encoder 1, Dynamics, dynamics
encoder 2, KeyRvb, send KlvRhd A
encoder 7, Keys, ST1 > MainLR | ST1 > Out1
```

A line without a comma starts a bank; `farve` is the colour of the bank button.
Each control is `control, name, target`. Left of `|` is the normal target, right
of it the target under shift. A control with no line does nothing.

Targets on the mixer: `Ip3 > Out5` (a send), `Out1` or `MainLR` (an output
master), or a raw NRPN address in hex (`46 18`). Targets in Live:
`vol <track>`, `send <track> <A-L>`, or a named plugin parameter.

### Multis

```
2 Rhodes-Pad
KlvRhd, Rhodes, 108
Juno, SBJuno.vstpreset, 44
```

Name, then `track, preset, volume` (volume 0-127 on Live's fader). `na` keeps
the current preset. Tracks that are not listed are un-armed. Multi number N is
on pad N. Saving from the keyboard rewrites only that Multi's block and keeps
the previous file as `.bak`.

### Setlists

One file per setlist in a `setlister` folder, one song per line:

```
Blueberry Hill
Alle sømænd
2
Smile
```

A line is matched to a locator if the locator's name appears in it. Lines that
match no locator are shown as headings (`2` here is the second set). The chosen
setlist is saved with the set. Without a setlist, all locators are shown.

---

## The mixer

The CQ20B takes NRPN on channel 1 (Allen & Heath CQ MIDI Protocol V1.2):

```
CC99 address MSB   CC98 address LSB   CC6 value   CC38 0      level
CC99 00            CC98 channel       CC6 0       CC38 1/0    mute on/off
CC99 MSB           CC98 LSB           CC96 7F                 ask for the current value
```

The CQ20B wants both data bytes, even for a level. Send CC99 and CC98 only when
the address changes; while a fader moves, CC6 and CC38 are enough, which halves
the traffic. At startup the script asks for the current values, so the pads and
readouts match the mixer before anything is touched.

The bridge script and the address tables are in
**[extras/aaCQ20B](extras/aaCQ20B)**.

---

The code and this text were written with Claude, Anthropic's AI model, from my
decisions and measurements on the hardware.
