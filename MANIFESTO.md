# A keyboard for the stage

KeyLabLive is the shareable part of a bigger rig: **SB Workstation**, the setup
I play every gig with. It runs a KeyLab 88 mk3, Ableton Live, a handful of
plugins and an Allen & Heath CQ20B mixer. That rig is too tied to my own gear to
hand out. What can be handed out is how it was thought through, and the few
things about Live and the KeyLab that cost real time to find out.

This page is both.

---

## The philosophy

**1. The stage is not the studio.**
Controllers and scripts are designed at a desk, with a mouse in reach and time
to look. On stage there is neither. Everything needed during a song has to be
on the keyboard, under the hands, readable at a glance.

**2. The most important thing always works.**
A screen button arms its track, whatever the screen shows and whatever menu
happens to be open. A function that only works in the right mode will fail on
the night you are in the wrong one.

**3. No button is ever dark.**
Off means dim, not black. A button you cannot find on a dark stage is worse
than one that shows the wrong state.

**4. Muscle memory is sacred.**
What has a fixed place keeps it. Lists do not reshuffle when something new is
added; the piano is on the same button tonight as last year.

**5. Nothing starts by accident.**
One stray touch must never set the transport running. Firing a clip to send a
message starts playback, so clips are not used to send messages.

**6. The screen is for feedback, not decoration.**
The preset on each track, the song you are on, what the faders control right
now. If you have to wonder, the screen has failed.

**7. A whole state is one press away.**
A song needs pianos, pads, levels and arms set together. Store the lot under one
name and recall it with one pad — and store it from the keyboard, the moment it
sounds right.

**8. Settings live in text, not in code.**
Banks, presets and setlists are plain text files a musician can open and change
in a minute. The code reads them; it does not contain them.

**9. The simplest thing that works, and nothing that does not.**
A change that did not help comes out before the next one goes in. No debug code
left behind, no log lines for things that work, no comments explaining old
attempts.

**10. The hardware has the last word.**
A theory is not a result. Measure against the real keyboard — and when a clean
measurement disagrees with the model, the model is wrong.

---

## What it does in practice

The private rig, in one page:

- **Screen buttons 1-4 and 8** arm instruments. Hold one and its preset list
  opens; pads, the wheel or Play pick from it.
- **Fixed places and free places.** Plugins chosen by Program Change (Pianoteq,
  Hammond, Omnisphere) sit on fixed buttons. The other tracks are free places
  that load any preset tagged in one Live Collection.
- **Banks.** Every fader and encoder does whatever the active bank in a text file
  says: a mixer send, a mixer output, a track volume in Live, a plugin
  parameter. One button steps through banks, another is a latching shift. Save
  shows the bank on screen.
- **Multis.** Hold the Multi button and tap a pad, and the current presets,
  volumes and arms are saved under that pad. Tap it later to get it all back.
- **Repertoire.** Locators are the song list. The wheel picks, Play goes there
  and starts, and playback stops just before the next song.
- **The mixer from the keyboard.** Mute pads and faders talk to the CQ20B,
  and the pads light from the mixer's own state, so they never disagree.

KeyLabLive keeps the parts anyone can use with only Live and a KeyLab.

---

## What took time to find out

For anyone writing their own Live control surface. None of it is in Ableton's
documentation.

### Only the main thread may touch Live

Live calls the script on its main thread, and everything that changes Live must
happen there. A long press needs a timer, and a timer runs on another thread. So
the timer does nothing but put the action in a queue, and the queue is emptied
in `update_display()`, which Live calls on the main thread about ten times a
second.

```python
class LongPress(object):
    def press(self):
        self.cancel()
        self._fired = False
        self._timer = threading.Timer(LONG_PRESS_SECONDS, self._worker)
        self._timer.daemon = True
        self._timer.start()

    def release(self):
        """True if the press was short."""
        self.cancel()
        return not self._fired

    def _worker(self):
        self._fired = True                         # set here, so a release
        self._surface.enqueue_action(self._on_long)  # right after is not short
```

The same queue solves a second rule: inside a listener on one parameter, Live
does not let you write to another. Queue the write instead.

### A new MIDI listener needs a full restart of Live

Choosing the script again in Preferences is not enough. If a button you just
added does nothing, restart Live before you debug anything.

### A script sends MIDI out of its own port only

A control surface has one Output port. Mine is KeyLab DAW, for the screen and
LEDs. To reach a mixer on another port, a second, tiny script sits in its own
Control Surface slot with the mixer as Input and Output, and the two find each
other through a shared module in `sys.modules`:

```python
def registry():
    reg = sys.modules.get("cq20b_bridge_registry")
    if reg is None:
        reg = types.ModuleType("cq20b_bridge_registry")
        reg.instance = None
        sys.modules["cq20b_bridge_registry"] = reg
    return reg
```

It works whatever the folders are called and whichever script Live loads first.
Without the bridge, the mixer part does nothing and the rest still works.

### Program Change without clips

A Python script cannot send MIDI into a track. The obvious workaround — a clip
holding a Program Change — starts playback when fired (see rule 5). What works
instead is a small Max for Live device on a relay track, routed to the
instrument, with two parameters exposed through Configure:

- `pc` — the program number, written by the script
- `trigger` — flipped between min and max on every pick

Live only reports a parameter when its value changes, so without `trigger`,
picking the same preset twice would do nothing. The device turns the change into
a real Program Change with `[midiformat]`.

### A held pedal survives un-arm

Un-arm a track while the sustain pedal is down and the notes hang. Routed MIDI
into an un-armed track with Monitor on Auto is blocked, so the fix has to come
first: send CC64 = 0 while the track is still armed, then un-arm a tick later.

```python
def unarm(self):
    toggle(cc64_off_param)              # pedal up, on the bridge device
    self._surface.schedule_message(1, self._finish_unarm)

def _finish_unarm(self):
    self.track.arm = False
```

### Stop before the next song, not on it

Stopping exactly on the next locator now and then lets a fragment of the next
song through. Stop a fixed 200 ms early instead, converted to beats at the
current tempo every time it is checked:

```python
def poll(self):                         # from update_display()
    song = self._surface.song()
    lead_beats = STOP_LEAD_MS / 1000.0 * song.tempo / 60.0
    if song.current_song_time >= self._boundary_time - lead_beats:
        song.stop_playing()
        self.move_cursor(1)
```

### State belongs to the set

The active bank, the chosen setlist and the preset on each track are stored with
the Live set via `song().set_data(key, value)` and read back with
`song().get_data(key, default)`. Open the set and the keyboard is where you left
it, with no file of its own to lose.

### Text files a musician can edit

A bank is a name followed by one line per control. Left of `|` is the normal
function, right of it the function under shift:

```
JM2
farve, 60 127 60
fader 1, KlvRhd, vol KlvRhd
fader 5, Trax, ST2 > Out5
encoder 2, KeyRvb, send KlvRhd A
encoder 7, Keys, ST1 > MainLR | ST1 > Out1
encoder 8, Main, MainLR | Mon1, Out1
```

(`farve` is Danish for colour: the footer colour of the bank.)

A Multi is a name followed by `track, preset, volume`; tracks not mentioned are
un-armed:

```
2 Rhodes-Pad
KlvRhd, Rhodes, 108
Juno, SBJuno.vstpreset, 44
```

When a Multi is saved from the keyboard, only its own block in the file is
rewritten, and the previous file is kept as `.bak`.

### The KeyLab mk3 screen

The protocol is undocumented. The full map is in
**[keylab-mk3-sysex](https://github.com/saxofonbrian/keylab-mk3-sysex)**. The
facts that matter most when building:

- **Fader and encoder readouts follow skin contact.** The controls are
  capacitive. Push a fader with a fingernail and the value is sent but no
  readout appears. It is not the update rate and cannot be coded away.
- **The fader popup (layout `0x1D`) only appears while a fader is touched.**
  For text sent from the script, use the pad popup (`0x1E`).
- **Send each SysEx packet as one message**, never byte by byte. Byte by byte
  loses a few percent of packets.
- **Draw the list with title `0x14`.** With `0x28` and no icon on the items,
  every changing fader readout pauses the keyboard's MIDI.
- **A list line shows 34 characters.** Footer labels are best kept to about 12.

---

## Credit

The rig, the rules above and every measurement are mine. The code and this text
were written with Claude, Anthropic's AI model.
