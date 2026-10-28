# hardware_test.py - check each part on its own BEFORE running main.py.
# In Thonny: open this file and press Run. It walks through every part.
# Or run one test from the shell, e.g.:  import hardware_test; hardware_test.joystick()
import time
from machine import Pin, I2C
import config as C


def wait(msg):
    input("\n>>> " + msg + "  [press Enter]")


def display():
    from sevenseg import SevenSeg
    seg = SevenSeg(C.SEG_PINS, C.SEG_DP_PIN, C.SEG_COMMON_ANODE)
    print("7-seg: counting 0-9. Every digit should look right.")
    for n in range(10):
        seg.show(n)
        time.sleep_ms(600)
    seg.clear()


def eyes():
    left = Pin(C.EYE_LEFT_PIN, Pin.OUT)
    right = Pin(C.EYE_RIGHT_PIN, Pin.OUT)
    print("Eyes: LEFT, then RIGHT, then both, 3 times.")
    for _ in range(3):
        for l, r in ((1, 0), (0, 1), (1, 1), (0, 0)):
            left.value(l); right.value(r)
            time.sleep_ms(300)


def buzzer():
    import sounds
    b = sounds.Buzzer(C.BUZZER_PIN)
    print("Buzzer: placed / start / finished sounds (is the switch ON?)")
    for tune in (sounds.PHONE_PLACED, sounds.TIMER_START, sounds.FINISHED):
        b.play(tune)
        time.sleep_ms(400)


def servo():
    from servo import Servo
    s = Servo(C.SERVO_PIN, C.SERVO_MIN_US, C.SERVO_MAX_US, start_angle=C.SERVO_OPEN_ANGLE)
    print("Servo: OPEN -> LOCK -> OPEN. LOCK should be 90 deg counterclockwise.")
    time.sleep_ms(800)
    s.sweep(C.SERVO_LOCK_ANGLE)
    time.sleep_ms(1000)
    s.sweep(C.SERVO_OPEN_ANGLE)


def color(seconds=10):
    from veml6040 import VEML6040
    i2c = I2C(0, scl=Pin(C.I2C_SCL_PIN), sda=Pin(C.I2C_SDA_PIN), freq=100000)
    print("I2C devices found:", [hex(a) for a in i2c.scan()], "(want 0x10)")
    sensor = VEML6040(i2c)
    print("Color sensor: cover and uncover it. W should drop a lot when covered.")
    t_end = time.ticks_add(time.ticks_ms(), seconds * 1000)
    while time.ticks_diff(t_end, time.ticks_ms()) > 0:
        r, g, b, w = sensor.rgbw()
        print("R %5d  G %5d  B %5d  W %5d" % (r, g, b, w))
        time.sleep_ms(300)


def joystick(seconds=10):
    from joystick import Joystick
    print("Leave the stick centered for calibration...")
    j = Joystick(C.JOY_X_PIN, C.JOY_Y_PIN, C.JOY_INVERT_Y, C.JOY_DEADZONE,
                 C.JOY_CLICK_LEVEL)
    print("Center X=%d Y=%d. Now push UP, DOWN, and CLICK." % (j.cx, j.cy))
    print("If UP shows 'down', set JOY_INVERT_Y = True in config.py")
    names = {1: "up", -1: "down", 0: "-"}
    t_end = time.ticks_add(time.ticks_ms(), seconds * 1000)
    while time.ticks_diff(t_end, time.ticks_ms()) > 0:
        x, y = j.raw()
        print("X %5d  Y %5d  dir %-4s  click %s"
              % (x, y, names[j.vertical()], j.is_pressed()))
        time.sleep_ms(200)


def motor():
    from encoder_motor import EncoderMotor
    m = EncoderMotor(C.MOTOR_A_PIN, C.MOTOR_B_PIN, C.ENC_A_PIN, C.ENC_B_PIN,
                     C.ENCODER_COUNTS_PER_REV)
    target = C.TRAY_ANGLE_DEG / 360 * C.ENCODER_COUNTS_PER_REV
    print("Tray: open %d deg CCW, wait 2 s, close." % C.TRAY_ANGLE_DEG)
    moved = m.rotate_deg(C.MOTOR_CCW_SIGN * C.TRAY_ANGLE_DEG, C.MOTOR_MAX_SPEED,
                         C.MOTOR_MIN_SPEED, C.MOTOR_KP, C.MOTOR_TIMEOUT_MS)
    print("  opened %d counts (target %d)" % (moved, target))
    time.sleep_ms(2000)
    moved = m.rotate_deg(-C.MOTOR_CCW_SIGN * C.TRAY_ANGLE_DEG, C.MOTOR_MAX_SPEED,
                         C.MOTOR_MIN_SPEED, C.MOTOR_KP, C.MOTOR_TIMEOUT_MS)
    print("  closed %d counts (target %d)" % (moved, target))
    print("If it opened clockwise, flip the sign of MOTOR_CCW_SIGN in config.py")


def all_tests():
    for name, test in (("7-segment display", display), ("eye LEDs", eyes),
                       ("buzzer", buzzer), ("servo", servo),
                       ("color sensor", color), ("joystick", joystick),
                       ("DC motor + encoder", motor)):
        wait("Next: " + name)
        try:
            test()
        except Exception as e:
            print("  FAILED:", e)
    print("\nAll tests done.")


if __name__ == "__main__":
    all_tests()
