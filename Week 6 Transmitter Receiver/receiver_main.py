"""
RECEIVER (your partner's arm). Save on that ESP32 as main.py, next to
config.py and onshape.py.

Polls the Onshape assembly's revolute mates (GET /matevalues) and drives
two servos to match. A background thread does the polling; the main loop
eases each servo toward the latest target so motion looks continuous even
though new angles only arrive a couple of times per second.
"""

from machine import Pin, PWM
import math
import time
import _thread

import config
import onshape

# =====================================================================
# PINS / SERVOS  (change to match your partner's wiring)
# =====================================================================
SERVO1_PIN = 4            # shoulder
SERVO2_PIN = 5            # elbow
SERVO_MIN_US = 500
SERVO_MAX_US = 2500
SERVO_MIN_DEG = 0.0
SERVO_MAX_DEG = 180.0
HOME_DEG = 90.0

# =====================================================================
# ONSHAPE MATE -> SERVO MAPPING
# servo angle = SERVO_AT_MATE_ZERO + DIR * mate angle (deg)
# Use the same SERVO_AT_MATE_ZERO / DIR idea as the sender, but calibrated
# for THIS arm's servo mounting.
# =====================================================================
SHOULDER_SERVO_AT_MATE_ZERO = 90.0
SHOULDER_DIR = 1
ELBOW_SERVO_AT_MATE_ZERO = 90.0
ELBOW_DIR = -1

# =====================================================================
# TIMING
# =====================================================================
POLL_MS = 250             # at most one GET per this many ms
LOOP_MS = 20              # servo update rate (50 Hz)
MAX_DEG_PER_S = 180.0     # how fast servos chase a new target


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


JOINT_MIN_DEG = -90.0     # each joint's travel, in CAD mate degrees
JOINT_MAX_DEG = 90.0


def mate_to_servo(rad, at_zero, direction):
    deg = math.degrees(rad)
    deg = (deg + 180.0) % 360.0 - 180.0          # wrap to -180..180
    deg = max(JOINT_MIN_DEG, min(JOINT_MAX_DEG, deg))
    return at_zero + direction * deg


# =====================================================================
# DOWNLINK THREAD -- reads the mates from Onshape
# =====================================================================
target = [HOME_DEG, HOME_DEG]
running = [True]


def downlink_loop():
    while running[0]:
        t0 = time.ticks_ms()
        try:
            mates = onshape.get_mates()
            m1 = onshape.find_mate(mates, config.SHOULDER_MATE)
            m2 = onshape.find_mate(mates, config.ELBOW_MATE)
            t1 = mate_to_servo(m1["rotationZ"], SHOULDER_SERVO_AT_MATE_ZERO, SHOULDER_DIR)
            t2 = mate_to_servo(m2["rotationZ"], ELBOW_SERVO_AT_MATE_ZERO, ELBOW_DIR)
            if abs(t1 - target[0]) >= 0.5 or abs(t2 - target[1]) >= 0.5:
                print("<< Onshape: servo1=%.1f servo2=%.1f (%d ms)"
                      % (t1, t2, time.ticks_diff(time.ticks_ms(), t0)))
            target[0], target[1] = t1, t2
        except Exception as e:
            print("GET error:", e)
            time.sleep_ms(1000)
        wait = POLL_MS - time.ticks_diff(time.ticks_ms(), t0)
        if wait > 0:
            time.sleep_ms(wait)


def step_toward(servo, goal, max_step):
    err = goal - servo.angle
    if abs(err) <= max_step:
        servo.write(goal)
    else:
        servo.write(servo.angle + (max_step if err > 0 else -max_step))


def main():
    servo1 = Servo(SERVO1_PIN)
    servo2 = Servo(SERVO2_PIN)
    servo1.write(HOME_DEG)
    servo2.write(HOME_DEG)

    onshape.connect_wifi()
    mates = onshape.get_mates()
    onshape.print_mates(mates)
    onshape.find_mate(mates, config.SHOULDER_MATE)   # fail fast on bad names
    onshape.find_mate(mates, config.ELBOW_MATE)

    _thread.stack_size(16 * 1024)
    _thread.start_new_thread(downlink_loop, ())

    max_step = MAX_DEG_PER_S * LOOP_MS / 1000.0
    try:
        while True:
            step_toward(servo1, target[0], max_step)
            step_toward(servo2, target[1], max_step)
            time.sleep_ms(LOOP_MS)
    except KeyboardInterrupt:
        running[0] = False
        servo1.off()
        servo2.off()
        print("Stopped")


main()
