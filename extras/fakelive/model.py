"""
Fake Live object model: song, tracks, devices, parameters, locators, browser.

Every property that can be listened to gets add_<name>_listener,
remove_<name>_listener and <name>_has_listener automatically. When a script
asks for something the model does not have, it is recorded in MISSING:
scripts often catch AttributeError themselves, and a gap in the model would
otherwise go unnoticed.
"""

MISSING = []


class Observable(object):
    _observable = ()

    def __init__(self, **values):
        object.__setattr__(self, "_listeners", {})
        for key, value in values.items():
            object.__setattr__(self, key, value)

    def __setattr__(self, key, value):
        old = self.__dict__.get(key, None)
        object.__setattr__(self, key, value)
        if key in self._observable and old != value:
            for cb in list(self._listeners.get(key, [])):
                cb()

    def __getattr__(self, key):
        for prefix, suffix in (("add_", "_listener"), ("remove_", "_listener"), ("", "_has_listener")):
            if key.startswith(prefix) and key.endswith(suffix):
                prop = key[len(prefix):-len(suffix)]
                if prop in self._observable:
                    return self._make_listener_func(prefix, prop)
        MISSING.append("%s.%s" % (type(self).__name__, key))
        raise AttributeError("%s has no '%s' (fake Live)" % (type(self).__name__, key))

    def _make_listener_func(self, prefix, prop):
        lst = self._listeners.setdefault(prop, [])
        if prefix == "add_":
            return lambda cb: lst.append(cb)
        if prefix == "remove_":
            def remove(cb):
                if cb not in lst:
                    raise RuntimeError("remove_%s_listener: listener was not added" % prop)
                lst.remove(cb)
            return remove
        return lambda cb: cb in lst

    def listener_count(self):
        return sum(len(v) for v in self._listeners.values())


class Parameter(Observable):
    _observable = ("value", "name")

    def __init__(self, name, value=0.0, min=0.0, max=1.0, is_quantized=False, items=()):
        Observable.__init__(self, name=name, value=value, min=min, max=max,
                            is_quantized=is_quantized, is_enabled=True,
                            value_items=tuple(items), original_name=name)

    def __setattr__(self, key, value):
        if key == "value" and "min" in self.__dict__:
            if value < self.min or value > self.max:
                raise RuntimeError("Invalid value %r for '%s' (%s..%s)" % (value, self.name, self.min, self.max))
        Observable.__setattr__(self, key, value)

    def __str__(self):
        return "%s" % self.value

    def str_for_value(self, value):
        return "%s" % value

    @property
    def display_value(self):
        return str(self.value)


class Chain(Observable):
    _observable = ("devices", "name")

    def __init__(self, name, devices=()):
        Observable.__init__(self, name=name, devices=list(devices))


class Device(Observable):
    _observable = ("name", "parameters", "chains")

    def __init__(self, name, params=(), type=0, chains=None, class_name="Fake"):
        plist = [Parameter("Device On", 1.0, 0.0, 1.0)] + [
            p if isinstance(p, Parameter) else Parameter(p) for p in params]
        Observable.__init__(self, name=name, parameters=plist, type=type,
                            can_have_chains=chains is not None,
                            chains=list(chains or []), class_name=class_name,
                            class_display_name=class_name)


class MixerDevice(Observable):
    def __init__(self, sends=1):
        Observable.__init__(self, volume=Parameter("Track Volume", 0.85),
                            panning=Parameter("Track Panning", 0.0, -1.0, 1.0),
                            sends=[Parameter("%s-Send" % chr(65 + i)) for i in range(sends)])


class Track(Observable):
    _observable = ("arm", "name", "color", "devices", "mute", "solo", "input_routing_type")

    def __init__(self, name, devices=(), color=0x3C8CE6, can_be_armed=True, sends=1):
        Observable.__init__(self, name=name, devices=list(devices), color=color,
                            arm=False, mute=False, solo=False,
                            can_be_armed=can_be_armed, has_midi_input=True,
                            mixer_device=MixerDevice(sends))


class CuePoint(Observable):
    _observable = ("name", "time")

    def __init__(self, song, name, time):
        Observable.__init__(self, name=name, time=float(time))
        object.__setattr__(self, "_song", song)

    def jump(self):
        self._song.current_song_time = self.time


class SongView(Observable):
    _observable = ("selected_track",)

    def __init__(self):
        Observable.__init__(self, selected_track=None, selected_device=None)

    def select_device(self, device, *a):
        object.__setattr__(self, "selected_device", device)


class Song(Observable):
    _observable = ("is_playing", "tracks", "cue_points", "tempo", "current_song_time", "scenes",
                   "record_mode", "metronome", "can_undo", "can_redo", "can_capture_midi")

    def __init__(self, tracks=(), tempo=120.0):
        Observable.__init__(self, tracks=list(tracks), return_tracks=[], scenes=[],
                            cue_points=[], tempo=float(tempo),
                            is_playing=False, current_song_time=0.0,
                            record_mode=False, metronome=False,
                            can_undo=False, can_redo=False, can_capture_midi=False,
                            view=SongView())
        object.__setattr__(self, "_data", {})

    def add_cue(self, name, beat):
        self.cue_points = sorted(self.cue_points + [CuePoint(self, name, beat)], key=lambda c: c.time)

    def get_data(self, key, default):
        return self._data.get(key, default)

    def set_data(self, key, value):
        self._data[key] = value

    def start_playing(self):
        self.is_playing = True

    def stop_playing(self):
        self.is_playing = False

    def continue_playing(self):
        self.is_playing = True

    def undo(self):
        self.can_undo = False

    def redo(self):
        self.can_redo = False

    def capture_midi(self, *a):
        self.can_capture_midi = False

    def tap_tempo(self):
        pass


# ----- browser -----------------------------------------------------------------

class BrowserItem(Observable):
    def __init__(self, name, children=(), is_loadable=False, is_folder=False):
        Observable.__init__(self, name=name, children=list(children),
                            is_loadable=is_loadable, is_folder=is_folder,
                            is_device=False, uri="fake:" + name)


class Browser(Observable):
    _observable = ("hotswap_target",)

    def __init__(self, collections=None, instruments=None):
        Observable.__init__(self, hotswap_target=None,
                            colors=list(collections or []),
                            instruments=BrowserItem("Instruments", instruments or []),
                            sounds=BrowserItem("Sounds"), user_library=BrowserItem("User Library"),
                            user_folders=[], drums=BrowserItem("Drums"),
                            audio_effects=BrowserItem("Audio Effects"),
                            midi_effects=BrowserItem("MIDI Effects"), plugins=BrowserItem("Plug-ins"),
                            max_for_live=BrowserItem("Max for Live"), packs=[], current_project=BrowserItem("Project"))
        object.__setattr__(self, "loaded", [])

    def load_item(self, item):
        target = self.hotswap_target
        self.loaded.append((item.name, target))
        if target is not None:
            name = item.name.rsplit(".", 1)[0] if "." in item.name else item.name
            target.name = name


class AppView(Observable):
    def __init__(self):
        Observable.__init__(self)
        object.__setattr__(self, "_visible", set())

    def is_view_visible(self, name, *a):
        return name in self._visible

    def show_view(self, name):
        self._visible.add(name)

    def focus_view(self, name):
        self._visible.add(name)


class Application(Observable):
    def __init__(self, browser):
        Observable.__init__(self, browser=browser, view=AppView())

    def get_major_version(self):
        return 12

    def get_minor_version(self):
        return 4

    def get_bugfix_version(self):
        return 6
