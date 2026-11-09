# ROBOT (Cytron Robo ESP32 car)  ->  BLE peripheral / "Yeller"
#
# - Advertises as ROBOT_NAME and waits for the joystick controller.
# - Receives "x,y\n" (-100..100 each) and drives both motors with PWM,
#   so speed follows how far the stick is pushed.
# - Watches the floor with the VEML6040 color sensor on Grove 5. When it
#   crosses the black finish tape it plays a tune on the board's built-in
#   buzzer and sends "FINISH\n" back to the controller.
#
# Upload to this ESP32:  BLE_CEEO.py, veml6040.py, robot.py
# (save robot.py as main.py if you want it to run on power-up)

from BLE_CEEO import Yell
from machine import Pin, PWM, SoftI2C
import veml6040
import time

# ======================= SETTINGS =======================
ROBOT_NAME = "HVbot"        # MUST match controller.py, 8 characters max

# Motors (motor terminal 1 = right, motor terminal 2 = left)
RIGHT_PIN_A, RIGHT_PIN_B = 13, 12
LEFT_PIN_A,  LEFT_PIN_B  = 27, 14
RIGHT_INVERT = False        # flip if this wheel spins backwards on "forward"
LEFT_INVERT = False
PWM_FREQ = 20000            # Hz. 20 kHz is above hearing range, so no motor whine
                            # (the Robo ESP32 motor driver allows up to 20 kHz)
MIN_DUTY = 22000            # 0-65535: smallest duty that actually turns the wheels
TIMEOUT_MS = 500            # stop the motors if no command arrives this long

# Color sensor on Grove 5 = GPIO 33 / 32 (both wire orders are tried)
SENSOR_PINS = (33, 32)
DARK_RATIO = 0.5            # "black" = white-channel reading below 50% of the floor reading
REARM_RATIO = 0.8           # must see the floor again (above 80%) before it can trigger again
PRINT_SENSOR = False        # True = print readings so you can tune DARK_RATIO

# Built-in buzzer on the Robo ESP32 (the buzzer MUTE switch must be OFF to hear it)
BUZZER_PIN = 23

# White floor-light LED on Grove 3/4 (GPIO 25) from the line follower.
# Set to 25 if it's plugged in so the sensor sees steady light, else None.
ILLUM_LED_PIN = None
# ========================================================


# ---------------------------------------------------------------- motors
class Motor:
    # 2-pin motor terminal: PWM on one pin, the other pin low, sets the direction.
    def __init__(self, pin_a, pin_b, invert=False):
        self.a = PWM(Pin(pin_a), freq=PWM_FREQ)
        self.b = PWM(Pin(pin_b), freq=PWM_FREQ)
        self.invert = invert
        self.set(0)

    def set(self, speed):
        # speed: -100 (full reverse) ... 0 (stop) ... 100 (full forward)
        speed = max(-100, min(100, speed))
        if self.invert:
            speed = -speed
        duty = 0 if speed == 0 else MIN_DUTY + (65535 - MIN_DUTY) * abs(speed) // 100
        if speed > 0:
            self.a.duty_u16(duty)
            self.b.duty_u16(0)
        elif speed < 0:
            self.a.duty_u16(0)
            self.b.duty_u16(duty)
        else:
            self.a.duty_u16(0)
            self.b.duty_u16(0)


right = Motor(RIGHT_PIN_A, RIGHT_PIN_B, RIGHT_INVERT)
left = Motor(LEFT_PIN_A, LEFT_PIN_B, LEFT_INVERT)


def mix(x, y):
    # "Arcade drive": y = forward speed, x = how hard to turn.
    l = y + x
    r = y - x
    # Scale both down if either goes past 100 so the turn keeps its shape
    # (full forward + full right = left 100, right 0).
    m = max(abs(l), abs(r), 100)
    return l * 100 // m, r * 100 // m


def drive(x, y):
    l, r = mix(x, y)
    left.set(l)
    right.set(r)


def stop():
    left.set(0)
    right.set(0)


# ---------------------------------------------------------------- buzzer
FINISH_TUNE = [(1047, 100), (0, 30), (1319, 100), (0, 30), (1568, 200), (0, 80),
               (1047, 100), (0, 30), (1319, 100), (0, 30), (1568, 300), (0, 0)]


class Buzzer:
    # Plays a tune without blocking, so the robot keeps driving meanwhile.
    # Its PWM frequency is never the same as the motors', so it gets its own
    # PWM timer and changing notes can't disturb the motor PWM.
    def __init__(self, pin):
        self.pwm = PWM(Pin(pin), freq=2000)
        self.pwm.duty_u16(0)
        self.notes = []
        self.note_end = 0

    def play(self, notes):
        # notes: list of (frequency Hz, length ms); frequency 0 = silence
        self.notes = list(notes)
        self.note_end = time.ticks_ms()

    def update(self):
        # Call this often from the main loop.
        if not self.notes or time.ticks_diff(time.ticks_ms(), self.note_end) < 0:
            return
        freq, ms = self.notes.pop(0)
        if freq > 0:
            self.pwm.freq(freq)
            self.pwm.duty_u16(32768)
        else:
            self.pwm.duty_u16(0)
        self.note_end = time.ticks_add(time.ticks_ms(), ms)

    def off(self):
        self.notes = []
        self.pwm.duty_u16(0)


buzzer = Buzzer(BUZZER_PIN)


# ---------------------------------------------------------------- color sensor
VEML6040_ADDR = 0x10


def find_sensor():
    # Grove cables differ on which wire is SDA, so try both orders.
    p1, p2 = SENSOR_PINS
    for sda, scl in ((p1, p2), (p2, p1)):
        try:
            i2c = SoftI2C(sda=Pin(sda), scl=Pin(scl), freq=100000, timeout=1000)
            if VEML6040_ADDR in i2c.scan():
                sensor = veml6040.VEML6040(i2c)
                # The library default is 1280 ms per reading, far too slow to
                # catch a strip of tape while driving. 40 ms = 25 readings/s.
                sensor.set_integration_time(veml6040.IT_40MS)
                sensor.set_auto_mode()
                print("Color sensor found on Grove 5 (SDA=%d, SCL=%d)" % (sda, scl))
                return sensor
        except OSError:
            pass
    print("WARNING: color sensor not found on Grove 5 - finish line detection is off")
    return None


def read_white(sensor):
    try:
        return sensor.read_white()
    except OSError:
        return None


class FinishLine:
    # Learns how bright the white floor is, then reports one "finish" each
    # time the sensor goes dark (black tape) after seeing the floor again.
    def __init__(self, sensor):
        self.sensor = sensor
        self.floor = None
        self.armed = True
        if sensor:
            print("Calibrating floor... keep the robot on the white floor")
            time.sleep_ms(100)
            total, n = 0, 0
            for _ in range(10):
                w = read_white(sensor)
                if w is not None:
                    total += w
                    n += 1
                time.sleep_ms(45)
            if n:
                self.floor = max(1, total // n)
                print("Floor (white channel):", self.floor,
                      " finish triggers below", int(self.floor * DARK_RATIO))

    def check(self):
        # Returns True once when the robot crosses the tape.
        if not self.floor:
            return False
        w = read_white(self.sensor)
        if w is None:
            return False
        if PRINT_SENSOR:
            print("white:", w)
        if self.armed and w < self.floor * DARK_RATIO:
            self.armed = False
            return True
        if not self.armed and w > self.floor * REARM_RATIO:
            self.armed = True
        return False


# ---------------------------------------------------------------- BLE
cmd_x = 0
cmd_y = 0
last_msg_ms = time.ticks_ms()
buffer = b""


def on_data(data):
    # Data can arrive in pieces; a newline ends each message.
    global buffer, cmd_x, cmd_y, last_msg_ms
    buffer += data
    while b"\n" in buffer:
        line, buffer = buffer.split(b"\n", 1)
        try:
            xs, ys = line.decode().split(",")
            cmd_x = max(-100, min(100, int(xs)))
            cmd_y = max(-100, min(100, int(ys)))
            last_msg_ms = time.ticks_ms()
        except ValueError:
            pass               # ignore a garbled message
    if len(buffer) > 64:       # junk with no newline: throw it away
        buffer = b""


def main():
    global cmd_x, cmd_y
    stop()
    if ILLUM_LED_PIN is not None:
        Pin(ILLUM_LED_PIN, Pin.OUT).value(1)
        time.sleep_ms(20)
    finish = FinishLine(find_sensor())
    buzzer.play([(1500, 80), (0, 0)])   # short chirp = robot is ready

    robot = Yell(ROBOT_NAME, interval_us=30000, verbose=False)
    robot.callback = on_data
    try:
        while True:  # go back to advertising whenever the controller drops
            stop()
            print("Waiting for controller...")
            # connect_up() blocks while advertising, so finish the chirp first
            while buzzer.notes:
                buzzer.update()
                time.sleep_ms(5)
            if not robot.connect_up():
                continue

            print("Controller connected")
            cmd_x, cmd_y = 0, 0
            next_sensor_ms = time.ticks_ms()
            while robot.is_connected:
                # 1) drive (with failsafe)
                if time.ticks_diff(time.ticks_ms(), last_msg_ms) > TIMEOUT_MS:
                    stop()
                else:
                    drive(cmd_x, cmd_y)

                # 2) finish line, checked every 20 ms
                if time.ticks_diff(time.ticks_ms(), next_sensor_ms) >= 0:
                    next_sensor_ms = time.ticks_add(time.ticks_ms(), 20)
                    if finish.check():
                        print("FINISH LINE!")
                        buzzer.play(FINISH_TUNE)
                        try:
                            robot.send("FINISH\n")
                        except OSError:
                            pass

                buzzer.update()
                time.sleep_ms(5)

            print("Controller disconnected")
            buzzer.off()
    finally:
        stop()
        buzzer.off()
        robot.disconnect()


if __name__ == "__main__":
    main()
