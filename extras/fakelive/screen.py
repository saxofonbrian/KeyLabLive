"""
Reads the SysEx a script sends to a KeyLab mk3 in DAW mode and keeps track of
what the keyboard would show: screen buttons, LEDs, the list and popups.
The formats are those in KeyLabLive/keylab_screen.py.
"""

HEADER = (0xF0, 0x00, 0x20, 0x6B, 0x7F, 0x42)
LED_FAMILY = (0x00, 0x02, 0x03)
SCREEN_FAMILY = (0x00, 0x02, 0x04)
CONN_FAMILY = (0x00, 0x02, 0x05)

LED_NAMES = {4: "Tap", 5: "Rec", 6: "Play", 7: "Stop", 8: "Cycle", 9: "Back",
             10: "Fwd", 11: "Metro", 12: "Redo", 13: "Undo", 14: "Quant", 15: "Save"}
for _i in range(12):
    LED_NAMES[82 + _i] = "Pad%d" % (_i + 1)

VISIBLE, ANCHOR = 7, 3


def _text(body, i):
    out = []
    while i < len(body) and body[i] != 0x00:
        out.append(chr(body[i]))
        i += 1
    return "".join(out), i + 1


def _n14(hi, lo):
    return (hi << 7) | lo


def colour_name(rgb):
    if rgb is None:
        return "-"
    r, g, b = rgb
    if max(rgb) == 0:
        return "black"
    level = "bright" if max(rgb) >= 0x60 else "dim"
    if r and g and not b and abs(r - g) < r * 0.5:
        hue = "yellow"
    elif r and g and b and max(rgb) - min(rgb) < 0x10:
        hue = "white"
    elif r >= g and r >= b and g < r * 0.5 and b < r * 0.5:
        hue = "red"
    elif g >= r and g >= b and r < g * 0.5:
        hue = "cyan" if b > g * 0.5 else "green"
    elif b >= r and b >= g:
        hue = "purple" if r > b * 0.4 else ("cyan" if g > b * 0.5 else "blue")
    elif r > b and g > b:
        hue = "orange"
    else:
        hue = "%02x%02x%02x" % rgb
    return "%s %s" % (level, hue)


class KeyLabScreen(object):
    def __init__(self):
        self.footers = {}        # id -> dict(text, lit, colour)
        self.leds = {}           # id -> rgb
        self.list_title = None
        self.list_length = 0
        self.list_items = {}     # index -> (text, blue)
        self.list_cursor = None
        self.popup = None        # (layout, value, name, position)
        self.connected = False
        self.unknown = []
        self.packets = 0

    def feed(self, msg):
        self.packets += 1
        if msg[:1] != (0xF0,):
            return  # ordinary MIDI out of the DAW port, not the screen
        if tuple(msg[:6]) != HEADER:
            self.unknown.append(msg)
            return
        fam, body = tuple(msg[6:9]), msg[9:-1]
        if fam == CONN_FAMILY:
            self.connected = bool(body[0])
        elif fam == LED_FAMILY:
            self.leds[body[0]] = tuple(body[1:4])
        elif fam == SCREEN_FAMILY:
            self._screen(body)
        else:
            self.unknown.append(msg)

    def _screen(self, b):
        kind = b[0]
        if 0x01 <= kind <= 0x08:
            text, _ = _text(b, 13)
            self.footers[kind] = dict(text=text, lit=b[2] == 0x03, colour=tuple(b[8:11]))
        elif kind in (0x1C, 0x1D, 0x1E):
            value, i = _text(b, 2)
            name, i = _text(b, i + 1)
            pos = b[i + 1]
            self.popup = ({0x1C: "encoder", 0x1D: "fader", 0x1E: "popup"}[kind], value, name, pos)
        elif kind == 0x14:
            title, i = _text(b, 2)
            self.list_title = title
            self.list_length = _n14(b[i + 1], b[i + 2])
            self.list_items = {}
            self.list_cursor = None
        elif kind in (0x15, 0x16) and b[1] == 0x03:
            self.list_cursor = _n14(b[2], b[3])
        elif kind in (0x15, 0x16):
            text, i = _text(b, 2)
            blue = b[i + 1] == 0x01
            index = _n14(b[i + 4], b[i + 5])
            self.list_items[index] = (text, blue)
        else:
            self.unknown.append(tuple(b))

    # ----- display -----

    def list_top(self):
        c = self.list_cursor or 0
        return max(0, min(c - ANCHOR, self.list_length - VISIBLE))

    def visible_lines(self):
        top = self.list_top()
        rows = []
        for idx in range(top, min(top + VISIBLE, self.list_length)):
            text, blue = self.list_items.get(idx, ("<missing>", False))
            rows.append((idx, text, blue, idx == self.list_cursor))
        return rows

    def footer_text(self, fid):
        f = self.footers.get(fid)
        return f["text"] if f else None

    def render(self):
        out = []
        top = [self._footer(i) for i in (5, 6, 7, 8)]
        bottom = [self._footer(i) for i in (1, 2, 3, 4)]
        out.append(" | ".join(top))
        out.append("-" * 60)
        out.append("[%s] (%d lines)" % (self.list_title, self.list_length))
        for idx, text, blue, cur in self.visible_lines():
            out.append("%s%3d %s%s" % (">" if cur else " ", idx + 1, text, "  (blue)" if blue else ""))
        if self.popup:
            out.append("popup: %s  '%s' / '%s'  bar %d" % self.popup)
        out.append("-" * 60)
        out.append(" | ".join(bottom))
        out.append("LED: " + ", ".join("%s=%s" % (LED_NAMES.get(k, k), colour_name(v))
                                       for k, v in sorted(self.leds.items()) if k < 82))
        out.append("Pads: " + ", ".join("%d=%s" % (k - 81, colour_name(v))
                                        for k, v in sorted(self.leds.items()) if k >= 82))
        return "\n".join(out)

    def _footer(self, i):
        f = self.footers.get(i)
        if not f:
            return "%d:-" % i
        return "%d:%s%s" % (i, f["text"], "*" if f["lit"] else "")
