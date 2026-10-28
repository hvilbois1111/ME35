# joystick.py - Seeed Grove Thumb Joystick v1.1 on two ESP32 ADC1 pins.
# The stick is two potentiometers. There is no separate button wire:
# pressing the stick drives the X output to full scale, so a click = X near max.
import time
from machine import ADC, Pin

_FULL = 65535


class Joystick:
    def __init__(self, x_pin, y_pin, invert_y=False, deadzone=0.30,
                 click_level=0.93, repeat_delay_ms=500, repeat_rate_ms=250):
        self.x = ADC(Pin(x_pin))
        self.y = ADC(Pin(y_pin))
        for adc in (self.x, self.y):
            adc.atten(ADC.ATTN_11DB)                  # full 0-3.3 V range
        self.invert_y = invert_y
        self.deadzone = deadzone
        self.click_level = click_level
        self.repeat_delay_ms = repeat_delay_ms
        self.repeat_rate_ms = repeat_rate_ms
        self._held_dir = 0
        self._next_repeat = 0
        self._was_pressed = False
        self._press_start = None
        self.calibrate()

    def calibrate(self, samples=20):
        """Record the resting center. Don't touch the stick while this runs."""
        sx = sy = 0
        for _ in range(samples):
            sx += self.x.read_u16()
            sy += self.y.read_u16()
            time.sleep_ms(5)
        self.cx = sx / samples
        self.cy = sy / samples

    def raw(self):
        return self.x.read_u16(), self.y.read_u16()

    def is_pressed(self):
        return self.x.read_u16() > self.click_level * _FULL

    def vertical(self):
        """+1 = pushed up, -1 = pushed down, 0 = centered."""
        v = (self.y.read_u16() - self.cy) / (_FULL / 2)
        if self.invert_y:
            v = -v
        if v > self.deadzone:
            return 1
        if v < -self.deadzone:
            return -1
        return 0

    def step(self):
        """+1/-1 once per push, auto-repeating while held. 0 otherwise."""
        now = time.ticks_ms()
        d = 0 if self.is_pressed() else self.vertical()
        if d == 0:
            self._held_dir = 0
            return 0
        if d != self._held_dir:                       # new push
            self._held_dir = d
            self._next_repeat = time.ticks_add(now, self.repeat_delay_ms)
            return d
        if time.ticks_diff(now, self._next_repeat) >= 0:  # held: repeat
            self._next_repeat = time.ticks_add(now, self.repeat_rate_ms)
            return d
        return 0

    def clicked(self):
        """True once when the stick is pressed down (edge-triggered)."""
        p = self.is_pressed()
        fired = p and not self._was_pressed
        if p and not self._was_pressed:
            self._press_start = time.ticks_ms()
        if not p:
            self._press_start = None
        self._was_pressed = p
        return fired

    def held_ms(self):
        """How long the click has been held down (0 if not pressed)."""
        if self._press_start is None or not self.is_pressed():
            return 0
        return time.ticks_diff(time.ticks_ms(), self._press_start)
