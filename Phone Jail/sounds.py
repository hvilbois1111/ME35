# sounds.py - the robot's voice on the Robo ESP32's on-board piezo buzzer.
import time
from machine import Pin, PWM

# (frequency Hz, duration ms); frequency 0 = rest
PHONE_PLACED = [(1319, 70), (1760, 70), (2349, 120)]           # happy "boo-bee-BEEP"
LOCKED = [(880, 60), (0, 40), (880, 60)]                       # "click-click"
STEP = [(2637, 25)]                                            # tiny tick per digit
TIMER_START = [(1047, 80), (1568, 80), (2093, 160)]            # "let's go"
FINISHED = [(1568, 100), (1976, 100), (2349, 100), (3136, 250),
            (0, 80), (2349, 90), (3136, 300)]                  # celebration
SAD = [(784, 180), (698, 180), (587, 400)]                     # emergency release


class Buzzer:
    def __init__(self, pin):
        self.pwm = PWM(Pin(pin), freq=1000, duty_u16=0)

    def tone(self, freq, ms, gap_ms=15):
        if freq:
            self.pwm.freq(freq)
            self.pwm.duty_u16(32768)
        time.sleep_ms(ms)
        self.pwm.duty_u16(0)
        time.sleep_ms(gap_ms)

    def play(self, notes):
        for freq, ms in notes:
            self.tone(freq, ms)

    def off(self):
        self.pwm.duty_u16(0)
