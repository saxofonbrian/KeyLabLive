"""
The rig: runs a KeyLab script against the fake Live, without hardware.

    rig = Rig("../../KeyLabLive", keylablive_set.build)
    rig.press(49)            # screen button 1, short
    rig.hold(49, 0.6)        # screen button 1, held
    rig.pad(5)               # pad 5
    rig.wheel(+3)            # three clicks clockwise
    print(rig.screen.render())

The script folder is copied to a temporary folder first, so files the script
writes do not touch the real ones. The clock is fake: long presses and waits
take no time.
"""
import importlib
import os
import shutil
import sys
import tempfile
import threading as _real_threading
import time as _real_time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import Live                                  # noqa: E402
import model                                 # noqa: E402
from screen import KeyLabScreen              # noqa: E402
from _Framework import ButtonElement as _be  # noqa: E402

TICK = 0.1   # Live calls update_display about ten times a second


class Clock(object):
    def __init__(self):
        self.now = 1_800_000_000.0
        self.timers = []


class FakeTimer(object):
    def __init__(self, clock, interval, function, args=None, kwargs=None):
        self._clock, self.interval, self.function = clock, interval, function
        self.args, self.kwargs = args or (), kwargs or {}
        self.daemon = True
        self.deadline = None
        self.cancelled = False

    def start(self):
        self.deadline = self._clock.now + self.interval
        self._clock.timers.append(self)

    def cancel(self):
        self.cancelled = True

    def is_alive(self):
        return self.deadline is not None and not self.cancelled and self in self._clock.timers


def _fake_time_module(clock):
    m = types.ModuleType("time")
    for k in dir(_real_time):
        setattr(m, k, getattr(_real_time, k))
    m.time = lambda: clock.now
    m.monotonic = lambda: clock.now
    m.perf_counter = lambda: clock.now
    m.sleep = lambda s: None
    m.localtime = lambda t=None: _real_time.localtime(clock.now if t is None else t)
    m.strftime = lambda fmt, t=None: _real_time.strftime(fmt, t or _real_time.localtime(clock.now))
    return m


def _fake_threading_module(clock):
    m = types.ModuleType("threading")
    for k in dir(_real_threading):
        setattr(m, k, getattr(_real_threading, k))
    m.Timer = lambda interval, function, args=None, kwargs=None: FakeTimer(clock, interval, function, args, kwargs)
    return m


class _CInstance(object):
    def __init__(self, rig):
        self._rig = rig
        self.song = rig.song
        self.app = rig.app

    def on_midi_out(self, msg):
        self._rig.midi_out.append(msg)
        self._rig.screen.feed(msg)

    def on_log(self, text):
        self._rig.log.append(text)


class Rig(object):
    _counter = 0

    def __init__(self, script_path, build, keep_copy=False):
        """script_path: the script folder, absolute or relative to this file."""
        script_path = os.path.normpath(os.path.join(HERE, script_path))
        script_folder = os.path.basename(script_path)
        self.keep_copy = keep_copy
        self.clock = Clock()
        self.song, browser = build()
        self.app = model.Application(browser)
        Live.Application._app = self.app
        self.midi_out, self.log = [], []
        self.screen = KeyLabScreen()
        del model.MISSING[:]
        del _be.REGISTRY[:]

        # The copy gets a unique name, so every rig gets its own modules.
        Rig._counter += 1
        self.tmp = tempfile.mkdtemp(prefix="fakelive_")
        pkg = "%s_rig%d" % (script_folder, Rig._counter)
        self.folder = os.path.join(self.tmp, pkg)
        shutil.copytree(script_path, self.folder,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "_to_delete", ".DS_Store"))
        sys.path.insert(0, self.tmp)
        self.package = importlib.import_module(pkg)
        ft, fth = _fake_time_module(self.clock), _fake_threading_module(self.clock)
        for name, mod in list(sys.modules.items()):
            if name == pkg or name.startswith(pkg + "."):
                if getattr(mod, "time", None) is _real_time:
                    mod.time = ft
                if getattr(mod, "threading", None) is _real_threading:
                    mod.threading = fth
        self.surface = self.package.create_instance(_CInstance(self))
        self.tick()

    # ----- time -----

    def tick(self, n=1):
        """n calls to update_display, TICK seconds apart; timers fire on the way."""
        for _ in range(n):
            self.clock.now += TICK
            self._fire_timers()
            self.surface.update_display()

    def wait(self, seconds):
        self.tick(max(1, int(round(seconds / TICK))))

    def _fire_timers(self):
        due = [t for t in self.clock.timers if not t.cancelled and t.deadline <= self.clock.now]
        self.clock.timers = [t for t in self.clock.timers if t not in due and not t.cancelled]
        for t in due:
            t.function(*t.args, **t.kwargs)

    # ----- hardware in -----

    def _send(self, msg_type, channel, ident, value):
        hit = [e for e in _be.REGISTRY
               if e.msg_type == msg_type and e.channel == channel and e.identifier == ident]
        for e in hit:
            e.receive_value(value)
        return bool(hit)

    def listens(self, cc, channel=0):
        return any(e.msg_type == 1 and e.channel == channel and e.identifier == cc
                   for e in _be.REGISTRY)

    def cc(self, cc, value, channel=0):
        if not self._send(1, channel, cc, value):
            self.log.append("[rig] CC%d=%d: no element is listening" % (cc, value))
        self.tick()

    def press(self, cc):
        self.cc(cc, 127)
        self.cc(cc, 0)

    def hold(self, cc, seconds=0.6):
        self.cc(cc, 127)
        self.wait(seconds)
        self.cc(cc, 0)

    def pad(self, number, hold=0.0):
        """number is 1-12, as on the keyboard."""
        note = number - 1
        self._send(0, 9, note, 127)
        self.tick()
        if hold:
            self.wait(hold)
        self._send(0, 9, note, 0)
        self.tick()

    def wheel(self, steps):
        for _ in range(abs(steps)):
            self.cc(116, 65 if steps > 0 else 63)

    def wheel_click(self):
        self.press(117)

    def disconnect(self):
        self.surface.disconnect()
        if not self.keep_copy:
            shutil.rmtree(self.tmp, ignore_errors=True)

    # ----- reading back -----

    def errors(self):
        return [l for l in self.log if l.startswith("[rig]")] + ["model is missing: " + m for m in sorted(set(model.MISSING))]
