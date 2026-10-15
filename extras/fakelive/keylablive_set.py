"""
A fake Live set for KeyLabLive: four instrument tracks, a few locators, and a
'Presets' Collection in the browser. build() returns (song, browser) for Rig.

The browser also holds every name in the script's presets-manual.txt, so the
manual list loads as it would with Live's own library.
"""
import os

from model import Browser, BrowserItem, Device, Parameter, Song, Track

INSTRUMENT = 1

TRACKS = [
    ("Piano", "Grand Piano", 0xE6A03C),
    ("Pad", "Analog", 0x3CE68C),
    ("Organ", "Organ", 0xC83C3C),
    ("Synth", "Wavetable", 0x8C3CE6),
]

LOCATORS = ["Intro", "First Song", "Second Song", "Third Song", "Encore"]
BEATS_PER_SONG = 64

COLLECTION = ["Grand Piano.adg", "Suitcase.adg", "Warm Pad.adv", "Drawbars.adg",
              "Saw Lead.adv", "Sub Bass.adv"]


def manual_names(script_path):
    path = os.path.join(script_path, "presets-manual.txt")
    names = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("["):
                    names.append(line.split(",")[0].strip())
    return names


def build(script_path, collection=None):
    tracks = [Track(name, [Device(device, [Parameter("Volume", 0.5)], type=INSTRUMENT)],
                    color=colour)
              for name, device, colour in TRACKS]
    song = Song(tracks, tempo=120.0)
    for n, name in enumerate(LOCATORS):
        song.add_cue(name, n * BEATS_PER_SONG)

    names = COLLECTION if collection is None else collection
    presets = BrowserItem("Presets", [BrowserItem(n, is_loadable=True) for n in names])
    sounds = [BrowserItem(n, is_loadable=True) for n in manual_names(script_path)]
    return song, Browser(collections=[presets], instruments=sounds)
