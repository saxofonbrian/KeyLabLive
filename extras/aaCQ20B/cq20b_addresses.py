# =============================================================================
# NRPN addresses on the Allen & Heath CQ20B
# =============================================================================
#
# Plain Python, no Live needed. Used by the main script to turn a target
# written in a text file, such as "ST1 > Out5", into the (msb, lsb) address
# the bridge sends.
#
# CHANNEL INDEX
#   Ip1-Ip16 = 0-15, ST1 = 0x18, ST2 = 0x1A, USB = 0x1C, BT = 0x1E.
#
# LEVELS (0-127 in data MSB, data LSB = 0)
#   Channel to Main LR:   0x40 * 128 + channel
#   Channel to Out1-6:    0x40 * 128 + 0x44 + 12 * channel + slot
#                         each channel has a block of 12 places, Out1-Out6
#                         are places 0-5 (Ip1 > Out1 is 40 44)
#   Output master:        0x4F 0x00 for Main LR, 0x4F 0x01-0x06 for Out1-6
#
#   With the outputs linked as stereo pairs, address the odd ones: Out1,
#   Out3, Out5.
#
# MUTES (address MSB 0x00, data LSB 1 = mute, 0 = unmute)
#   Input channels: the channel index as LSB.
#   Main LR 0x44, Out1 0x45, Out3 0x47, Out5 0x49, FX1 0x51, FX2 0x52.
#   Muting FX1 or FX2 mutes the whole effect return, not one channel's send.
# =============================================================================

CHANNELS = {"st1": 0x18, "st2": 0x1A, "usb": 0x1C, "bt": 0x1E}
for _n in range(1, 17):
    CHANNELS["ip%d" % _n] = _n - 1

_SEND_BASE = 0x40 * 128 + 0x44   # Ip1 > Out1
_SEND_STRIDE = 12                # places per channel
_OUT_SLOT = {"out1": 0, "out2": 1, "out3": 2, "out4": 3, "out5": 4, "out6": 5}

DESTINATIONS = {"mainlr": lambda ch: 0x40 * 128 + ch}
for _name, _slot in _OUT_SLOT.items():
    def _make(slot):
        return lambda ch: _SEND_BASE + _SEND_STRIDE * ch + slot
    DESTINATIONS[_name] = _make(_slot)

OUTPUT_MASTERS = {
    "mainlr": (0x4F, 0x00),
    "out1":   (0x4F, 0x01),
    "out2":   (0x4F, 0x02),
    "out3":   (0x4F, 0x03),
    "out4":   (0x4F, 0x04),
    "out5":   (0x4F, 0x05),
    "out6":   (0x4F, 0x06),
}

MUTE_MSB = 0x00
MUTE_TARGETS = dict(CHANNELS)
MUTE_TARGETS.update({
    "mainlr": 0x44,
    "out1":   0x45,
    "out3":   0x47,
    "out5":   0x49,
    "fx1":    0x51,
    "fx2":    0x52,
})


def _key(text):
    return text.strip().lower().replace(" ", "").replace("/", "")


def level_address(spec):
    """
    The (msb, lsb) of a level:
        'ST1 > Out5'    a channel's send to Out1-6 or MainLR
        'Out1'          an output master, Out1-6 or MainLR
        '46 18'         raw hex MSB LSB
    Raises ValueError for anything else.
    """
    if ">" in spec:
        left, right = spec.split(">", 1)
        channel = CHANNELS.get(_key(left))
        dest = DESTINATIONS.get(_key(right))
        if channel is None:
            raise ValueError("unknown channel '%s'" % left.strip())
        if dest is None:
            raise ValueError("unknown destination '%s' (use Out1-6 or MainLR)" % right.strip())
        value = dest(channel)
        return (value >> 7) & 0x7F, value & 0x7F
    if _key(spec) in OUTPUT_MASTERS:
        return OUTPUT_MASTERS[_key(spec)]
    parts = spec.split()
    if len(parts) == 2:
        try:
            msb, lsb = int(parts[0], 16), int(parts[1], 16)
        except ValueError:
            msb = lsb = -1
        if 0 <= msb <= 127 and 0 <= lsb <= 127:
            return msb, lsb
    raise ValueError("'%s' is not a level (channel > destination, Out1-6, MainLR or hex MSB LSB)" % spec)


def mute_address(name):
    """The (msb, lsb) of a mute: 'Ip8', 'ST1', 'MainLR', 'Out3', 'FX1' ..."""
    lsb = MUTE_TARGETS.get(_key(name))
    if lsb is None:
        raise ValueError("'%s' is not a mute target" % name)
    return MUTE_MSB, lsb
