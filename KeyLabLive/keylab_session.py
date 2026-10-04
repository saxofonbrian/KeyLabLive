# =============================================================================
# KeyLabLive - the clip-launch grid
# =============================================================================
#
# Only built when SESSION_GRID is switched on in keylab_config.py.
#
# Pads 1-12 always launch clips - including while a preset list is open on
# screen; picking a preset from the list has no pad path, only the
# jog wheel, Play and Back/Forward. _Pad's own value listener always calls
# KeyLabLive.pad_pressed(index), which forwards straight here (or to delete,
# with Record held) - see pad_pressed in keylab_live.py. Session itself owns
# no MIDI listeners of its own, only clip-slot listeners for LED feedback.
#
# THE WINDOW IS PANNABLE. The grid is a fixed 4x3 window (4 tracks, 3 scenes)
# that can sit anywhere in the set - see pan(). Record-shift + Back/Forward
# moves it across tracks, Record-shift + the jog wheel moves it across
# scenes, one step at a time; see _Transport and _Wheel in keylab_live.py.
# The window starts at track 0 / scene 0, where pads 1-4 sit on the same four
# tracks as screen buttons 1-4 - panning away from the start breaks
# that alignment, same as on any Launchpad-style controller.
#
# Bounds are read live from song().tracks / song().scenes on every pan, never
# cached - the same approach Arturia's and Novation's own scripts take, and
# it means the window is never stale if tracks or scenes are added or removed
# mid-session. A track add/remove also rebuilds the window on its own, via
# KeyLabLive._on_tracks_changed - not just on the next pan.
#
# Live's own Session View highlight rectangle is kept in step with the
# window on every rebuild - see update_session_highlight in keylab_live.py.
#
# Grid layout by pad number, relative to the window's own first track and
# first scene. Pads 1-4 are scene 1.
#
#   Pad 1   Pad 2   Pad 3   Pad 4       scene 1
#   Pad 5   Pad 6   Pad 7   Pad 8       scene 2
#   Pad 9   Pad 10  Pad 11  Pad 12      scene 3
#   Track 1 Track 2 Track 3 Track 4
#
# To put scene 1 on pads 9-12 instead, reverse _SCENE_ROWS below.
#
# STATE MACHINE
#   Mirrors _Framework.ClipSlotComponent by hand: triggered beats playing
#   beats the clip's own colour (dimmed) beats empty. Reproduced here rather than
#   imported because that component's default LED path assumes an indexed
#   colour palette (it looks values up in a Skin dict) and these pads are
#   true RGB over SysEx.
# =============================================================================

from __future__ import absolute_import, print_function, unicode_literals

from . import keylab_config as cfg
from . import keylab_screen as scr

# Pad index (0-11) -> (track column, scene row) WITHIN THE WINDOW. Row 0 is
# pads 1-4 / the first scene. Add the window's own offset to get the real
# track/scene index - see Session._rebuild.
_TRACK_COLUMNS = (0, 1, 2, 3, 0, 1, 2, 3, 0, 1, 2, 3)
_SCENE_ROWS = (0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2)

_WINDOW_TRACKS = 4
_WINDOW_SCENES = 3


class _ClipSlotPad(object):
    """One pad bound to one (track, scene) clip slot."""

    def __init__(self, session, clip_slot):
        self._session = session
        self._clip_slot = clip_slot
        self._clip = None
        self._slot_listeners = False
        self._clip_listeners = False

        try:
            clip_slot.add_has_clip_listener(self._on_has_clip)
            clip_slot.add_is_triggered_listener(self._on_changed)
            self._slot_listeners = True
        except (AttributeError, RuntimeError):
            pass

        self._bind_clip()

    # -- keeping the clip listeners in step with has_clip ---------------------

    def _bind_clip(self):
        try:
            clip = self._clip_slot.clip if self._clip_slot.has_clip else None
        except (AttributeError, RuntimeError):
            clip = None
        if clip is self._clip:
            return
        self._unbind_clip()
        self._clip = clip
        if clip is None:
            return
        try:
            clip.add_playing_status_listener(self._on_changed)
            clip.add_is_recording_listener(self._on_changed)
            clip.add_color_listener(self._on_changed)
            clip.add_is_triggered_listener(self._on_changed)
            self._clip_listeners = True
        except (AttributeError, RuntimeError):
            self._clip_listeners = False

    def _unbind_clip(self):
        if not self._clip_listeners or self._clip is None:
            self._clip = None
            self._clip_listeners = False
            return
        clip = self._clip
        for remove in ("remove_playing_status_listener", "remove_is_recording_listener",
                       "remove_color_listener", "remove_is_triggered_listener"):
            try:
                getattr(clip, remove)(self._on_changed)
            except Exception:
                # Same reasoning as _unbind_clip's caller, disconnect() above.
                pass
        self._clip = None
        self._clip_listeners = False

    def _on_has_clip(self):
        self._bind_clip()
        self._on_changed()

    def _on_changed(self):
        self._session.draw_one(self)

    # -- press ------------------------------------------------------------

    def fire(self):
        try:
            self._clip_slot.fire()
        except (AttributeError, RuntimeError):
            pass

    def delete(self):
        """Record-shift + pad. Works on a playing clip too - no stopped-only
        guard. Undo is the safety net, not a confirmation step."""
        try:
            self._clip_slot.delete_clip()
        except (AttributeError, RuntimeError):
            pass

    # -- colour -----------------------------------------------------------

    def colour(self):
        slot = self._clip_slot
        try:
            has_clip = bool(slot.has_clip)
            clip = slot.clip if has_clip else None
            target = clip if clip is not None else slot

            if target.is_triggered:
                if clip is not None and clip.will_record_on_start:
                    return cfg.SESSION_TRIGGERED_RECORD
                return cfg.SESSION_TRIGGERED_PLAY

            if clip is not None and clip.is_playing:
                return cfg.SESSION_RECORDING if clip.is_recording else cfg.SESSION_PLAYING

            if clip is not None:
                # Stopped: the clip's own colour, dimmed - see
                # SESSION_STOPPED_DIM in keylab_config.py.
                rgb = scr.rgb_from_color_value(clip.color) or cfg.SESSION_PLAYING
                return tuple(max(1, c // cfg.SESSION_STOPPED_DIM) for c in rgb)

            # Empty slot. Red, not dim, if the track is armed and this slot
            # can actually take a recording - mirrors the fallback
            # _Framework.ClipSlotComponent offers for exactly this case
            # (record_button_value), reproduced directly here instead of
            # through that component's slightly roundabout opt-in.
            if self._record_ready():
                return cfg.SESSION_RECORD_READY
            return cfg.SESSION_EMPTY
        except (AttributeError, RuntimeError):
            return cfg.SESSION_EMPTY

    def _record_ready(self):
        slot = self._clip_slot
        try:
            if not getattr(slot, "has_stop_button", True):
                return False
            track = slot.canonical_parent
            if track is None or not getattr(track, "can_be_armed", False):
                return False
            return bool(track.arm) or bool(getattr(track, "implicit_arm", False))
        except (AttributeError, RuntimeError):
            return False

    def disconnect(self):
        if self._slot_listeners:
            for remove, callback in (
                ("remove_has_clip_listener", self._on_has_clip),
                ("remove_is_triggered_listener", self._on_changed),
            ):
                try:
                    getattr(self._clip_slot, remove)(callback)
                except Exception:
                    # Broad on purpose, same reasoning as _Track.disconnect
                    # in keylab_live.py: a clip slot whose track was just
                    # deleted - the exact moment this can run, from
                    # KeyLabLive._on_tracks_changed - raises
                    # Boost.Python.ArgumentError here, not AttributeError or
                    # RuntimeError.
                    pass
        self._unbind_clip()


class Session(object):
    """
    The clip-launch grid: a 4x3 window of pads that can be panned anywhere
    over the set's tracks and scenes - see pan().

    The window's own position (self._track_offset, self._scene_offset) is
    the only state that survives a pan; everything else (the twelve
    _ClipSlotPad objects and their listeners) is thrown away and rebuilt
    against the new position, because a pad's identity IS which clip slot
    it is bound to. There is no cheaper way to move a bound listener than
    to unbind it and bind a new one.
    """

    def __init__(self, surface):
        self._surface = surface
        self._pads = {}          # pad index -> _ClipSlotPad, only where a slot exists
        self._armed_tracks = []  # tracks we hold an arm listener on, this window
        self._track_offset = 0
        self._scene_offset = 0
        self._rebuild()

    # -- building and rebuilding the window -----------------------------------

    def _rebuild(self):
        """(Re)binds all twelve pads to the clip slots at the window's
        current offset. Called once at startup and again on every pan."""
        for pad in self._pads.values():
            pad.disconnect()
        self._pads = {}
        for track in self._armed_tracks:
            try:
                track.remove_arm_listener(self._on_arm_changed)
            except Exception:
                # Same reasoning as _ClipSlotPad.disconnect above: this runs
                # on every rebuild, including the one triggered by a track
                # just having been deleted.
                pass
        self._armed_tracks = []

        try:
            tracks = list(self._surface.song().tracks)
        except (AttributeError, RuntimeError):
            tracks = []
        try:
            scene_count = len(self._surface.song().scenes)
        except (AttributeError, RuntimeError):
            scene_count = 0

        for index in range(scr.PAD_COUNT):
            col = self._track_offset + _TRACK_COLUMNS[index]
            row = self._scene_offset + _SCENE_ROWS[index]
            if col >= len(tracks) or row >= scene_count:
                continue
            try:
                clip_slot = tracks[col].clip_slots[row]
            except (AttributeError, RuntimeError, IndexError):
                continue
            self._pads[index] = _ClipSlotPad(self, clip_slot)

        # Arming or un-arming a track changes every empty slot on it between
        # "record ready" (red) and dim - one listener per track in the
        # window, not per pad, redraws the whole grid rather than tracking
        # which pads that touches.
        window_tracks = tracks[self._track_offset:self._track_offset + _WINDOW_TRACKS]
        for track in window_tracks:
            try:
                track.add_arm_listener(self._on_arm_changed)
                self._armed_tracks.append(track)
            except (AttributeError, RuntimeError):
                pass

        # Draws Live's own highlight rectangle in Session View around the
        # window - the "red wreath" an Arturia or Framework-SessionComponent
        # script gets for free, which our hand-rolled grid has to ask for
        # itself. See KeyLabLive.update_session_highlight.
        self._surface.update_session_highlight(
            self._track_offset, self._scene_offset, _WINDOW_TRACKS, _WINDOW_SCENES)

    def pan(self, d_tracks, d_scenes):
        """
        Moves the window by the given number of tracks and scenes (one axis
        is always 0 - Back/Forward and the wheel never pan both at once).

        Bounds come from song().tracks / song().scenes read right now, not
        from anything cached, so the clamp is always correct even if the set
        has changed shape since the window last moved. A pan that would not
        actually change the offset (already at an edge) is a no-op - no
        rebuild, no redraw, nothing sent to the keyboard.
        """
        try:
            track_count = len(self._surface.song().tracks)
            scene_count = len(self._surface.song().scenes)
        except (AttributeError, RuntimeError):
            return
        max_track_offset = max(0, track_count - _WINDOW_TRACKS)
        max_scene_offset = max(0, scene_count - _WINDOW_SCENES)
        new_track_offset = max(0, min(self._track_offset + d_tracks, max_track_offset))
        new_scene_offset = max(0, min(self._scene_offset + d_scenes, max_scene_offset))
        if new_track_offset == self._track_offset and new_scene_offset == self._scene_offset:
            return
        self._track_offset = new_track_offset
        self._scene_offset = new_scene_offset
        self._rebuild()
        self.draw()

    def _on_arm_changed(self):
        self.draw()

    def draw(self):
        """All twelve pads. Called at startup, after every pan, and available
        any time the grid as a whole needs repainting."""
        for index in range(scr.PAD_COUNT):
            pad = self._pads.get(index)
            colour = pad.colour() if pad is not None else cfg.SESSION_EMPTY
            self._surface.send(scr.pad_led_packet(index, colour))

    def draw_one(self, clip_pad):
        for index, pad in self._pads.items():
            if pad is clip_pad:
                self._surface.send(scr.pad_led_packet(index, pad.colour()))
                return

    def pad_pressed(self, index):
        pad = self._pads.get(index)
        if pad is not None:
            pad.fire()

    def delete_pad(self, index):
        pad = self._pads.get(index)
        if pad is not None:
            pad.delete()

    def disconnect(self):
        for pad in self._pads.values():
            pad.disconnect()
        for track in self._armed_tracks:
            try:
                track.remove_arm_listener(self._on_arm_changed)
            except (AttributeError, RuntimeError):
                pass
