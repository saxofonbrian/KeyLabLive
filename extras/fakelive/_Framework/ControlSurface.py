import contextlib

import Live


class ControlSurface(object):
    """The part of Live's ControlSurface the scripts use. c_instance is the rig."""

    def __init__(self, c_instance):
        self._c_instance = c_instance
        self._scheduled = []

    @contextlib.contextmanager
    def component_guard(self):
        yield

    def song(self):
        return self._c_instance.song

    def application(self):
        return self._c_instance.app

    def _send_midi(self, midi_event_bytes, optimized=None):
        self._c_instance.on_midi_out(tuple(midi_event_bytes))
        return True

    def log_message(self, *message):
        self._c_instance.on_log(" ".join(str(m) for m in message))

    def show_message(self, message):
        self._c_instance.on_log("[status bar] " + str(message))

    def schedule_message(self, delay_in_ticks, callback, parameter=None):
        self._scheduled.append([max(1, int(delay_in_ticks)), callback, parameter])

    def update_display(self):
        due = [s for s in self._scheduled if s[0] <= 1]
        for s in self._scheduled:
            s[0] -= 1
        self._scheduled = [s for s in self._scheduled if s[0] > 0]
        for _, callback, parameter in due:
            callback() if parameter is None else callback(parameter)

    def request_rebuild_midi_map(self):
        pass

    def disconnect(self):
        pass
