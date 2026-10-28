# main.py - Phone-jail desktop pet (ME-35 midterm). Runs automatically on boot.
#
# State machine:
#   IDLE        tray empty, eyes off, display "-"
#   SET_TIMER   phone detected -> servo locks it, eyes blink; joystick up/down
#               picks 1-9 (x10 min), click starts the timer
#   RUNNING     countdown on the 7-segment display, eyes "watching"
#   RELEASE     time's up -> servo unlocks, celebration, candy tray opens 30 deg
#               for 5 s then closes
#   WAIT_REMOVE wait for the phone to be picked up before re-arming
import time
from machine import Pin, I2C

import config as C
import sounds
from sevenseg import SevenSeg
from veml6040 import VEML6040
from joystick import Joystick
from encoder_motor import EncoderMotor
from servo import Servo


# ---------------------------------------------------------------- helpers
class Eyes:
    def __init__(self, left_pin, right_pin):
        self.left = Pin(left_pin, Pin.OUT, value=0)
        self.right = Pin(right_pin, Pin.OUT, value=0)

    def set(self, left, right):
        self.left.value(1 if left else 0)
        self.right.value(1 if right else 0)

    def off(self):
        self.set(0, 0)


class PhoneDetector:
    """Phone present = the color sensor is covered (light level drops a lot)
    and stays that way for PHONE_CONFIRM_MS. Calibrates on the empty tray at boot."""

    def __init__(self, sensor, ratio, confirm_ms):
        self.sensor = sensor
        self.ratio = ratio
        self.confirm_ms = confirm_ms
        self.calibrate()
        self.present = False
        self._pending_since = None

    def calibrate(self, samples=5):
        total = 0
        for _ in range(samples):
            total += self.sensor.brightness()
            time.sleep_ms(self.sensor.integration_ms)
        self.baseline = max(total / samples, 1)
        print("Empty-tray brightness:", int(self.baseline),
              "-> 'covered' below", int(self.baseline * self.ratio))
        if self.baseline < 200:
            print("WARNING: very dark - phone detection may be unreliable")

    def update(self):
        """Call every loop. Returns the debounced phone-present state."""
        raw = self.sensor.brightness() < self.baseline * self.ratio
        now = time.ticks_ms()
        if raw == self.present:
            self._pending_since = None
        elif self._pending_since is None:
            self._pending_since = now
        elif time.ticks_diff(now, self._pending_since) >= self.confirm_ms:
            self.present = raw
            self._pending_since = None
        return self.present


def step_ms():
    unit_ms = 1000 if C.TEST_MODE else 60000          # 1 "minute" = 1 s in test mode
    return C.MINUTES_PER_STEP * unit_ms


# ---------------------------------------------------------------- setup
seg = SevenSeg(C.SEG_PINS, C.SEG_DP_PIN, C.SEG_COMMON_ANODE)
eyes = Eyes(C.EYE_LEFT_PIN, C.EYE_RIGHT_PIN)
buzzer = sounds.Buzzer(C.BUZZER_PIN)
servo = Servo(C.SERVO_PIN, C.SERVO_MIN_US, C.SERVO_MAX_US, start_angle=C.SERVO_OPEN_ANGLE)
motor = EncoderMotor(C.MOTOR_A_PIN, C.MOTOR_B_PIN, C.ENC_A_PIN, C.ENC_B_PIN,
                     C.ENCODER_COUNTS_PER_REV)
print("Keep the tray EMPTY and the joystick centered - calibrating...")
seg.show("-")
joy = Joystick(C.JOY_X_PIN, C.JOY_Y_PIN, C.JOY_INVERT_Y, C.JOY_DEADZONE,
               C.JOY_CLICK_LEVEL, C.JOY_REPEAT_DELAY_MS, C.JOY_REPEAT_RATE_MS)
i2c = I2C(0, scl=Pin(C.I2C_SCL_PIN), sda=Pin(C.I2C_SDA_PIN), freq=100000)
phone = PhoneDetector(VEML6040(i2c), C.PHONE_COVER_RATIO, C.PHONE_CONFIRM_MS)


# ---------------------------------------------------------------- actions
def release_phone(with_candy):
    seg.show(0)
    servo.sweep(C.SERVO_OPEN_ANGLE)
    if not with_candy:
        eyes.off()
        buzzer.play(sounds.SAD)
        return
    eyes.set(1, 1)
    buzzer.play(sounds.FINISHED)
    tray = C.MOTOR_CCW_SIGN * C.TRAY_ANGLE_DEG
    motor.rotate_deg(tray, C.MOTOR_MAX_SPEED, C.MOTOR_MIN_SPEED, C.MOTOR_KP,
                     C.MOTOR_TIMEOUT_MS)                      # open (CCW)
    t_end = time.ticks_add(time.ticks_ms(), C.TRAY_OPEN_TIME_S * 1000)
    while time.ticks_diff(t_end, time.ticks_ms()) > 0:        # happy blinking
        on = (time.ticks_ms() // 150) % 2
        eyes.set(on, not on)
        time.sleep_ms(20)
    motor.rotate_deg(-tray, C.MOTOR_MAX_SPEED, C.MOTOR_MIN_SPEED, C.MOTOR_KP,
                     C.MOTOR_TIMEOUT_MS)                      # close
    eyes.set(1, 1)


# ---------------------------------------------------------------- main loop
def run():
    state = "IDLE"
    steps = C.DEFAULT_STEPS
    end_time = 0
    last_state = None
    print("Ready.")

    while True:
        now = time.ticks_ms()
        present = phone.update()

        if state == "IDLE":
            eyes.off()
            seg.show("-")
            if present:
                buzzer.play(sounds.PHONE_PLACED)
                servo.sweep(C.SERVO_LOCK_ANGLE)               # lock the phone in
                buzzer.play(sounds.LOCKED)
                steps = C.DEFAULT_STEPS
                seg.show(steps)
                joy.clicked()                                 # clear stale click
                state = "SET_TIMER"

        elif state == "SET_TIMER":
            blink = (now // 400) % 2                          # alternating eyes
            eyes.set(blink, not blink)
            d = joy.step()
            if d:
                new = max(C.MIN_STEPS, min(C.MAX_STEPS, steps + d))
                if new != steps:
                    steps = new
                    seg.show(steps)
                    buzzer.play(sounds.STEP)
            if joy.clicked():                                 # stick pressed in
                buzzer.play(sounds.TIMER_START)
                eyes.set(1, 1)
                for _ in range(3):                            # flash digit = "started"
                    seg.clear()
                    time.sleep_ms(150)
                    seg.show(steps)
                    time.sleep_ms(150)
                end_time = time.ticks_add(time.ticks_ms(), steps * step_ms())
                state = "RUNNING"

        elif state == "RUNNING":
            remaining = time.ticks_diff(end_time, now)
            if remaining <= 0:
                state = "RELEASE"
            else:
                digit = (remaining + step_ms() - 1) // step_ms()   # round up
                seg.show(digit)
                seg.set_dp((now // 500) % 2)                  # "alive" blink
                # eyes watch you, with a quick blink every 3 s
                eyes.set(*((0, 0) if now % 3000 < 150 else (1, 1)))
                joy.clicked()
                if C.EMERGENCY_HOLD_MS and joy.held_ms() >= C.EMERGENCY_HOLD_MS:
                    print("Emergency release")
                    release_phone(with_candy=False)
                    state = "WAIT_REMOVE"

        elif state == "RELEASE":
            seg.set_dp(False)
            release_phone(with_candy=True)
            state = "WAIT_REMOVE"

        elif state == "WAIT_REMOVE":
            seg.show(0)
            if not present:                                   # phone picked up
                state = "IDLE"

        if state != last_state:
            print("State:", state)
            last_state = state
        time.sleep_ms(20)


try:
    run()
finally:                                                      # Ctrl-C / Stop in Thonny
    motor.stop()
    buzzer.off()
    eyes.off()
    seg.clear()
