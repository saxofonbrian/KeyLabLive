# =============================================================================
# KeyLabLive - the control surface
# =============================================================================
#
# Settings are in keylab_config.py. The keyboard's protocol is in
# keylab_screen.py. This file is the machinery that joins them.
#
# The code and comments in this script were written by Claude, Anthropic's AI
# model - see Credit in README.md.
#
# WHAT IT DOES
#   - The screen buttons arm and un-arm the first tracks in the set, up to
#     eight (MAX_TRACKS), labelled and coloured from the track itself. A short press always does that - there is no state in
#     which the button means something else.
#   - Holding a screen button opens the preset list for that track. Pick with
#     the jog wheel, Play or Back/Forward; Stop closes the list without
#     picking. All tracks share one list; only the choice is per track.
#     That button turns yellow for as long as its list is on screen, so the
#     list is never anonymous. Holding a DIFFERENT button moves the list to
#     that track, and the yellow moves with it.
#   - The middle of the screen lists the Arrangement locators. The wheel moves
#     the cursor; Play jumps and starts; playback stops just before the next
#     locator and the cursor moves on. The list follows the locators live.
#   - The faders set track volume, one per track. Absolute, but the position the keyboard
#     reports at startup is not treated as a move - see _Fader.
#   - Cycle rebuilds the preset list from your Collection.
#   - Tap and Metro are tap tempo and the metronome, and step between chapters
#     while a preset list is open.
#   - Save is Capture MIDI; Undo, Redo and Quantize are Live's own.
#   - With SESSION_GRID switched on in keylab_config.py, pads 1-12 launch
#     clips. Off, the pads are claimed but do nothing, and Record is Live's
#     Arrangement Record.
#   - With the grid on, holding Record turns Back/Forward and the jog wheel into clip-launch-
#     grid navigation (pan across tracks / scenes) instead of their normal
#     roles, and turns a pad press into deleting that slot's clip instead of
#     launching it - see _Record and Session.pan in keylab_session.py.
#   - Screen buttons, faders and the clip-launch grid all follow the set's
#     actual track list live - add or remove a track and they catch up on
#     their own, no restart needed. See _on_tracks_changed.
#
# HOW MIDI GETS IN
#   A remote script only receives notes and CCs that it has asked Live to
#   forward, and that request is made per control in build_midi_map. That is
#   what ButtonElement does for us. A script with no controls receives nothing
#   at all - it loads, reports success and sits there silently.
#
# A NOTE ON RESTARTS
#   Adding a new MIDI listener needs Live restarted, not just a change in the
#   Control Surface dropdown. Editing the preset file or your Collection does
#   not - that is what Cycle is for.
# =============================================================================

from __future__ import absolute_import, print_function, unicode_literals

import os
import threading
import time

try:
    import Queue as queue          # Python 2
except ImportError:
    import queue                   # Python 3

from _Framework.ButtonElement import ButtonElement
from _Framework.ControlSurface import ControlSurface
from _Framework.InputControlElement import MIDI_CC_TYPE, MIDI_NOTE_TYPE

from . import keylab_config as cfg
from . import keylab_screen as scr
from .keylab_presets import (
    PresetBrowser, chapters_of, load_manual_file, load_preset_file,
    merge_preset_entries, preset_key, short_label, write_preset_file,
)
from .keylab_repertoire import Repertoire
from .keylab_session import Session


def _clamp(value):
    """Live's volume parameter runs 0.0-1.0. This is a position on Live's own
    fader curve, not decibels."""
    return max(0.0, min(1.0, value))


# =============================================================================
# One track
# =============================================================================

class _Track(object):
    """
    A screen button, its track, and that track's place in the preset list.

    The button has exactly two jobs, and which one you get depends only on how
    long you hold it - never on what is on the screen. Short press arms or
    un-arms. Long press opens the preset list and keeps it open while held -
    see _on_button.

    That matters more than it sounds. A third job - a short press picking the
    entry at the cursor while this track's list is open - reads well on paper
    and is wrong in the hand, because arm would then stop working whenever a
    list happened to be open, and arm is the one thing on this keyboard that
    has to work without being thought about. Picking is already covered three
    other ways; arming is not.
    """

    def __init__(self, surface, index, track):
        self._surface = surface
        self.index = index
        self.track = track
        self.footer_id, button_cc = scr.SCREEN_BUTTONS[index + 1]

        self.chosen = None         # index of the preset showing in the footer
        self.chapter = None        # the chapter its list was last open in
        self._label = None         # footer text, or None for the track name
        self._pressed_at = None
        self._opened_by_hold = False

        self.button = ButtonElement(
            True, MIDI_CC_TYPE, scr.MAIN_CHANNEL, button_cc)
        self.button.add_value_listener(self._on_button)

        try:
            self.track.add_arm_listener(self._on_arm)
            self.track.add_name_listener(self._on_name)
            self.track.add_color_listener(self._on_arm)
        except (AttributeError, RuntimeError):
            pass

    @property
    def entries(self):
        """
        The preset list - the one list, held by the surface and shared by every
        track. A track is a slot that becomes whatever is loaded into it, so
        there is nothing to divide up. Only WHICH entry a track has chosen
        (self.chosen) and which chapter it was last looking at belong to the
        track.
        """
        return self._surface.entries

    # -- display -------------------------------------------------------------

    def label(self):
        """
        The preset name once one has been chosen, else the track's name - cut
        to what the button can show.

        The cut happens here and not in the file, so the file holds the
        preset's real name and there is never a second name to keep in step
        with it.
        """
        if self._label:
            return short_label(self._label)
        try:
            return short_label(self.track.name)
        except (AttributeError, RuntimeError):
            return "Track %d" % (self.index + 1)

    def set_label(self, text):
        self._label = text
        self.draw()

    def draw(self):
        try:
            armed = bool(self.track.arm)
        except (AttributeError, RuntimeError):
            armed = False
        if self._surface.preset_track is self:
            # This track's list is the one on screen. Yellow says so, and says
            # it whether or not the track is armed - arm is a short press away
            # at any moment, and the button must not go quiet underneath the
            # list it belongs to. Brightness still carries arm, so nothing is
            # lost: the colour says whose list this is, the brightness says
            # whether it is armed.
            colour = cfg.FOOTER_LIST_ARMED if armed else cfg.FOOTER_LIST_UNARMED
        else:
            colour = None
            if cfg.TRACK_COLOUR_FOOTER:
                colour = scr.track_colour(self.track, armed, cfg.TRACK_COLOUR_DIM)
            if colour is None:
                colour = cfg.FOOTER_ARMED if armed else cfg.FOOTER_UNARMED
        self._surface.send(
            scr.footer_packet(self.footer_id, armed, self.label(), colour))

    def _on_arm(self):
        self.draw()

    def _on_name(self):
        # Only matters while no preset has been chosen - after that the footer
        # shows the preset, and the track name is free to follow whatever
        # device a hot-swap has just put there.
        if not self._label:
            self.draw()

    # -- button --------------------------------------------------------------

    def _on_button(self, value):
        """
        Two outcomes, and the only thing that chooses between them is the
        clock. Nothing here looks at whether a list is open, deliberately: the
        lights on these buttons mean armed, and a button whose meaning changes
        under you is a button you cannot use without looking.
        """
        if value == 127:
            self._pressed_at = time.time()
            self._opened_by_hold = False
            # A background timer, because Live gives us no callback for "still
            # held". It only ever hands work back to the main thread.
            threading.Timer(cfg.LONG_PRESS_SECONDS, self._held).start()
            return

        held = time.time() - (self._pressed_at or time.time())
        self._pressed_at = None

        if held >= cfg.LONG_PRESS_SECONDS and self._opened_by_hold:
            return                      # list opened on the way down; leave it
        self._toggle_arm()

    def _held(self):
        if self._pressed_at is None:
            return                      # released before the threshold
        self._opened_by_hold = True
        self._surface.enqueue(lambda: self._surface.open_preset_list(self))

    def _toggle_arm(self):
        try:
            self.track.arm = not self.track.arm
        except (AttributeError, RuntimeError) as exc:
            self._surface.log_message(
                "KeyLabLive: could not arm track %d (%r)" % (self.index + 1, exc))

    def disconnect(self):
        self.button.remove_value_listener(self._on_button)
        for remove, callback in (("remove_arm_listener", self._on_arm),
                                 ("remove_name_listener", self._on_name),
                                 ("remove_color_listener", self._on_arm)):
            try:
                getattr(self.track, remove)(callback)
            except Exception:
                # Broad on purpose: a track that was just deleted - which is
                # exactly when this runs, from _on_tracks_changed - raises
                # Boost.Python.ArgumentError here, not AttributeError or
                # RuntimeError.
                pass


# =============================================================================
# Faders
# =============================================================================

class _Fader(object):
    """
    Fader N sets track N's volume. Absolute, raw 0-127, no decibel conversion:
    where the fader stands is what the track gets. That is deliberate - a fader
    you can see the position of should mean what it looks like it means.

    THE ONE VALUE THAT IS NOT A MOVE IS THE FIRST. The keyboard reports every
    fader's position the moment the script connects, and the faders have no
    motors, so those positions are simply where the hardware was left - nothing
    to do with the set that is being opened. Taken as moves they would overwrite
    the saved volumes every time a set is opened. That first value is noted
    and nothing else; the fader takes the track the moment it is
    actually moved.

    That still means the first move jumps the track to where the fader stands,
    which is what absolute costs and is why the touch CC matters: rest a finger
    on a fader and the track's own value appears on the screen before anything
    moves. Touch to look, move to take over.

    Both the volume and the screen are updated for every incoming value, with
    no throttle. A readout that does not appear is the capacitive touch sensor,
    not the update rate. The accepted trade is that a fast fader move
    during fast playing on the same track gives a very slight MIDI timing
    hiccup - it is the sysex traffic itself, not its frequency, and it is worth
    the feedback. Do not try to tune it away.
    """

    def __init__(self, surface, index, track):
        self._surface = surface
        self._index = index
        self._track = track
        self._last = None          # None until this fader has reported once
        try:
            self._volume = track.mixer_device.volume
        except (AttributeError, RuntimeError):
            self._volume = None
        self.control = ButtonElement(
            False, MIDI_CC_TYPE, scr.MAIN_CHANNEL, scr.FADER_VALUE_CCS[index])
        self.control.add_value_listener(self._on_value)

        # Every fader has a second CC that fires on skin contact alone. It is
        # what makes an absolute fader usable: rest a finger on it and the
        # track's value appears, without anything moving.
        self.touch = None
        if index < len(scr.FADER_TOUCH_CCS):
            self.touch = ButtonElement(
                True, MIDI_CC_TYPE, scr.MAIN_CHANNEL, scr.FADER_TOUCH_CCS[index])
            self.touch.add_value_listener(self._on_touch)

    def _on_touch(self, value):
        """
        A finger landed on the fader. Show where the TRACK is - nothing has
        moved yet, and this must not move it.

        The keyboard puts its own readout up at the same instant, drawn from
        where the hardware is standing. This overwrites it with the track's
        value, so you can see what you are about to take over before you do.
        """
        if value == 0:
            return                  # on touch, not on release
        if self._volume is None:
            return
        try:
            raw = int(round(self._volume.value * 127))
        except (AttributeError, RuntimeError):
            return
        self._draw(raw)

    def _on_value(self, value):
        if self._last is None:
            # The connect-time report. Note where the fader is standing and
            # leave the track alone.
            self._last = value
            return
        if value == self._last or self._volume is None:
            return
        self._last = value
        try:
            self._volume.value = _clamp(value / 127.0)
        except (AttributeError, RuntimeError):
            return
        self._draw(value)

    def _draw(self, raw):
        """
        The track's value on the screen, as the raw 0-127 number.

        One number the whole way: what the fader sends, what is written to
        Live, and what the keyboard's own readout uses. Not decibels and not a
        percentage - those would be a second scale to convert between for no
        gain.
        """
        if not cfg.FADER_SHOW_VALUE:
            return
        try:
            name = self._track.name
        except (AttributeError, RuntimeError):
            name = "Track %d" % (self._index + 1)
        self._surface.send(
            scr.fader_packet(str(raw), name, raw, cfg.FADER_POPUP))

    def disconnect(self):
        self.control.remove_value_listener(self._on_value)
        if self.touch is not None:
            self.touch.remove_value_listener(self._on_touch)


# =============================================================================
# Pads
# =============================================================================

class _Pad(object):
    """
    Pads 1-12 are the clip-launch grid when SESSION_GRID is on - including
    while a preset list is open on screen - and nothing at all when it is
    off. See KeyLabLive.pad_pressed.

    In the DAW bank the pads send NOTES on channel 10, not CC.
    """

    def __init__(self, surface, index):
        self._surface = surface
        self._index = index
        self.control = ButtonElement(
            True, MIDI_NOTE_TYPE, scr.PAD_CHANNEL, scr.PAD_FIRST_NOTE + index)
        self.control.add_value_listener(self._on_value)

    def _on_value(self, value):
        if value > 0:
            self._surface.pad_pressed(self._index)

    def disconnect(self):
        self.control.remove_value_listener(self._on_value)


# =============================================================================
# Transport
# =============================================================================

class _Transport(object):
    """
    Stop / Play / Back / Forward.

    They drive the repertoire list normally, the preset list while one is
    open (Back/Forward move the cursor, Play applies without closing the
    list so several can be tried in a row, and Stop closes it), and the
    clip-launch grid's window while Record is held (Back/Forward pan it
    across tracks, one step per press - see Session.pan). The preset list
    always wins when one is open; Record-shift is only even checked once
    that is ruled out.
    """

    def __init__(self, surface):
        self._surface = surface
        self._held = None
        self._repeat_at = 0.0
        self.stop = self._button(scr.STOP_CC, self._on_stop)
        self.play = self._button(scr.PLAY_CC, self._on_play)
        self.back = self._button(scr.BACK_CC, self._on_back)
        self.forward = self._button(scr.FORWARD_CC, self._on_forward)

    def _button(self, cc, callback):
        element = ButtonElement(True, MIDI_CC_TYPE, scr.MAIN_CHANNEL, cc)
        element.add_value_listener(callback)
        return element

    def _on_stop(self, value):
        if value != 127:
            return
        if self._surface.preset_track is not None:
            self._surface.close_preset_list()
            return
        self._surface.repertoire.stop()

    def _on_play(self, value):
        if value != 127:
            return
        if self._surface.preset_track is not None:
            self._surface.apply_preset_at_cursor(keep_open=True)
            return
        self._surface.repertoire.play_cursor()

    def _on_back(self, value):
        self._light(scr.BACK_LED, value)
        self._navigate(value, -1)

    def _on_forward(self, value):
        self._light(scr.FORWARD_LED, value)
        self._navigate(value, 1)

    def _light(self, led, value):
        idle, pressed = self._surface.nav_colours()
        self._surface.send(scr.led_packet(led, pressed if value == 127 else idle))

    def _navigate(self, value, direction):
        if value != 127:
            if self._held == direction:
                self._held = None
            return
        if self._surface.preset_track is not None:
            # One step per press inside a preset list, and the preset is
            # applied after a pause - see NAV_SELECT_DELAY. Holding the button
            # down would otherwise load every preset it passed over.
            self._surface.move_preset_cursor(direction)
            self._surface.arm_delayed_apply()
            return
        if self._surface.shift_held():
            # Pans the clip-launch grid across tracks instead of scrolling
            # the repertoire. One step per press - no repeat
            # while held, unlike the repertoire scroll below.
            self._surface.grid_pan(direction, 0)
            return
        self._surface.repertoire.move(direction)
        self._held = direction
        self._repeat_at = time.time() + cfg.NAV_REPEAT_DELAY

    def poll(self):
        if self._held is None:
            return
        now = time.time()
        if now < self._repeat_at:
            return
        self._repeat_at = now + cfg.NAV_REPEAT_INTERVAL
        self._surface.repertoire.move(self._held)

    def disconnect(self):
        for element, callback in ((self.stop, self._on_stop),
                                  (self.play, self._on_play),
                                  (self.back, self._on_back),
                                  (self.forward, self._on_forward)):
            element.remove_value_listener(callback)


# =============================================================================
# Chapters
# =============================================================================

class _Chapters(object):
    """
    Tap and Metro step between chapters while a preset list is open.
    Otherwise they are their own native selves: Tap Tempo
    (song().tap_tempo()) and the metronome (song().metronome).

    They are the only two buttons in the transport row this script otherwise
    does not use, which is why chapters got the job: Back/Forward already
    step the cursor and audition what they land on, and taking that away to
    switch chapters would cost more than it gained. Nothing here takes
    anything away from their native role - it only runs while a list happens
    to be open, which tap tempo and the metronome have no use for anyway.
    """

    def __init__(self, surface):
        self._surface = surface
        self.previous = self._button(scr.TAP_CC, self._on_previous)
        self.next = self._button(scr.METRO_CC, self._on_next)
        self._pulses_left = 0
        self._pulse_at = None
        self._pulse_on = False

        self._metronome_listener = False
        try:
            self._surface.song().add_metronome_listener(self._on_metronome_changed)
            self._metronome_listener = True
        except (AttributeError, RuntimeError):
            pass

    def _button(self, cc, callback):
        element = ButtonElement(True, MIDI_CC_TYPE, scr.MAIN_CHANNEL, cc)
        element.add_value_listener(callback)
        return element

    # -- routing: chapter navigation while a list is open, native otherwise --

    def _on_previous(self, value):
        if self._surface.preset_track is not None:
            self._press(value, -1, scr.TAP_LED)
        else:
            self._on_tap(value)

    def _on_next(self, value):
        if self._surface.preset_track is not None:
            self._press(value, 1, scr.METRO_LED)
        else:
            self._on_metro(value)

    def _press(self, value, direction, led):
        if not self._surface.chapters_active():
            return
        # Touching either button answers the question the pulse was asking.
        self._pulses_left = 0
        self._pulse_at = None
        self._surface.send(scr.led_packet(
            led, cfg.CHAPTER_PRESSED if value == 127 else cfg.CHAPTER_IDLE))
        if value == 127:
            self._surface.change_chapter(direction)

    # -- native: Tap Tempo ------------------------------------------------

    def _on_tap(self, value):
        self._surface.send(scr.led_packet(
            scr.TAP_LED, cfg.TAP_FLASH if value == 127 else cfg.TAP_IDLE))
        if value != 127:
            return
        try:
            self._surface.song().tap_tempo()
        except (AttributeError, RuntimeError) as exc:
            self._surface.log_message("KeyLabLive: tap_tempo failed (%r)" % (exc,))

    # -- native: Metronome --------------------------------------------------

    def _on_metro(self, value):
        if value != 127:
            return
        try:
            song = self._surface.song()
            song.metronome = not song.metronome
        except (AttributeError, RuntimeError) as exc:
            self._surface.log_message("KeyLabLive: metronome toggle failed (%r)" % (exc,))

    def _on_metronome_changed(self):
        self._refresh_metro()

    def _refresh_metro(self):
        # Only draws while no list is open - chapters_active owns the LED
        # the rest of the time (see update_chapter_leds in KeyLabLive).
        if self._surface.preset_track is not None:
            return
        try:
            on = bool(self._surface.song().metronome)
        except (AttributeError, RuntimeError):
            on = False
        self._surface.send(scr.led_packet(scr.METRO_LED, cfg.METRO_ON if on else cfg.METRO_OFF))

    def refresh_native(self):
        """Called by KeyLabLive.update_chapter_leds once no list is open."""
        self._surface.send(scr.led_packet(scr.TAP_LED, cfg.TAP_IDLE))
        self._refresh_metro()

    # -- the opening pulse ---------------------------------------------------

    def pulse(self):
        """
        Blink both buttons a few times, then hold steady.

        This is the only thing on the keyboard that says the chapter buttons
        exist. It fires when a list opens and then stops: a light that blinks
        all evening beside Play is noise on stage, and worse, it looks like a
        warning. A few pulses catch the eye once and then get out of the way.

        There is no blink in the firmware - Arturia's LED packet carries a
        colour and nothing else - so this is done here, on the poll loop.
        """
        if not self._surface.chapters_active():
            return
        if cfg.CHAPTER_PULSES <= 0:
            return
        self._pulses_left = cfg.CHAPTER_PULSES * 2      # on and off each time
        self._pulse_at = time.time()
        self._pulse_on = False

    def poll(self):
        if self._pulse_at is None:
            return
        if time.time() < self._pulse_at:
            return
        # A list closed under us, or the chapters went away: stop and let
        # update_chapter_leds put the buttons back where they belong.
        if not self._surface.chapters_active():
            self._pulses_left = 0

        if self._pulses_left <= 0:
            self._pulse_at = None
            self._surface.refresh_chapter_leds()
            return

        self._pulses_left -= 1
        self._pulse_on = not self._pulse_on
        colour = cfg.CHAPTER_PRESSED if self._pulse_on else cfg.CHAPTER_OFF
        self._surface.send(scr.led_packet(scr.TAP_LED, colour))
        self._surface.send(scr.led_packet(scr.METRO_LED, colour))
        self._pulse_at = time.time() + cfg.CHAPTER_PULSE_SECONDS

    def disconnect(self):
        self.previous.remove_value_listener(self._on_previous)
        self.next.remove_value_listener(self._on_next)
        if self._metronome_listener:
            try:
                self._surface.song().remove_metronome_listener(self._on_metronome_changed)
            except (AttributeError, RuntimeError):
                pass


# =============================================================================
# Jog wheel
# =============================================================================

class _Wheel(object):
    """
    Turn moves the cursor, click selects - in the repertoire list normally,
    or in the preset list while one is open. While Record is held (and no
    preset list is open) turning instead pans the clip-launch grid's window
    across scenes, one step per detent - see Session.pan.
    """

    def __init__(self, surface):
        self._surface = surface
        self.turn = ButtonElement(False, MIDI_CC_TYPE, scr.MAIN_CHANNEL, scr.WHEEL_CC)
        self.turn.add_value_listener(self._on_turn)
        self.click = ButtonElement(True, MIDI_CC_TYPE, scr.MAIN_CHANNEL, scr.WHEEL_CLICK_CC)
        self.click.add_value_listener(self._on_click)

    def _on_turn(self, value):
        if value == scr.WHEEL_CENTRE:
            return
        # Sign only. The value moves further from centre the faster you turn,
        # and using the magnitude makes a list run away.
        direction = 1 if value > scr.WHEEL_CENTRE else -1
        if self._surface.preset_track is not None:
            self._surface.move_preset_cursor(direction)
            return
        if self._surface.shift_held():
            self._surface.grid_pan(0, direction)
            return
        self._surface.repertoire.move(direction)

    def _on_click(self, value):
        if value != 127:
            return
        if self._surface.preset_track is not None:
            self._surface.choose_preset_at_cursor()
            return
        self._surface.repertoire.play_cursor()

    def disconnect(self):
        self.turn.remove_value_listener(self._on_turn)
        self.click.remove_value_listener(self._on_click)


# =============================================================================
# Cycle
# =============================================================================

class _Cycle(object):
    """
    Rebuilds the browser index and rewrites the preset file from the
    Collection.

    Both are read once at startup, so without this button a newly saved preset,
    or a preset you have just tagged, needs Live restarted before it can be
    used.

    The rebuild takes real time on a large library, so it is queued and runs on
    the main thread rather than inside the MIDI callback.
    """

    def __init__(self, surface):
        self._surface = surface
        self._clear_at = None
        self.button = ButtonElement(True, MIDI_CC_TYPE, scr.MAIN_CHANNEL, scr.CYCLE_CC)
        self.button.add_value_listener(self._on_button)
        self._surface.send(scr.led_packet(scr.CYCLE_LED, cfg.CYCLE_IDLE))

    def _on_button(self, value):
        if value != 127:
            return
        self._surface.send(scr.led_packet(scr.CYCLE_LED, cfg.CYCLE_BUSY))
        self._surface.send(scr.popup_packet("Rebuilding", "Presets"))
        self._surface.enqueue(self._rebuild)

    def _rebuild(self):
        count = self._surface.rebuild_presets()
        self._surface.send(scr.popup_packet("%d presets" % count, "Index"))
        self._surface.send(scr.led_packet(scr.CYCLE_LED, cfg.CYCLE_DONE))
        self._clear_at = time.time() + cfg.CYCLE_DONE_SECONDS

    def poll(self):
        if self._clear_at is None or time.time() < self._clear_at:
            return
        self._clear_at = None
        self._surface.send(scr.led_packet(scr.CYCLE_LED, cfg.CYCLE_IDLE))

    def disconnect(self):
        self.button.remove_value_listener(self._on_button)


# =============================================================================
# Record
# =============================================================================

class _Record(object):
    """
    CC22, with one of two jobs depending on SESSION_GRID.

    Grid off: Record is Record - it switches Live's Arrangement Record
    (song().record_mode) on and off, and the LED follows Live, so it is right
    however recording was started or stopped.

    Grid on: a shift key for the clip-launch grid. Hold Record and press a pad
    to delete that slot's clip instead of launching it (see
    KeyLabLive.pad_pressed), or hold Record and use Back/Forward or the jog
    wheel to pan the grid's window across tracks and scenes instead of their
    normal roles (see KeyLabLive.shift_held, _Transport, _Wheel).

    Deleting a playing clip works exactly as readily as a stopped one; Undo is
    the safety net, not a confirmation dialog this keyboard has no room for.
    """

    def __init__(self, surface):
        self._surface = surface
        self.held = False
        self._shift = surface.session is not None
        self._listening = False
        self.button = ButtonElement(True, MIDI_CC_TYPE, scr.MAIN_CHANNEL, scr.REC_CC)
        self.button.add_value_listener(self._on_button)
        if self._shift:
            self._surface.send(scr.led_packet(scr.REC_LED, cfg.REC_IDLE))
            return
        try:
            self._surface.song().add_record_mode_listener(self._draw_record)
            self._listening = True
        except (AttributeError, RuntimeError) as exc:
            self._surface.log_message(
                "KeyLabLive: no record listener (%r) - the Record LED will "
                "only update when the button is pressed" % (exc,))
        self._draw_record()

    def _on_button(self, value):
        if self._shift:
            self.held = value == 127
            self._surface.send(scr.led_packet(
                scr.REC_LED, cfg.REC_SHIFT if self.held else cfg.REC_IDLE))
            return
        if value != 127:
            return
        try:
            song = self._surface.song()
            song.record_mode = not song.record_mode
        except (AttributeError, RuntimeError) as exc:
            self._surface.log_message("KeyLabLive: record failed (%r)" % (exc,))
        if not self._listening:
            self._draw_record()

    def _draw_record(self):
        try:
            recording = bool(self._surface.song().record_mode)
        except (AttributeError, RuntimeError):
            recording = False
        self._surface.send(scr.led_packet(
            scr.REC_LED, cfg.REC_ON if recording else cfg.REC_OFF))

    def disconnect(self):
        self.button.remove_value_listener(self._on_button)
        if self._listening:
            try:
                self._surface.song().remove_record_mode_listener(self._draw_record)
            except (AttributeError, RuntimeError):
                pass


# =============================================================================
# Save / Quantize / Undo / Redo
# =============================================================================

class _HistoryButtons(object):
    """
    CC 41-44, read out of Arturia's own compiled script - see the
    SAVE_CC/QUANTIZE_CC/UNDO_CC/REDO_CC note in keylab_screen.py. In that
    script "Save" is bound to the role capture_midi, not a generic save, and
    that is what it does here too.

    Save lights up from song().can_capture_midi, which Live lets a script
    listen to. Undo and Redo light up from song().can_undo / can_redo, which
    it does not, so those two are polled in update_display. Each listener is
    still asked for first, so a Live that offers one uses it.

    Quantize quantizes whatever clip is open in Live's detail view to 1/16,
    which is what Live's own Edit > Quantize menu command acts on.
    """

    def __init__(self, surface):
        self._surface = surface
        self.save = self._button(scr.SAVE_CC, self._on_save)
        self.quantize = self._button(scr.QUANTIZE_CC, self._on_quantize)
        self.undo = self._button(scr.UNDO_CC, self._on_undo)
        self.redo = self._button(scr.REDO_CC, self._on_redo)

        self._capture_listener = False
        self._undo_listener = False
        self._redo_listener = False

        # Last colour actually sent, per LED - so the polling below does not
        # resend an unchanged packet every 100ms and flood the MIDI output
        # (visible as a fast-flickering activity light).
        self._capture_colour = None
        self._undo_colour = None
        self._redo_colour = None

        song = self._surface.song()
        try:
            song.add_can_capture_midi_listener(self._refresh_capture)
            self._capture_listener = True
        except (AttributeError, RuntimeError):
            pass
        try:
            song.add_can_undo_listener(self._refresh_undo)
            self._undo_listener = True
        except (AttributeError, RuntimeError):
            pass
        try:
            song.add_can_redo_listener(self._refresh_redo)
            self._redo_listener = True
        except (AttributeError, RuntimeError):
            pass

        self._refresh_capture()
        self._refresh_undo()
        self._refresh_redo()

    def _button(self, cc, callback):
        element = ButtonElement(True, MIDI_CC_TYPE, scr.MAIN_CHANNEL, cc)
        element.add_value_listener(callback)
        return element

    # -- Save / Capture MIDI ---------------------------------------------------

    def _on_save(self, value):
        if value != 127:
            return
        try:
            self._surface.song().capture_midi()
        except (AttributeError, RuntimeError) as exc:
            self._surface.log_message("KeyLabLive: capture_midi failed (%r)" % (exc,))

    def _refresh_capture(self):
        try:
            can_capture = bool(self._surface.song().can_capture_midi)
        except (AttributeError, RuntimeError):
            can_capture = False
        colour = cfg.SAVE_READY if can_capture else cfg.SAVE_IDLE
        if colour == self._capture_colour:
            return
        self._capture_colour = colour
        self._surface.send(scr.led_packet(scr.SAVE_LED, colour))

    # -- Undo --------------------------------------------------------------

    def _on_undo(self, value):
        if value != 127:
            return
        try:
            self._surface.song().undo()
        except (AttributeError, RuntimeError) as exc:
            self._surface.log_message("KeyLabLive: undo failed (%r)" % (exc,))

    def _refresh_undo(self):
        try:
            can_undo = bool(self._surface.song().can_undo)
        except (AttributeError, RuntimeError):
            can_undo = False
        colour = cfg.UNDO_READY if can_undo else cfg.UNDO_IDLE
        if colour == self._undo_colour:
            return
        self._undo_colour = colour
        self._surface.send(scr.led_packet(scr.UNDO_LED, colour))

    # -- Redo --------------------------------------------------------------

    def _on_redo(self, value):
        if value != 127:
            return
        try:
            self._surface.song().redo()
        except (AttributeError, RuntimeError) as exc:
            self._surface.log_message("KeyLabLive: redo failed (%r)" % (exc,))

    def _refresh_redo(self):
        try:
            can_redo = bool(self._surface.song().can_redo)
        except (AttributeError, RuntimeError):
            can_redo = False
        colour = cfg.REDO_READY if can_redo else cfg.REDO_IDLE
        if colour == self._redo_colour:
            return
        self._redo_colour = colour
        self._surface.send(scr.led_packet(scr.REDO_LED, colour))

    # -- Quantize ----------------------------------------------------------
    #
    # clip.quantize() takes members of Live.Song.RecordingQuantization (the
    # note-level grid - 1/4 down to 1/32), NOT Live.Song.Quantization (that
    # one is launch/bar-level only), and it wants the enum member itself, not
    # an index. Live has spelled the member inconsistently across versions -
    # "sixtenth" as well as "sixteenth" - so both are tried.
    _QUANTIZE_GRID_NAMES = ("rec_q_sixtenth", "rec_q_sixteenth")

    def _on_quantize(self, value):
        self._surface.send(scr.led_packet(
            scr.QUANTIZE_LED, cfg.QUANTIZE_PRESSED if value == 127 else cfg.QUANTIZE_IDLE))
        if value != 127:
            return
        try:
            clip = self._surface.song().view.detail_clip
        except (AttributeError, RuntimeError) as exc:
            self._surface.log_message("KeyLabLive: quantize failed (%r)" % (exc,))
            return
        if clip is None:
            return
        import Live
        grid = None
        for name in self._QUANTIZE_GRID_NAMES:
            grid = getattr(Live.Song.RecordingQuantization, name, None)
            if grid is not None:
                break
        if grid is None:
            self._surface.log_message(
                "KeyLabLive: quantize failed - Live.Song.RecordingQuantization "
                "has neither %s" % (" nor ".join(self._QUANTIZE_GRID_NAMES),))
            return
        try:
            clip.quantize(grid, 1.0)
        except (AttributeError, RuntimeError) as exc:
            self._surface.log_message("KeyLabLive: quantize failed (%r)" % (exc,))

    # -- fallback for hosts that refuse the can_undo / can_redo listener ------

    def poll(self):
        if not self._undo_listener:
            self._refresh_undo()
        if not self._redo_listener:
            self._refresh_redo()
        if not self._capture_listener:
            self._refresh_capture()

    def disconnect(self):
        for element, callback in (
            (self.save, self._on_save), (self.quantize, self._on_quantize),
            (self.undo, self._on_undo), (self.redo, self._on_redo),
        ):
            element.remove_value_listener(callback)
        song = self._surface.song()
        for listening, remove, callback in (
            (self._capture_listener, "remove_can_capture_midi_listener", self._refresh_capture),
            (self._undo_listener, "remove_can_undo_listener", self._refresh_undo),
            (self._redo_listener, "remove_can_redo_listener", self._refresh_redo),
        ):
            if listening:
                try:
                    getattr(song, remove)(callback)
                except (AttributeError, RuntimeError):
                    pass


# =============================================================================
# The surface
# =============================================================================

class KeyLabLive(ControlSurface):

    def __init__(self, c_instance):
        ControlSurface.__init__(self, c_instance)
        self.tracks = []
        self.preset_track = None       # the track whose list is open, or None
        self.entries = []              # manual list + tagged list, in that order
        self.chapters = []             # chapter names in order; [] = no chapters
        self._manual = []              # the hand-written list, never written to
        self._remembered = []          # untagged presets, kept for their chapters
        self._rows = {}                # chapter -> [index into self.entries]
        self._chapter = None           # the chapter on screen, or None
        self._chapter_cursor = {}      # chapter -> where its cursor was left
        self._faders = []
        self._pads = []
        self._transport = None
        self._wheel = None
        self._cycle = None
        self._chapter_buttons = None
        self._history = None
        self._record = None
        self.session = None
        self.repertoire = None
        self._browser = None
        self._queue = queue.Queue()
        self._nav_colour = None
        self._chapter_colour = None
        self._apply_at = None
        self._cursor = 0
        self._top = 0
        self._playing_listener = False
        self._tracks_listener = False

        with self.component_guard():
            self._setup()

    # -- helpers used by every component -------------------------------------

    def send(self, packet):
        self._send_midi(tuple(packet))

    def enqueue(self, callback):
        """
        Hand work from a background thread to the main thread. Anything that
        touches Live's model must run there; this queue is drained in
        update_display.
        """
        self._queue.put(callback)

    def browser(self):
        if self._browser is None:
            root = cfg.PRESET_ROOT_FORMAT % cfg.PRESET_COLLECTION
            self._browser = PresetBrowser(
                self, [root], getattr(cfg, "PRESET_SEARCH_ROOTS", ()))
            self._browser.set_manual_names(
                [preset for preset, _chapter in self._manual])
        return self._browser

    def _file(self, name):
        return os.path.join(os.path.dirname(os.path.realpath(__file__)), name)

    # -- setup ---------------------------------------------------------------

    def _build_tracks(self):
        """
        (Re)builds self.tracks and self._faders from the set's current track
        list - up to MAX_TRACKS, capped at however many screen buttons this
        keyboard has. Called once at startup and again, from
        _on_tracks_changed, whenever a track is added or removed, so the
        screen never shows a track that is no longer there, or misses one
        that just arrived.

        Returns (tracks, count) so the caller can log how many of the set's
        tracks actually got a screen button.
        """
        for group in (self.tracks, self._faders):
            for item in group:
                item.disconnect()
        self.tracks = []
        self._faders = []

        try:
            tracks = list(self.song().tracks)
        except (AttributeError, RuntimeError):
            tracks = []

        count = min(len(tracks), cfg.MAX_TRACKS, len(scr.SCREEN_BUTTONS))

        for i in range(count):
            self.tracks.append(_Track(self, i, tracks[i]))

        if cfg.FADERS_CONTROL_VOLUME:
            for i in range(min(count, len(scr.FADER_VALUE_CCS))):
                self._faders.append(_Fader(self, i, tracks[i]))

        # A button that had a track before this rebuild and does not any more
        # (a track was removed) would otherwise just keep showing it forever -
        # nothing else repaints a footer nobody owns. Blank every button past
        # the new count on every rebuild; cheap, and always correct.
        for i in range(count, len(scr.SCREEN_BUTTONS)):
            footer_id, _cc = scr.SCREEN_BUTTONS[i + 1]
            self.send(scr.footer_packet(footer_id, False, "", cfg.FOOTER_UNARMED))

        return tracks, count

    def _on_tracks_changed(self):
        """
        A track was added or removed somewhere in the set. Rebuilds the screen
        buttons, the faders, and the clip-launch grid's window against the new
        track list, so none of them need Live restarted to catch up.
        """
        with self.component_guard():
            self._build_tracks()
        self.request_rebuild_midi_map()
        for track in self.tracks:
            track.draw()
        if self.session is not None:
            self.session._rebuild()
            self.session.draw()

    def update_session_highlight(self, track_offset, scene_offset, width, height):
        """
        Live's own highlight rectangle in Session View, drawn around whichever
        clip slots the grid currently addresses - see Session._rebuild.
        Normally wired automatically by _Framework.SessionComponent's
        set_highlighting_callback; our hand-rolled grid asks for it directly
        instead. Position and size only - Live chooses the colour (your
        theme), not this script.
        """
        try:
            self._set_session_highlight(
                track_offset, scene_offset, width, height, False)
        except (AttributeError, RuntimeError):
            pass

    def _setup(self):
        song = self.song()

        if not song.tracks:
            self.log_message("KeyLabLive: the set has no tracks - stopping")
            return

        tracks, count = self._build_tracks()
        if len(tracks) > count:
            self.log_message(
                "KeyLabLive: the set has %d track(s) - using the first %d "
                "(MAX_TRACKS in keylab_config.py, capped at %d screen buttons)"
                % (len(tracks), count, len(scr.SCREEN_BUTTONS)))

        try:
            song.add_tracks_listener(self._on_tracks_changed)
            self._tracks_listener = True
        except (AttributeError, RuntimeError) as exc:
            self.log_message(
                "KeyLabLive: no tracks listener (%r) - added/removed tracks "
                "will need Live restarted to show up" % (exc,))

        for i in range(scr.PAD_COUNT):
            self._pads.append(_Pad(self, i))

        # Built after self.tracks, which it reads from directly - see
        # keylab_session.py. The pads above are claimed either way: left
        # unclaimed, Live can pass them on as notes to whatever is armed.
        if cfg.SESSION_GRID:
            self.session = Session(self)

        self._transport = _Transport(self)
        self._wheel = _Wheel(self)
        self._cycle = _Cycle(self)
        self._chapter_buttons = _Chapters(self)
        self._history = _HistoryButtons(self)
        self._record = _Record(self)
        self.repertoire = Repertoire(self)

        # Play and Stop show whether the transport is running, so they have to
        # hear about it from Live and not only from the buttons on this
        # keyboard: playback can just as well be started from Live's own
        # transport, or from anything else driving it.
        try:
            song.add_is_playing_listener(self._on_is_playing)
            self._playing_listener = True
        except (AttributeError, RuntimeError) as exc:
            self.log_message(
                "KeyLabLive: no transport listener (%r) - Play and Stop will "
                "only update when the list does" % (exc,))

        self.send(scr.DAW_CONNECT)
        for track in self.tracks:
            track.draw()
        if self.session is not None:
            self.session.draw()
        else:
            for i in range(scr.PAD_COUNT):
                self.send(scr.pad_led_packet(i, cfg.PAD_OFF))
        self.repertoire.draw()
        self.update_nav_leds()
        self.update_chapter_leds()
        self.update_play_led()

        # The preset file is read now; the browser index is built a moment
        # later - see update_display. Live may still be scanning its library
        # while a set is loading.
        self.load_presets()

    def _on_is_playing(self):
        self.update_play_led()

    # -- the preset file -----------------------------------------------------

    def load_presets(self):
        """
        Read both lists and join them into the one list on screen: the manual
        file first, then the tagged one.

        A preset in both files is shown once, from the manual file - that file
        is the one a person edited on purpose, so it decides the chapter and
        the place. Chapters are matched by name across the two, so the same
        chapter name in both is one chapter.

        A preset with no chapter of its own takes the one named after its file,
        so the title on screen says where it came from. That only happens if
        something, somewhere, has a chapter: with none anywhere the list stays
        flat and chapters stay switched off.
        """
        self._manual = load_manual_file(self._file(cfg.PRESET_FILE_MANUAL))
        tagged, self._remembered = load_preset_file(self._file(cfg.PRESET_FILE))

        if any(chapter for _preset, chapter in self._manual + tagged):
            self._manual = [(preset, chapter or cfg.CHAPTER_UNNAMED)
                            for preset, chapter in self._manual]
            tagged = [(preset, chapter or cfg.CHAPTER_TAGGED)
                      for preset, chapter in tagged]

        seen = set(preset_key(preset) for preset, _chapter in self._manual)
        self.entries = list(self._manual)
        for preset, chapter in tagged:
            key = preset_key(preset)
            if key not in seen:
                seen.add(key)
                self.entries.append((preset, chapter))

        self._index_chapters()
        if self._browser is not None:
            self._browser.set_manual_names(
                [preset for preset, _chapter in self._manual])

    def _index_chapters(self):
        """
        Sort the list into chapters once, so that moving the cursor does not
        have to filter it on every tick.

        With no chapters in the file there is a single unnamed bucket holding
        everything.
        """
        self.chapters = chapters_of(self.entries)
        self._rows = {}
        if not self.chapters:
            self._rows[None] = list(range(len(self.entries)))
            return
        for name in self.chapters:
            self._rows[name] = []
        for i, (_preset, chapter) in enumerate(self.entries):
            self._rows[chapter].append(i)

    def _rows_now(self):
        return self._rows.get(self._chapter, [])

    def rebuild_presets(self):
        """
        Cycle's work, in this order - it matters:
          1. read the manual file, so the index knows which names to look for
          2. rebuild the browser index, so newly saved presets exist (needs 1)
          3. rewrite presets.txt from the Collection (needs step 2)
          4. read both files back, so the list shows the result
        """
        browser = self.browser()
        browser.set_manual_names([
            preset for preset, _chapter
            in load_manual_file(self._file(cfg.PRESET_FILE_MANUAL))])
        count = browser.reload()

        if cfg.PRESET_FILES_AUTO:
            names = browser.list_items(
                cfg.PRESET_ROOT_FORMAT % cfg.PRESET_COLLECTION)
            if names:
                path = self._file(cfg.PRESET_FILE)
                existing, remembered = load_preset_file(path)
                merged, still = merge_preset_entries(existing, remembered, names)
                write_preset_file(path, merged, still, cfg.PRESET_COLLECTION)
            else:
                # Leaving the file alone is deliberate. A Collection that comes
                # back empty is far more often a typo or a library still being
                # scanned than a list you meant to empty, and rewriting it
                # would throw away every chapter you have written.
                self.log_message(
                    "KeyLabLive: Collection '%s' is empty or missing - leaving "
                    "%s alone" % (cfg.PRESET_COLLECTION, cfg.PRESET_FILE))

        self.load_presets()
        for track in self.tracks:
            self._seed_label(track)
        return count

    def _seed_label(self, track):
        """
        Show the preset that is actually on the track, rather than the track
        name, by matching the instrument's name against the list.

        This is also how a track gets its chapter back after Live restarts:
        nothing is stored in the set, the chapter simply follows whichever
        preset is sitting on the track.

        A loaded preset takes its own name, so this usually works. It is a name
        coincidence rather than a fact - the device may have been renamed - so
        nothing depends on it.
        """
        browser = self.browser()
        device = browser.find_instrument(track.track)
        if device is None:
            return
        try:
            device_name = device.name
        except (AttributeError, RuntimeError):
            return
        for i, (preset, chapter) in enumerate(track.entries):
            if browser.name_matches(preset, device_name):
                track.chosen = i
                track.chapter = chapter if self.chapters else None
                track.set_label(preset)
                return

    # -- the preset list -----------------------------------------------------

    def open_preset_list(self, track):
        """
        Open the list for one track - including while another track's list is
        already open, which is simply a hold on a different button. Nothing has
        to be closed first, and the title changes to say whose list this now
        is.
        """
        if not track.entries:
            self.send(scr.popup_packet("No presets", track.label()))
            self.log_message(
                "KeyLabLive: the preset list is empty - is anything tagged with "
                "the '%s' Collection, and has Cycle been pressed?"
                % cfg.PRESET_COLLECTION)
            return

        # Moving the list from one track to another: remember where the cursor
        # was left, as closing would have done, and drop any pending apply from
        # Back/Forward so it cannot land on the new track.
        previous = self.preset_track
        if previous is not None and previous is not track:
            if self._chapter in self._rows:
                self._chapter_cursor[self._chapter] = self._cursor
        self._apply_at = None

        # Set first: draw() reads it to decide whether this button is the one
        # holding the list, and arming below fires the arm listener, which
        # draws.
        self.preset_track = track
        if previous is not None and previous is not track:
            previous.draw()
        track.draw()
        self.repertoire.set_open(False)
        try:
            track.track.arm = True
        except (AttributeError, RuntimeError):
            pass

        self._chapter = self._opening_chapter(track)
        rows = self._rows_now()
        self._cursor = self._opening_cursor(track, rows)
        self._top = scr.list_top(self._cursor, len(rows))

        self.send(scr.popup_packet("Preset?", track.label()))
        self._draw_preset_list()
        self.update_play_led()
        self.update_nav_leds()
        self.update_chapter_leds()
        if self._chapter_buttons is not None:
            self._chapter_buttons.pulse()

    def _opening_chapter(self, track):
        """
        Where the list opens: where this track was last looking, else the
        chapter of whatever preset is on it, else the first chapter.
        """
        if not self.chapters:
            return None
        if track.chapter in self._rows:
            return track.chapter
        if track.chosen is not None and 0 <= track.chosen < len(self.entries):
            chapter = self.entries[track.chosen][1]
            if chapter in self._rows:
                return chapter
        return self.chapters[0]

    def _opening_cursor(self, track, rows):
        """On the preset this track is playing if it is in view, else where the
        cursor was left in this chapter."""
        if not rows:
            return 0
        if track.chosen in rows:
            return rows.index(track.chosen)
        remembered = self._chapter_cursor.get(self._chapter, 0)
        return max(0, min(remembered, len(rows) - 1))

    def change_chapter(self, direction):
        """Tap and Metro. Wraps unless CHAPTER_WRAP says otherwise."""
        if not self.chapters or self.preset_track is None:
            return
        try:
            at = self.chapters.index(self._chapter)
        except ValueError:
            at = 0
        self._chapter_cursor[self._chapter] = self._cursor

        target = at + direction
        if cfg.CHAPTER_WRAP:
            target %= len(self.chapters)
        elif not (0 <= target < len(self.chapters)):
            return

        self._chapter = self.chapters[target]
        rows = self._rows_now()
        self._cursor = self._opening_cursor(self.preset_track, rows)
        self._top = scr.list_top(self._cursor, len(rows))
        # A chapter change must not load anything - it is navigation, not a
        # choice. Any pending apply from Back/Forward is dropped.
        self._apply_at = None
        self._draw_preset_list()

    def chapters_active(self):
        return bool(self.chapters) and self.preset_track is not None

    def _chapter_title(self):
        """
        The list's title, and the only place on screen that says the chapter
        buttons exist. "< Racks 2/4 >" - the arrows point at Tap and Metro,
        which sit at the two ends of the transport row, and the count says
        whether pressing one is worth it.

        The title is not truncated by the screen protocol the way the footer
        buttons are, so there is room. ASCII only: "<" and ">" survive, the
        prettier arrows would be dropped silently.
        """
        if not self.chapters:
            return self.preset_track.label()
        # The fallback only bites if both chapter names in keylab_config.py
        # have been set to nothing, which leaves a genuinely unnamed chapter.
        name = self._chapter or "Other"
        if len(self.chapters) < 2 or not cfg.CHAPTER_TITLE_ARROWS:
            return name
        try:
            position = self.chapters.index(self._chapter) + 1
        except ValueError:
            return name
        return "< %s %d/%d >" % (name, position, len(self.chapters))

    def _draw_preset_list(self):
        track = self.preset_track
        if track is None:
            return
        rows = self._rows_now()
        names = [self.entries[i][0] for i in rows]
        self.send(scr.list_title_packet(self._chapter_title(), len(names)))
        window = names[self._top:self._top + scr.LIST_VISIBLE_LINES]
        for offset, name in enumerate(window):
            self.send(scr.list_item_packet(
                scr.LIST_APPEND, name, self._top + offset))
        self.send(scr.list_cursor_packet(self._cursor))

    def move_preset_cursor(self, delta):
        """
        The window follows the cursor on every move (scr.list_top), one line
        at a time, so the lines on screen are always the ones the firmware
        frames its cursor box by - see scr.list_cursor_packet.
        """
        track = self.preset_track
        rows = self._rows_now()
        if track is None or not rows:
            return
        length = len(rows)
        self._cursor = max(0, min(self._cursor + delta, length - 1))

        old_top = self._top
        self._top = scr.list_top(self._cursor, length)

        if self._top == old_top - 1:
            self.send(scr.list_item_packet(
                scr.LIST_PREPEND, self.entries[rows[self._top]][0],
                self._top))
        elif self._top == old_top + 1:
            bottom = self._top + scr.LIST_VISIBLE_LINES - 1
            self.send(scr.list_item_packet(
                scr.LIST_APPEND, self.entries[rows[bottom]][0], bottom))
        elif self._top != old_top:
            # Jumped by more than one line (should not happen with the single
            # steps the wheel and Back/Forward send) - redraw the window
            # whole rather than try to patch it one line at a time.
            self._draw_preset_list()
            return

        self.send(scr.list_cursor_packet(self._cursor))

    def arm_delayed_apply(self):
        self._apply_at = time.time() + cfg.NAV_SELECT_DELAY

    def _poll_delayed_apply(self):
        if self._apply_at is None or time.time() < self._apply_at:
            return
        self._apply_at = None
        self.apply_preset_at_cursor(keep_open=True)

    def choose_preset_at_cursor(self):
        self.apply_preset_at_cursor(keep_open=False)

    def apply_preset_at_cursor(self, keep_open):
        track = self.preset_track
        rows = self._rows_now()
        if track is None or not rows:
            return
        self._apply_at = None
        self.apply_preset(track, rows[self._cursor])
        if not keep_open:
            self.close_preset_list()

    def pad_pressed(self, pad_index):
        """
        Pads 1-12 are the clip-launch grid, open preset list or not - or
        nothing at all with SESSION_GRID off. Picking a preset has no pad
        path, only the jog wheel, Play and Back/Forward. Record held deletes the slot instead of launching
        it - see keylab_session.py and _Record.
        """
        if self.session is None:
            return
        if self._record is not None and self._record.held:
            self.session.delete_pad(pad_index)
        else:
            self.session.pad_pressed(pad_index)

    def shift_held(self):
        """Whether Record is currently held - the clip-launch grid's shift
        key, consulted by _Transport and _Wheel to pan the grid's window
        instead of their normal roles. See _Record."""
        return self._record is not None and self._record.held

    def grid_pan(self, d_tracks, d_scenes):
        if self.session is not None:
            self.session.pan(d_tracks, d_scenes)

    def close_preset_list(self):
        if self._chapter in self._rows:
            self._chapter_cursor[self._chapter] = self._cursor
        track = self.preset_track
        self.preset_track = None
        self._apply_at = None
        # Cleared first, so draw() puts the button back to the track's own
        # colour rather than drawing the yellow again.
        if track is not None:
            track.draw()
        self.repertoire.draw()
        self.update_play_led()
        self.update_nav_leds()
        self.update_chapter_leds()

    # -- applying a preset ---------------------------------------------------

    def apply_preset(self, track, index):
        if not (0 <= index < len(track.entries)):
            return
        preset, chapter = track.entries[index]

        browser = self.browser()
        device = browser.find_instrument(track.track)
        if device is None:
            self._fail(preset, "track %d has no instrument device"
                       % (track.index + 1))
            return

        ok, detail = browser.load(track.track, device, preset)
        if not ok:
            self._fail(preset, detail)
            return

        track.chosen = index
        track.chapter = chapter if self.chapters else None
        track.set_label(preset)
        self.send(scr.popup_packet(short_label(preset), track.label()))

    def _fail(self, preset, reason):
        # On the screen as well as in the log: without it a failed choice looks
        # exactly like nothing happening, and there is no way to tell the two
        # apart while playing.
        self.send(scr.popup_packet("Failed", short_label(preset)))
        self.log_message("KeyLabLive: '%s' failed - %s" % (preset, reason))

    # -- LEDs ----------------------------------------------------------------

    def nav_colours(self):
        """(idle, pressed) for Back/Forward - yellow when they pick presets."""
        if self.preset_track is not None:
            return cfg.NAV_SELECT_IDLE, cfg.NAV_SELECT_PRESSED
        return cfg.NAV_IDLE, cfg.NAV_PRESSED

    def update_nav_leds(self):
        """
        Only sends when the colour actually changes. update_play_led runs on
        every cursor move, and two packets per wheel tick is needless traffic
        on a button that is standing still.
        """
        idle = self.nav_colours()[0]
        if idle == self._nav_colour:
            return
        self._nav_colour = idle
        self.send(scr.led_packet(scr.BACK_LED, idle))
        self.send(scr.led_packet(scr.FORWARD_LED, idle))

    def update_chapter_leds(self):
        """
        Tap and Metro: chapter navigation while a list is open, their own
        native roles (Tap Tempo / metronome) otherwise - see _Chapters.

        Only the "list is open" half is drawn here, with the same
        "only on change" rule as the nav LEDs. The native half has its own
        state (the metronome's on/off) that does not fit that single-colour
        cache, so it is handed to _Chapters.refresh_native() instead.
        """
        if self.preset_track is None:
            self._chapter_colour = None
            if self._chapter_buttons is not None:
                self._chapter_buttons.refresh_native()
            return
        colour = cfg.CHAPTER_IDLE if self.chapters_active() else cfg.CHAPTER_OFF
        if colour == self._chapter_colour:
            return
        self._chapter_colour = colour
        self.send(scr.led_packet(scr.TAP_LED, colour))
        self.send(scr.led_packet(scr.METRO_LED, colour))

    def refresh_chapter_leds(self):
        """
        As above, but forced. The opening pulse leaves the LEDs somewhere this
        surface did not put them, so the "only on change" test would skip the
        write that puts them back.
        """
        self._chapter_colour = None
        self.update_chapter_leds()

    def update_play_led(self):
        """
        Play and Stop, both from the same truth: whether the transport is
        running. Called from the is_playing listener, so the pair follows Live
        however playback was started or stopped - this keyboard, Live's own
        transport, or anything else driving it.
        """
        try:
            playing = bool(self.song().is_playing)
        except (AttributeError, RuntimeError):
            return
        if self.preset_track is not None:
            colour = cfg.PLAY_PRESET
        elif playing:
            colour = cfg.PLAY_RUNNING
        elif self.repertoire is None or self.repertoire.cursor_has_locator():
            colour = cfg.PLAY_READY
        else:
            colour = cfg.PLAY_NO_SONG
        self.send(scr.led_packet(scr.PLAY_LED, colour))
        self.send(scr.led_packet(
            scr.STOP_LED, cfg.STOP_RUNNING if playing else cfg.STOP_IDLE))
        self.update_nav_leds()

    # -- Live's callbacks ----------------------------------------------------

    def update_display(self):
        ControlSurface.update_display(self)
        with self.component_guard():
            while True:
                try:
                    action = self._queue.get_nowait()
                except queue.Empty:
                    break
                action()
            if self.repertoire is not None:
                self.repertoire.poll()
            if self._transport is not None:
                self._transport.poll()
            if self._cycle is not None:
                self._cycle.poll()
            if self._chapter_buttons is not None:
                self._chapter_buttons.poll()
            if self._history is not None:
                self._history.poll()
            self._poll_delayed_apply()
            self._poll_first_index()

    _index_tries = 8

    def _poll_first_index(self):
        """
        Build the browser index shortly AFTER startup rather than during it.
        Live is not necessarily finished scanning its library while a set is
        still loading, and an index built too early comes back empty.
        """
        if self._index_tries <= 0:
            return
        self._index_tries -= 1
        browser = self.browser()
        browser.warm()
        if browser.index_size() > 0:
            self._index_tries = 0
            for track in self.tracks:
                self._seed_label(track)

    def disconnect(self):
        if self._playing_listener:
            try:
                self.song().remove_is_playing_listener(self._on_is_playing)
            except (AttributeError, RuntimeError):
                pass
            self._playing_listener = False
        if self._tracks_listener:
            try:
                self.song().remove_tracks_listener(self._on_tracks_changed)
            except (AttributeError, RuntimeError):
                pass
            self._tracks_listener = False
        if self._browser is not None:
            self._browser.shutdown()
        if self.repertoire is not None:
            self.repertoire.disconnect()
        for group in (self.tracks, self._faders, self._pads):
            for item in group:
                item.disconnect()
        for single in (self._transport, self._wheel, self._cycle,
                       self._chapter_buttons, self._history, self._record,
                       self.session):
            if single is not None:
                single.disconnect()
        try:
            self.send(scr.DAW_DISCONNECT)
        except Exception:
            pass
        ControlSurface.disconnect(self)
