# sevenseg.py - single-digit 7-segment driver (works with either polarity).
# Common cathode (e.g. 5161AS): COM pins (3 and 8) to GND, segment lit when GPIO is HIGH.
# Common anode   (e.g. 5161BS, INND-TS56RAB): COM pins to 3V3, segment lit when GPIO is LOW.
from machine import Pin

#            a  b  c  d  e  f  g
_DIGITS = {
    0: (1, 1, 1, 1, 1, 1, 0),
    1: (0, 1, 1, 0, 0, 0, 0),
    2: (1, 1, 0, 1, 1, 0, 1),
    3: (1, 1, 1, 1, 0, 0, 1),
    4: (0, 1, 1, 0, 0, 1, 1),
    5: (1, 0, 1, 1, 0, 1, 1),
    6: (1, 0, 1, 1, 1, 1, 1),
    7: (1, 1, 1, 0, 0, 0, 0),
    8: (1, 1, 1, 1, 1, 1, 1),
    9: (1, 1, 1, 1, 0, 1, 1),
    "-": (0, 0, 0, 0, 0, 0, 1),
}


class SevenSeg:
    def __init__(self, seg_pins, dp_pin=None, common_anode=True):
        self._on = 0 if common_anode else 1
        self._off = 1 - self._on
        self.segs = [Pin(p, Pin.OUT, value=self._off) for p in seg_pins]
        self.dp = Pin(dp_pin, Pin.OUT, value=self._off) if dp_pin is not None else None
        self._current = None

    def show(self, symbol):
        """Show 0-9 or '-'. Anything else blanks the display."""
        if symbol == self._current:
            return
        pattern = _DIGITS.get(symbol)
        if pattern is None:
            self.clear()
            return
        for pin, lit in zip(self.segs, pattern):
            pin.value(self._on if lit else self._off)
        self._current = symbol

    def set_dp(self, on):
        if self.dp is not None:
            self.dp.value(self._on if on else self._off)

    def clear(self):
        for pin in self.segs:
            pin.value(self._off)
        self.set_dp(False)
        self._current = None
