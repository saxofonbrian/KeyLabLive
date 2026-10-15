# =============================================================================
# aaCQ20B - a bridge between a Live control surface script and an
# Allen & Heath CQ20B mixer
# =============================================================================
#
# WHY A SEPARATE SCRIPT
#   A control surface script can only send MIDI out of its own Output port.
#   The main script's port is the keyboard, so NRPN for the mixer has to go
#   out through another script, one that has the CQ20B as its Output. This
#   script does nothing on its own: it sends what the main script asks for,
#   and passes the mixer's replies back.
#
# SETUP IN LIVE (Preferences -> Link, Tempo & MIDI)
#   Control Surface (a free slot): aaCQ20B
#   Input:  CQ20B      Output: CQ20B
#   Under MIDI Ports, turn on "Remote" for the CQ20B, In and Out.
#
# HOW THE MAIN SCRIPT FINDS IT
#   Through a shared module in sys.modules (registry() below). It works
#   whatever the folders are called and whichever script Live loads first.
#   The main script looks up registry().instance when it needs the bridge;
#   if it is None, the mixer is simply not there.
#
# NRPN (A&H CQ MIDI Protocol V1.2, MIDI channel 1)
#   CC99 address MSB, CC98 address LSB, CC6 data MSB, CC38 data LSB.
#   Level:      value in CC6, CC38 = 0. The CQ20B wants both data bytes.
#   Mute:       CC6 = 0, CC38 = 1 (mute) or 0 (unmute). Address MSB 0x00.
#   Get value:  CC99, CC98, then CC96 = 0x7F. The mixer replies with the
#               current value as a normal NRPN.
#   Addresses are in cq20b_addresses.py.
# =============================================================================

import sys
import types

from _Framework.ControlSurface import ControlSurface
from _Framework.InputControlElement import MIDI_CC_TYPE
from _Framework.ButtonElement import ButtonElement

CQ_CHANNEL = 0  # 0-indexed: MIDI channel 1
NRPN_MSB_CC = 99
NRPN_LSB_CC = 98
DATA_MSB_CC = 6
DATA_LSB_CC = 38
DATA_INCREMENT_CC = 96

REGISTRY_NAME = "cq20b_bridge_registry"


def registry():
    reg = sys.modules.get(REGISTRY_NAME)
    if reg is None:
        reg = types.ModuleType(REGISTRY_NAME)
        reg.instance = None
        sys.modules[REGISTRY_NAME] = reg
    return reg


class CQ20BBridge(ControlSurface):

    def __init__(self, c_instance):
        super(CQ20BBridge, self).__init__(c_instance)
        with self.component_guard():
            self._listeners = []
            self._last_addr = None   # last (msb, lsb) sent, see send_nrpn
            self._rx_msb = None
            self._rx_lsb = None
            self._rx_data_msb = 0
            self._elements = []
            for cc, callback in (
                (NRPN_MSB_CC, self._on_rx_msb),
                (NRPN_LSB_CC, self._on_rx_lsb),
                (DATA_MSB_CC, self._on_rx_data_msb),
                (DATA_LSB_CC, self._on_rx_data_lsb),
            ):
                element = ButtonElement(False, MIDI_CC_TYPE, CQ_CHANNEL, cc)
                element.add_value_listener(callback)
                self._elements.append((element, callback))
        registry().instance = self

    # ----- sending -----

    def _cc(self, cc, value):
        self._send_midi((0xB0 | CQ_CHANNEL, cc, value & 0x7F))

    def send_nrpn(self, msb, lsb, data_msb, data_lsb):
        """
        Sends the address (CC99/98) only when it changes, otherwise only the
        data (CC6/38). While a fader moves that halves the traffic.
        """
        if self._last_addr != (msb, lsb):
            self._cc(NRPN_MSB_CC, msb)
            self._cc(NRPN_LSB_CC, lsb)
            self._last_addr = (msb, lsb)
        self._cc(DATA_MSB_CC, data_msb)
        self._cc(DATA_LSB_CC, data_lsb)

    def request_value(self, msb, lsb):
        """Asks the mixer for the current value. The reply comes to the listeners."""
        self._cc(NRPN_MSB_CC, msb)
        self._cc(NRPN_LSB_CC, lsb)
        self._cc(DATA_INCREMENT_CC, 0x7F)
        self._last_addr = None

    # ----- receiving (replies, and changes made on the mixer itself) -----

    def add_listener(self, callback):
        """callback(msb, lsb, data_msb, data_lsb) for every complete NRPN from the mixer."""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _on_rx_msb(self, value):
        self._rx_msb = value

    def _on_rx_lsb(self, value):
        self._rx_lsb = value

    def _on_rx_data_msb(self, value):
        self._rx_data_msb = value

    def _on_rx_data_lsb(self, value):
        if self._rx_msb is None or self._rx_lsb is None:
            return
        for callback in list(self._listeners):
            callback(self._rx_msb, self._rx_lsb, self._rx_data_msb, value)

    def disconnect(self):
        for element, callback in self._elements:
            element.remove_value_listener(callback)
        self._listeners = []
        reg = registry()
        if reg.instance is self:
            reg.instance = None
        super(CQ20BBridge, self).disconnect()
