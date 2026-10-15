from .InputControlElement import MIDI_CC_TYPE, MIDI_NOTE_TYPE

# Every element, so the rig can send "physical" messages in.
REGISTRY = []


class ButtonElement(object):
    def __init__(self, is_momentary, msg_type, channel, identifier, *a, **k):
        self.is_momentary = is_momentary
        self.msg_type = msg_type
        self.channel = channel
        self.identifier = identifier
        self._listeners = []
        REGISTRY.append(self)

    def message_identifier(self):
        return self.identifier

    def add_value_listener(self, callback, identify_sender=False):
        self._listeners.append((callback, identify_sender))

    def remove_value_listener(self, callback):
        before = len(self._listeners)
        self._listeners = [l for l in self._listeners if l[0] != callback]
        if len(self._listeners) == before:
            raise RuntimeError("remove_value_listener: listener was not added")

    def value_has_listener(self, callback):
        return any(l[0] == callback for l in self._listeners)

    def receive_value(self, value):
        for callback, identify in list(self._listeners):
            if identify:
                callback(value, self)
            else:
                callback(value)

    def reset(self):
        pass

    def send_value(self, *a, **k):
        pass
