# Fake "Live" module: only what scripts look up in it.
class _DeviceType(object):
    undefined, instrument, audio_effect, midi_effect = 0, 1, 2, 4


class Device(object):
    DeviceType = _DeviceType


class Application(object):
    _app = None

    @staticmethod
    def get_application():
        return Application._app
