# robot_hw.py
# Hardware layer for the Cytron Robo ESP32 line follower:
# motors, two VEML6040 color sensors, NeoPixels, buzzer, buttons.
# Pin numbers come from the Robo ESP32 datasheet.

from machine import Pin, PWM, SoftI2C
from neopixel import NeoPixel
import time
from veml6040 import VEML6040, ADDR

# ------------------------------------------------------------------
# PIN / WIRING CONFIG  (run hw_test.py to check these)
# ------------------------------------------------------------------
LEFT_MOTOR_PINS = (12, 13)     # motor terminal M1 (M1A=D12, M1B=D13)
RIGHT_MOTOR_PINS = (14, 27)    # motor terminal M2 (M2A=D14, M2B=D27)
LEFT_MOTOR_REVERSED = False    # flip if that wheel spins backward
RIGHT_MOTOR_REVERSED = False

LEFT_SENSOR_PORT = (21, 22)    # Grove port 2 (the board's I2C port)
RIGHT_SENSOR_PORT = (17, 16)   # Grove port 1 (used as a 2nd, software I2C bus)
# If you'd rather use another port for a sensor: Grove 3 = (26, 25),
# Grove 5 = (33, 32). Don't use ports 6/7 (GPIO 36/39 are input-only).

NEOPIXEL_PIN = 15
NUM_PIXELS = 2
BUZZER_PIN = 23                # buzzer mute switch must be OFF to hear it
BUTTON_A_PIN = 34              # start
BUTTON_B_PIN = 35              # stop
BUTTON_ACTIVE_LOW = True       # pressed reads 0 (check with hw_test.py)

MOTOR_PWM_FREQ = 1000          # Hz (driver max is 20 kHz)
MIN_DUTY = 0.30                # yellow TT motors stall below roughly this duty
SENSOR_IT_MS = 40              # sensor integration time: 40, 80, 160 ...
LED_BRIGHTNESS = 0.3           # 0..1, NeoPixels are very bright


# ------------------------------------------------------------------
class Motor:
    def __init__(self, pins, reversed=False):
        a, b = pins
        if reversed:
            a, b = b, a
        self.a = PWM(Pin(a), freq=MOTOR_PWM_FREQ)
        self.b = PWM(Pin(b), freq=MOTOR_PWM_FREQ)
        self.set(0)

    def set(self, speed):
        """speed from -1.0 (full reverse) to +1.0 (full forward).
        Non-zero speeds are mapped above MIN_DUTY so the motor actually turns."""
        speed = max(-1.0, min(1.0, speed))
        if abs(speed) < 0.02:
            self.a.duty_u16(0)          # both low = brake
            self.b.duty_u16(0)
            return
        duty = int((MIN_DUTY + abs(speed) * (1.0 - MIN_DUTY)) * 65535)
        if speed > 0:
            self.a.duty_u16(duty)
            self.b.duty_u16(0)
        else:
            self.a.duty_u16(0)
            self.b.duty_u16(duty)


def _find_sensor_bus(pins):
    """Open a software I2C bus on a Grove port. Tries both SDA/SCL orders
    so you don't have to worry about which Grove wire is which."""
    p1, p2 = pins
    for sda, scl in ((p1, p2), (p2, p1)):
        bus = SoftI2C(sda=Pin(sda), scl=Pin(scl), freq=100000)
        try:
            if ADDR in bus.scan():
                return bus, sda, scl
        except OSError:
            pass
    return None, None, None


class Robot:
    def __init__(self, need_sensors=True):
        self.left_motor = Motor(LEFT_MOTOR_PINS, LEFT_MOTOR_REVERSED)
        self.right_motor = Motor(RIGHT_MOTOR_PINS, RIGHT_MOTOR_REVERSED)

        self.np = NeoPixel(Pin(NEOPIXEL_PIN, Pin.OUT), NUM_PIXELS)
        # Buzzer starts at a different freq than the motors so it gets
        # its own PWM timer (changing a shared timer would change motor PWM).
        self.buzzer = PWM(Pin(BUZZER_PIN), freq=2000)
        self.buzzer.duty_u16(0)

        self.btn_a = Pin(BUTTON_A_PIN, Pin.IN)
        self.btn_b = Pin(BUTTON_B_PIN, Pin.IN)

        self.sample_ms = SENSOR_IT_MS
        self.sensor_l = self.sensor_r = None
        self.sensor_info = {}
        for side, pins in (("left", LEFT_SENSOR_PORT), ("right", RIGHT_SENSOR_PORT)):
            bus, sda, scl = _find_sensor_bus(pins)
            if bus is None:
                self.sensor_info[side] = "NOT FOUND on pins %s" % (pins,)
                if need_sensors:
                    self.stop()
                    raise OSError("%s color sensor not found on pins %s" % (side, pins))
                continue
            s = VEML6040(bus, SENSOR_IT_MS)
            self.sensor_info[side] = "found (SDA=%d, SCL=%d)" % (sda, scl)
            if side == "left":
                self.sensor_l = s
            else:
                self.sensor_r = s

        self.leds(0, 0, 0)

    # ---------- motors ----------
    def drive(self, left, right):
        self.left_motor.set(left)
        self.right_motor.set(right)

    def stop(self):
        self.drive(0, 0)

    # ---------- sensors ----------
    def read_sensors(self):
        """Returns ((R,G,B,W) left, (R,G,B,W) right) raw counts."""
        return self.sensor_l.rgbw(), self.sensor_r.rgbw()

    # ---------- lights / sound ----------
    def leds(self, r, g, b, which=None):
        k = LED_BRIGHTNESS
        c = (int(r * k), int(g * k), int(b * k))
        for i in range(NUM_PIXELS):
            if which is None or which == i:
                self.np[i] = c
            elif which is not None:
                self.np[i] = (0, 0, 0)
        self.np.write()

    def tone(self, freq, ms, gap_ms=20):
        if freq > 0:
            self.buzzer.freq(int(freq))
            self.buzzer.duty_u16(20000)
        time.sleep_ms(ms)
        self.buzzer.duty_u16(0)
        time.sleep_ms(gap_ms)

    # ---------- buttons ----------
    def _pressed(self, pin):
        return (pin.value() == 0) if BUTTON_ACTIVE_LOW else (pin.value() == 1)

    def button_a(self):
        return self._pressed(self.btn_a)

    def button_b(self):
        return self._pressed(self.btn_b)

    def wait_button_a(self):
        while not self.button_a():
            time.sleep_ms(10)
        while self.button_a():          # wait for release
            time.sleep_ms(10)
