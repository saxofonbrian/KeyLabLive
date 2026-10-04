# =============================================================================
# KeyLabLive - REPERTOIRE
# =============================================================================
#
# The song list in the middle of the screen. It is simply the locators in your
# Arrangement - there is no separate song file to keep in sync. Add, rename,
# move or delete locators in Live and the list follows.
#
# The jog wheel moves the cursor. Clicking the wheel, or pressing Play, jumps
# to the song at the cursor and starts it. Playback stops automatically a
# little BEFORE the following locator and the cursor moves on, ready for the
# next song.
#
# Why "a little before": stopping exactly on the locator occasionally lets a
# very short piece of the next song through first. See STOP_LEAD_MS in
# keylab_config.py.
# =============================================================================

from __future__ import absolute_import, print_function, unicode_literals

from . import keylab_config as cfg
from .keylab_screen import (
    LIST_APPEND, LIST_PREPEND, LIST_VISIBLE_LINES,
    list_cursor_packet, list_item_packet, list_title_packet, list_top,
)


class Repertoire(object):

    def __init__(self, surface):
        self._surface = surface
        self._cursor = 0
        self._top = 0
        self._stop_at = None      # beat position where playback should stop
        self._open = False
        self._watched = []        # cue points carrying our name/time listeners
        self._watching_song = False
        self._watch()

    # -- following Live --------------------------------------------------------
    #
    # The list is only as current as the last time it was drawn, so Live has to
    # say when a locator is added, deleted, renamed or moved. Two levels: the
    # song reports that the SET of locators changed, each locator reports its
    # own name and position.

    def _watch(self):
        try:
            self._surface.song().add_cue_points_listener(self._on_points_changed)
            self._watching_song = True
        except (AttributeError, RuntimeError) as exc:
            self._surface.log_message(
                "KeyLabLive/repertoire: no locator listener (%r) - the list "
                "will not follow changes made in Live" % (exc,))
        self._watch_points()

    def _watch_points(self):
        self._unwatch_points()
        for point in self.cue_points():
            try:
                point.add_name_listener(self._on_point_changed)
                point.add_time_listener(self._on_point_changed)
            except (AttributeError, RuntimeError):
                continue
            self._watched.append(point)

    def _unwatch_points(self):
        for point in self._watched:
            for remove in ("remove_name_listener", "remove_time_listener"):
                try:
                    getattr(point, remove)(self._on_point_changed)
                except Exception:
                    # Broad on purpose, as for deleted tracks in keylab_live:
                    # a locator that was just deleted raises
                    # Boost.Python.ArgumentError here.
                    pass
        self._watched = []

    def _on_points_changed(self):
        self._watch_points()
        self._on_point_changed()

    def _on_point_changed(self):
        # While a preset list has the screen there is nothing to redraw; the
        # repertoire is drawn fresh when that list closes.
        if self._open:
            self.draw()
        self._surface.update_play_led()

    def disconnect(self):
        self._unwatch_points()
        if self._watching_song:
            try:
                self._surface.song().remove_cue_points_listener(
                    self._on_points_changed)
            except (AttributeError, RuntimeError):
                pass
            self._watching_song = False

    # -- the list ------------------------------------------------------------

    def cue_points(self):
        try:
            return list(self._surface.song().cue_points)
        except (AttributeError, RuntimeError):
            return []

    def names(self):
        out = []
        for point in self.cue_points():
            try:
                out.append(point.name)
            except (AttributeError, RuntimeError):
                out.append("?")
        return out

    def draw(self):
        """
        Redraw the whole list. Called at startup, when a preset list closes,
        and when a locator changes in Live.
        """
        names = self.names()
        if not names:
            self._surface.log_message(
                "KeyLabLive/repertoire: no locators in the Arrangement - "
                "the list stays empty")
            return
        self._cursor = max(0, min(self._cursor, len(names) - 1))
        self._top = list_top(self._cursor, len(names))
        self._send(names, self._top, self._cursor)
        self._open = True

    def _send(self, names, top, cursor):
        surface = self._surface
        surface.send(list_title_packet(cfg.REPERTOIRE_TITLE, len(names)))
        visible = names[top:top + LIST_VISIBLE_LINES]
        for offset, name in enumerate(visible):
            surface.send(list_item_packet(LIST_APPEND, name, top + offset))
        surface.send(list_cursor_packet(cursor))

    def is_open(self):
        return self._open

    def set_open(self, value):
        self._open = bool(value)

    # -- moving --------------------------------------------------------------

    def move(self, delta):
        names = self.names()
        if not names:
            return
        self._cursor = max(0, min(self._cursor + delta, len(names) - 1))

        # Keep the window where the firmware expects it (see list_top), and
        # push in one line at a time rather than redrawing everything - a
        # full redraw on every wheel tick is visibly slower on the hardware.
        top = list_top(self._cursor, len(names))
        while self._top < top:
            self._top += 1
            bottom = self._top + LIST_VISIBLE_LINES - 1
            self._surface.send(list_item_packet(LIST_APPEND, names[bottom], bottom))
        while self._top > top:
            self._top -= 1
            self._surface.send(list_item_packet(
                LIST_PREPEND, names[self._top], self._top))

        self._surface.send(list_cursor_packet(self._cursor))
        self._surface.update_play_led()

    def cursor_has_locator(self):
        return 0 <= self._cursor < len(self.cue_points())

    # -- transport -----------------------------------------------------------

    def play_cursor(self):
        """
        Jump to the song at the cursor and start it.

        Uses the cue point's own jump, not current_song_time: that property
        cannot be set, it reads back unchanged whatever the transport does.
        """
        points = self.cue_points()
        if not (0 <= self._cursor < len(points)):
            return
        try:
            points[self._cursor].jump()
            self._surface.song().start_playing()
        except (AttributeError, RuntimeError) as exc:
            self._surface.log_message(
                "KeyLabLive/repertoire: could not start (%r)" % (exc,))
            return
        self._arm_stop(points)

    def stop(self):
        try:
            self._surface.song().stop_playing()
        except (AttributeError, RuntimeError):
            pass
        self._stop_at = None

    def _arm_stop(self, points):
        """Work out where the automatic stop should happen."""
        self._stop_at = None
        if self._cursor + 1 >= len(points):
            return          # last song - let it run to the end
        try:
            next_time = points[self._cursor + 1].time
            tempo = self._surface.song().tempo
        except (AttributeError, RuntimeError):
            return
        # STOP_LEAD_MS is in milliseconds; the transport works in beats, and
        # the conversion depends on the tempo, so it is done fresh each time
        # rather than stored.
        lead_beats = (cfg.STOP_LEAD_MS / 1000.0) * (tempo / 60.0)
        self._stop_at = next_time - lead_beats

    def poll(self):
        """
        Called on every display update. The position is polled rather than
        listened to: that is accurate enough for a stop that is deliberately
        early anyway - see STOP_LEAD_MS.
        """
        if self._stop_at is None:
            return
        try:
            if not self._surface.song().is_playing:
                self._stop_at = None
                return
            position = self._surface.song().current_song_time
        except (AttributeError, RuntimeError):
            return
        if position < self._stop_at:
            return

        self._stop_at = None
        try:
            self._surface.song().stop_playing()
        except (AttributeError, RuntimeError):
            return
        # Move on to the next song so the cursor is where you want it before
        # you have thought about it.
        self.move(1)
