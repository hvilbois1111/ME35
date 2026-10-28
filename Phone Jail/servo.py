# servo.py - hobby servo on a 50 Hz PWM pin.
import time
from machine import Pin, PWM


class Servo:
    def __init__(self, pin, min_us=500, max_us=2500, freq=50, start_angle=None):
        self.pwm = PWM(Pin(pin), freq=freq)
        self.min_us = min_us
        self.max_us = max_us
        self.angle_now = None
        if start_angle is not None:
            self.write(start_angle)

    def write(self, angle):
        angle = max(0, min(180, angle))
        us = self.min_us + (self.max_us - self.min_us) * angle / 180
        self.pwm.duty_ns(int(us * 1000))
        self.angle_now = angle

    def sweep(self, target, step_deg=2, step_ms=10):
        """Move smoothly instead of snapping (gentler on the phone and the arm)."""
        if self.angle_now is None:
            self.write(target)
            return
        a = self.angle_now
        step = step_deg if target > a else -step_deg
        while (step > 0 and a < target) or (step < 0 and a > target):
            a = min(a + step, target) if step > 0 else max(a + step, target)
            self.write(a)
            time.sleep_ms(step_ms)
