"""
SENDER (your arm). Save on your ESP32 as main.py, next to config.py and
onshape.py.

2-DOF planar arm: each hand-turned DC motor encoder sets the angle of one servo.
    Encoder 1 -> servo 1 (shoulder, D4)
    Encoder 2 -> servo 2 (elbow,    D5)
The servo angles are pushed to the Onshape assembly's revolute mates
(POST /matevalues), so the CAD model and your partner's arm follow along.

Hardware: ROBO ESP32, 2x Miuzel MG90S servos, 2x DC motors with
          DFRobot Encoder v2.0 used as input knobs (motors are not powered).

Networking runs in a background thread so the knobs stay responsive while
an HTTPS request (roughly 0.3-1 s each) is in flight.
"""

from machine import Pin, PWM
import math
import time
import _thread

import config
import onshape

# =====================================================================
# GEOMETRY  -- pivot to pivot, used only for the printed tip position
# =====================================================================
ARM1_LENGTH = 100.0   # shoulder shaft -> elbow shaft (mm)
ARM2_LENGTH = 100.0   # elbow shaft   -> pointer tip  (mm)

# =====================================================================
# PINS
# =====================================================================
SERVO1_PIN = 4            # shoulder servo (D4)
SERVO2_PIN = 5            # elbow servo    (D5)
ENC1_PINS = (39, 32)      # encoder driving servo 1 (A, B)
ENC2_PINS = (25, 26)      # encoder driving servo 2 (A, B)

# =====================================================================
# SERVO CALIBRATION
# =====================================================================
SERVO_MIN_US = 500        # pulse width at 0 deg   (MG90S ~500 us)
SERVO_MAX_US = 2500       # pulse width at 180 deg (MG90S ~2500 us)
SERVO_MIN_DEG = 0.0       # software travel limits
SERVO_MAX_DEG = 180.0

# Starting pose: both servos at their midpoint (reset every run).
HOME_SERVO1 = 90.0
HOME_SERVO2 = 90.0

# Used only for the printed tip position:
#   servo 1 reading when arm 1 points along +x
#   servo 2 reading when arm 2 is straight in line with arm 1
SHOULDER_OFFSET = 0.0
ELBOW_OFFSET = 90.0

# =====================================================================
# SERVO <-> ONSHAPE MATE MAPPING
# mate angle (deg) = DIR * (servo angle - SERVO_AT_MATE_ZERO)
# SERVO_AT_MATE_ZERO: servo reading when the CAD mate reads 0 deg.
# DIR: set to -1 if the CAD joint turns the opposite way to the real one.
# =====================================================================
SHOULDER_SERVO_AT_MATE_ZERO = 90.0
SHOULDER_DIR = 1
ELBOW_SERVO_AT_MATE_ZERO = 90.0
ELBOW_DIR = -1            # CAD elbow mate turns opposite to the real joint

# =====================================================================
# INPUT FEEL
# =====================================================================
# Servo degrees per encoder count. The encoder is on the motor shaft,
# before the gearbox, so it gives many counts per output turn: keep this
# small. Make one negative to reverse that knob.
DEG_PER_COUNT_1 = 0.05
DEG_PER_COUNT_2 = 0.05
LOOP_MS = 20              # 50 Hz update, matches the servo PWM frame
PRINT_MS = 250            # status print interval

# =====================================================================
# UPLINK
# =====================================================================
SEND_MS = 200             # at most one POST per this many ms
SEND_DEADBAND_DEG = 1.0   # skip the POST unless a joint moved this much


# =====================================================================
# ENCODER (quadrature, counts every edge on A and B = 4x resolution)
# CW: 00 -> 10 -> 11 -> 01 counts up, CCW counts down.
# =====================================================================
class QuadEncoder:
    # index = (old_state << 2) | new_state, state = (A << 1) | B
    _TABLE = (0, -1, 1, 0,
              1, 0, 0, -1,
              -1, 0, 0, 1,
              0, 1, -1, 0)

    def __init__(self, pin_a, pin_b):
        self.a = Pin(pin_a, Pin.IN)
        self.b = Pin(pin_b, Pin.IN)
        self.count = 0
        self._state = (self.a.value() << 1) | self.b.value()
        trig = Pin.IRQ_RISING | Pin.IRQ_FALLING
        self.a.irq(handler=self._isr, trigger=trig)
        self.b.irq(handler=self._isr, trigger=trig)

    def _isr(self, _pin):
        s = (self.a.value() << 1) | self.b.value()
        self.count += QuadEncoder._TABLE[(self._state << 2) | s]
        self._state = s

    def read(self):
        return self.count


# =====================================================================
# SERVO
# =====================================================================
class Servo:
    def __init__(self, pin):
        self.pwm = PWM(Pin(pin), freq=50, duty_u16=0)
        self.angle = None

    def write(self, deg):
        deg = max(SERVO_MIN_DEG, min(SERVO_MAX_DEG, deg))
        us = SERVO_MIN_US + (SERVO_MAX_US - SERVO_MIN_US) * deg / 180.0
        self.pwm.duty_ns(int(us * 1000))
        self.angle = deg

    def off(self):
        self.pwm.duty_u16(0)


# =====================================================================
# TIP POSITION (forward kinematics, for display only)
# tip = R(q1)*[L1, 0] + R(q1 + q2)*[L2, 0]
# =====================================================================
def tip_position(s1, s2):
    q1 = math.radians(s1 - SHOULDER_OFFSET)
    q2 = math.radians(s2 - ELBOW_OFFSET)
    x = ARM1_LENGTH * math.cos(q1) + ARM2_LENGTH * math.cos(q1 + q2)
    y = ARM1_LENGTH * math.sin(q1) + ARM2_LENGTH * math.sin(q1 + q2)
    return x, y


# =====================================================================
# UPLINK THREAD -- pushes the latest servo angles to Onshape
# =====================================================================
latest = [HOME_SERVO1, HOME_SERVO2]   # written by the control loop
running = [True]


JOINT_MIN_DEG = -90.0     # each joint's travel, in CAD mate degrees
JOINT_MAX_DEG = 90.0


def servo_to_mate_rad(servo_deg, at_zero, direction):
    deg = direction * (servo_deg - at_zero)
    deg = max(JOINT_MIN_DEG, min(JOINT_MAX_DEG, deg))
    return math.radians(deg)


def uplink_loop(shoulder_mate, elbow_mate):
    sent = None
    while running[0]:
        t0 = time.ticks_ms()
        s1, s2 = latest[0], latest[1]
        moved = (sent is None or
                 abs(s1 - sent[0]) >= SEND_DEADBAND_DEG or
                 abs(s2 - sent[1]) >= SEND_DEADBAND_DEG)
        if moved:
            try:
                onshape.set_mates([
                    onshape.entry(shoulder_mate, servo_to_mate_rad(
                        s1, SHOULDER_SERVO_AT_MATE_ZERO, SHOULDER_DIR)),
                    onshape.entry(elbow_mate, servo_to_mate_rad(
                        s2, ELBOW_SERVO_AT_MATE_ZERO, ELBOW_DIR)),
                ])
                sent = (s1, s2)
                print(">> Onshape: servo1=%.1f servo2=%.1f (%d ms)"
                      % (s1, s2, time.ticks_diff(time.ticks_ms(), t0)))
            except Exception as e:
                print("POST error:", e)
                time.sleep_ms(1000)   # back off, then retry
        wait = SEND_MS - time.ticks_diff(time.ticks_ms(), t0)
        if wait > 0:
            time.sleep_ms(wait)


def start_uplink():
    """Connect and find the mates. Returns False (local-only mode) on failure."""
    try:
        onshape.connect_wifi()
        mates = onshape.get_mates()
        onshape.print_mates(mates)
        shoulder = onshape.find_mate(mates, config.SHOULDER_MATE)
        elbow = onshape.find_mate(mates, config.ELBOW_MATE)
    except Exception as e:
        print("Onshape setup failed, running local only:", e)
        return False
    _thread.stack_size(16 * 1024)
    _thread.start_new_thread(uplink_loop, (shoulder, elbow))
    return True


# =====================================================================
# MAIN
# =====================================================================
def main():
    servo1 = Servo(SERVO1_PIN)
    servo2 = Servo(SERVO2_PIN)
    enc1 = QuadEncoder(*ENC1_PINS)
    enc2 = QuadEncoder(*ENC2_PINS)

    # Reset to the midpoint every run
    servo1.write(HOME_SERVO1)
    servo2.write(HOME_SERVO2)
    time.sleep_ms(500)
    print("set")
    tx, ty = tip_position(servo1.angle, servo2.angle)
    print("Home: servo1=%.1f  servo2=%.1f | tip x=%.1f y=%.1f mm"
          % (servo1.angle, servo2.angle, tx, ty))

    start_uplink()

    last_c1 = enc1.read()
    last_c2 = enc2.read()
    last_print = time.ticks_ms()

    try:
        while True:
            c1 = enc1.read()
            c2 = enc2.read()
            d1 = (c1 - last_c1) * DEG_PER_COUNT_1
            d2 = (c2 - last_c2) * DEG_PER_COUNT_2
            last_c1, last_c2 = c1, c2

            # Each knob nudges its own servo. Servo.write clamps to 0-180,
            # so turning past a limit does nothing and reversing responds
            # immediately.
            if d1:
                servo1.write(servo1.angle + d1)
            if d2:
                servo2.write(servo2.angle + d2)
            latest[0], latest[1] = servo1.angle, servo2.angle

            now = time.ticks_ms()
            if time.ticks_diff(now, last_print) >= PRINT_MS:
                last_print = now
                tx, ty = tip_position(servo1.angle, servo2.angle)
                print("servo1=%5.1f servo2=%5.1f | tip x=%6.1f y=%6.1f | enc %d %d"
                      % (servo1.angle, servo2.angle, tx, ty, c1, c2))

            time.sleep_ms(LOOP_MS)
    except KeyboardInterrupt:
        running[0] = False
        servo1.off()
        servo2.off()
        print("Stopped")


main()
