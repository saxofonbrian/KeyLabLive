"""
Runs KeyLabLive's basic moves against the fake Live and checks the result.

    python3 test_keylablive.py                  # tests ../../KeyLabLive
    python3 test_keylablive.py path/to/script   # tests another copy

Every failed check is printed with the screen as it looked at that moment.
Exit code 0 means everything passed.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rig import Rig       # noqa: E402
import keylablive_set     # noqa: E402

BUTTON = {1: 49, 2: 50, 3: 51, 4: 52, 5: 45, 6: 46, 7: 47, 8: 48}
FADER_1, FADER_1_TOUCH = 105, 28
STOP, PLAY, TAP, CYCLE, METRO = 20, 21, 23, 24, 27

failures = []


def check(rig, label, ok):
    if not ok:
        failures.append(label)
        print("FAIL: %s\n%s\n" % (label, rig.screen.render()))


def main(script_path):
    script_path = os.path.normpath(os.path.join(os.getcwd(), script_path))
    rig = Rig(script_path, lambda: keylablive_set.build(script_path))
    rig.wait(1.5)
    s = rig.screen
    song = rig.song
    t = song.tracks

    check(rig, "startup: DAW handshake sent", s.connected)
    check(rig, "startup: the song list is on screen", s.list_title == "Repertoire")
    check(rig, "startup: one screen button per track", all(s.footer_text(i) for i in (1, 2, 3, 4)))

    # Arm
    rig.press(BUTTON[2])
    check(rig, "short press arms the track", t[1].arm and s.footers[2]["lit"])
    rig.press(BUTTON[2])
    rig.tick(3)
    check(rig, "short press again un-arms it", not t[1].arm and not s.footers[2]["lit"])

    # Preset list
    rig.hold(BUTTON[1], 0.6)
    check(rig, "hold opens the preset list", s.list_title not in ("Repertoire", None) and s.list_length > 0)
    check(rig, "opening the list selects the track in Live", song.view.selected_track is t[0])
    rig.press(BUTTON[3])
    rig.tick(3)
    check(rig, "arming works while a list is open", t[2].arm)
    rig.press(BUTTON[3])
    rig.tick(3)
    rig.wheel(2)
    check(rig, "the wheel moves the cursor", s.list_cursor == 2)
    wanted = s.list_items[2][0]
    rig.press(PLAY)
    rig.tick(3)
    loaded = rig.app.browser.loaded
    check(rig, "Play hot-swaps the preset into the track's instrument",
          loaded and loaded[-1][1] is t[0].devices[0])
    check(rig, "the button shows the preset", s.footer_text(1) == wanted[:len(s.footer_text(1) or "")])

    title = s.list_title
    rig.press(METRO)
    check(rig, "Metro steps to the next chapter", s.list_title != title)
    rig.press(TAP)
    check(rig, "Tap steps back", s.list_title == title)

    rig.press(STOP)
    check(rig, "Stop closes the list", s.list_title == "Repertoire")
    check(rig, "Stop on a list does not start or stop anything", not song.is_playing)

    # Song list
    rig.wheel(1)
    rig.press(PLAY)
    check(rig, "Play starts the song under the cursor", song.is_playing
          and song.current_song_time == keylablive_set.BEATS_PER_SONG)
    song.current_song_time = 2 * keylablive_set.BEATS_PER_SONG - 0.2
    rig.tick(2)
    check(rig, "playback stops just before the next locator", not song.is_playing)
    check(rig, "the cursor moves on to the next song", s.list_cursor == 2)

    # Faders
    before = t[0].mixer_device.volume.value
    rig.cc(FADER_1, 30)
    check(rig, "a fader's first value (where it was left) does not touch the track",
          t[0].mixer_device.volume.value == before)
    rig.cc(FADER_1, 100)
    check(rig, "moving fader 1 sets track 1's volume",
          abs(t[0].mixer_device.volume.value - 100 / 127.0) < 0.01)
    rig.cc(FADER_1_TOUCH, 127)
    check(rig, "touching fader 1 shows its readout", s.popup and s.popup[0] == "fader")
    rig.cc(FADER_1_TOUCH, 0)

    # Cycle
    rig.press(CYCLE)
    rig.wait(2.0)
    check(rig, "Cycle writes presets.txt from the Collection",
          os.path.exists(os.path.join(rig.folder, "presets.txt")))

    for line in rig.errors():
        failures.append(line)
        print("FAIL:", line)
    rig.disconnect()
    leftover = [tr.name for tr in t if tr.listener_count()]
    if leftover:
        failures.append("listeners left after disconnect: %s" % leftover)
        print("FAIL: listeners left after disconnect:", leftover)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "..", "KeyLabLive")
    main(path)
    print("KeyLabLive: %s" % ("all checks passed" if not failures else "%d failed" % len(failures)))
    sys.exit(1 if failures else 0)
