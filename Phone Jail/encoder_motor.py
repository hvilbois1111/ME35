# encoder_motor.py - DFRobot FIT0450 gear motor (120:1, hall encoder) on the
# Robo ESP32's built-in motor driver. The driver takes two PWM inputs per motor:
# PWM on A + 0 on B spins one way, 0 on A + PWM on B spins the other way.
import time
from machine import Pin, PWM


class EncoderMotor:
    def __init__(self, pin_a, pin_b, enc_a, enc_b, counts_per_rev=960, freq=1000):
        self.pa = PWM(Pin(pin_a), freq=freq, duty_u16=0)
        self.pb = PWM(Pin(pin_b), freq=freq, duty_u16=0)
        self.ea = Pin(enc_a, Pin.IN, Pin.PULL_UP)
        self.eb = Pin(enc_b, Pin.IN, Pin.PULL_UP)
        self.cpr = counts_per_rev
        self.count = 0
        self.ea.irq(trigger=Pin.IRQ_RISING, handler=self._on_edge)

    def _on_edge(self, pin):
        # On each rising edge of A, B tells us which way the shaft is turning.
        if self.eb.value():
            self.count -= 1
        else:
            self.count += 1

    def drive(self, speed):
        """speed: -100..100 (% PWM). Sign = direction."""
        speed = max(-100, min(100, speed))
        duty = int(abs(speed) * 655.35)
        if speed > 0:
            self.pa.duty_u16(duty)
            self.pb.duty_u16(0)
        elif speed < 0:
            self.pa.duty_u16(0)
            self.pb.duty_u16(duty)
        else:
            self.stop()

    def stop(self):
        self.pa.duty_u16(0)
        self.pb.duty_u16(0)

    def rotate_deg(self, degrees, max_speed=60, min_speed=30, kp=1.5, timeout_ms=3000):
        """Turn the output shaft by `degrees` (sign = direction) using
        proportional feedback from the encoder. Returns the counts actually moved."""
        target = abs(degrees) / 360 * self.cpr
        direction = 1 if degrees >= 0 else -1
        start = self.count
        t0 = time.ticks_ms()
        while True:
            moved = abs(self.count - start)
            error = target - moved
            if error <= 0:
                break
            if time.ticks_diff(time.ticks_ms(), t0) > timeout_ms:
                print("Motor timeout: moved %d of %d counts - check encoder wiring/power"
                      % (moved, target))
                break
            speed = min(max_speed, max(min_speed, kp * error))   # P control
            self.drive(direction * speed)
            time.sleep_ms(5)
        self.stop()
        return abs(self.count - start)
