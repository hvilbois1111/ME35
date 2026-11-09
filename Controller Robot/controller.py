# CONTROLLER (joystick ESP32)  ->  BLE central / "Listener"
#
# - Reads a 2-axis analog joystick and sends "x,y\n" to the robot every 50 ms.
#     x = -100 (full left)  ... 0 ... +100 (full right)
#     y = -100 (full back)  ... 0 ... +100 (full forward)
# - When the robot sends "FINISH\n" (it crossed the black tape), this board
#   beeps and flashes its NeoPixels to celebrate.
#
# Upload to this ESP32:  BLE_CEEO.py, controller.py
# (save controller.py as main.py if you want it to run on power-up)

from BLE_CEEO import Listen
from machine import ADC, Pin, PWM
import time

# ======================= SETTINGS =======================
ROBOT_NAME = "HVbot"     # MUST match ROBOT_NAME in robot.py, 8 characters max
PIN_X = 32               # joystick VRx -> ADC1 pins only (32-39)
PIN_Y = 33               # joystick VRy
INVERT_X = False         # flip if left/right come out backwards
INVERT_Y = False         # flip if pushing forward gives a negative y
DEADZONE = 8             # % of travel near center that counts as 0
SEND_PERIOD_MS = 50      # 20 messages per second
PRINT_VALUES = False     # True = print x,y so you can check your wiring

BUZZER_PIN = None        # GPIO of this board's buzzer (None = no sound)
USE_NEOPIXEL = True      # red = searching, green = connected, flashing = finish!
NEOPIXEL_PIN = 15
NEOPIXEL_COUNT = 2
# ========================================================

adc_x = ADC(Pin(PIN_X))
adc_y = ADC(Pin(PIN_Y))
adc_x.atten(ADC.ATTN_11DB)   # full 0-3.3 V range
adc_y.atten(ADC.ATTN_11DB)

np = None
if USE_NEOPIXEL:
    try:
        from neopixel import NeoPixel
        np = NeoPixel(Pin(NEOPIXEL_PIN), NEOPIXEL_COUNT)
    except Exception:
        np = None


def lights(color):
    if np:
        for i in range(NEOPIXEL_COUNT):
            np[i] = color
        np.write()


# ---------------------------------------------------------------- buzzer
class Beeper:
    # Beeps without blocking, so joystick commands keep flowing while it
    # plays (otherwise the robot's failsafe would stop the car).
    def __init__(self, pin, freq=2000):
        self.pwm = None
        if pin is not None:
            self.pwm = PWM(Pin(pin))
            self.pwm.freq(freq)
            self.pwm.duty_u16(0)
        self.steps = []
        self.step_end = 0

    def beep(self, count=3, on_ms=150, off_ms=100):
        self.steps = []
        for _ in range(count):
            self.steps.append((True, on_ms))
            self.steps.append((False, off_ms))
        self.step_end = time.ticks_ms()

    def busy(self):
        return len(self.steps) > 0

    def update(self):
        # Call this often from the main loop. Returns True while a beep is on.
        if not self.steps or time.ticks_diff(time.ticks_ms(), self.step_end) < 0:
            return None
        on, ms = self.steps.pop(0)
        if self.pwm:
            self.pwm.duty_u16(32768 if on else 0)
        self.step_end = time.ticks_add(time.ticks_ms(), ms)
        return on

    def off(self):
        self.steps = []
        if self.pwm:
            self.pwm.duty_u16(0)


beeper = Beeper(BUZZER_PIN)


# ---------------------------------------------------------------- joystick
def calibrate(adc, samples=50):
    # Average the resting value. Don't touch the joystick while this runs.
    total = 0
    for _ in range(samples):
        total += adc.read_u16()
        time.sleep_ms(5)
    return total // samples


def to_percent(raw, center, invert):
    # Turn a 0-65535 reading into -100..100, centered on the resting value.
    # Each side of center is scaled on its own because the stick rarely
    # rests at exactly 32768.
    d = raw - center
    if d >= 0:
        p = d * 100 // max(1, 65535 - center)
    else:
        p = d * 100 // max(1, center)
    # Small wobble near center = 0; past the deadzone, ramp smoothly 0..100.
    if abs(p) <= DEADZONE:
        return 0
    sign = 1 if p > 0 else -1
    p = sign * (abs(p) - DEADZONE) * 100 // (100 - DEADZONE)
    p = max(-100, min(100, p))
    return -p if invert else p


# ---------------------------------------------------------------- BLE receive
buffer = b""
finish_flag = False


def on_data(data):
    # Messages from the robot (it only sends "FINISH\n").
    global buffer, finish_flag
    buffer += data
    while b"\n" in buffer:
        line, buffer = buffer.split(b"\n", 1)
        if line.strip() == b"FINISH":
            finish_flag = True
    if len(buffer) > 64:
        buffer = b""


def main():
    global finish_flag
    lights((10, 0, 0))
    if BUZZER_PIN is None:
        print("Note: BUZZER_PIN is None, so the controller won't beep")
    print("Calibrating joystick center... (hands off)")
    center_x = calibrate(adc_x)
    center_y = calibrate(adc_y)
    print("Center:", center_x, center_y)

    controller = Listen(ROBOT_NAME, verbose=False)
    controller.callback = on_data
    try:
        while True:  # keep reconnecting if the robot drops out
            lights((10, 0, 0))
            print("Looking for", ROBOT_NAME, "...")
            if not controller.connect_up():
                time.sleep_ms(500)
                continue

            print("Connected to robot")
            lights((0, 10, 0))
            next_send = time.ticks_ms()
            while controller.is_connected:
                # 1) celebrate if the robot crossed the finish line
                if finish_flag:
                    finish_flag = False
                    print("Robot crossed the finish line!")
                    beeper.beep(count=5, on_ms=120, off_ms=80)

                state = beeper.update()
                if state is True:
                    lights((10, 0, 10))      # purple flash with each beep
                elif state is False:
                    lights((0, 0, 0))
                    if not beeper.busy():
                        lights((0, 10, 0))   # back to "connected" green

                # 2) send the joystick position every SEND_PERIOD_MS
                if time.ticks_diff(time.ticks_ms(), next_send) >= 0:
                    next_send = time.ticks_add(time.ticks_ms(), SEND_PERIOD_MS)
                    x = to_percent(adc_x.read_u16(), center_x, INVERT_X)
                    y = to_percent(adc_y.read_u16(), center_y, INVERT_Y)
                    msg = "{},{}\n".format(x, y)   # at most 10 bytes = one packet
                    if PRINT_VALUES:
                        print(msg, end="")
                    try:
                        controller.send(msg)
                    except OSError:
                        pass   # link dropped mid-send; the loop will notice

                time.sleep_ms(5)

            print("Lost connection")
            beeper.off()
    finally:
        lights((0, 0, 0))
        beeper.off()
        controller.disconnect()


if __name__ == "__main__":
    main()
