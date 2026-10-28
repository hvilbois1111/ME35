# main.py
# Two-sensor PID line follower with RED / GREEN / BLUE patch maneuvers.
# Runs automatically on boot. Press button A (GPIO34) to start,
# button B (GPIO35) to stop.  Needs calib.json (run calibrate.py first).

import time
from robot_hw import Robot
import sensing

# ================= TUNING =================
BASE_SPEED = 0.35        # 0..1 forward speed on straights (start slow)
KP = 0.5                 # steering per unit error
KI = 0.0                 # leave at 0 unless it sits off-center on long curves
KD = 0.02                # damps wobble (too high = jittery spinning in place)
I_LIMIT = 0.5            # anti-windup clamp on the integral

LOST_THRESHOLD = 0.85    # both sensors brighter than this = line lost
SEARCH_FAST = 0.55       # outer wheel while searching for a lost line
SEARCH_SLOW = -0.25      # inner wheel while searching (negative = reverse)
LOST_TIMEOUT_MS = 3000   # give up and stop after this long without the line

COLOR_MAX_DIST = 0.15    # reject color matches farther than this from calibration
COLOR_CONFIRM = 2        # consecutive reads that must agree before acting
COLOR_COOLDOWN_MS = 1500 # ignore colors this long after a maneuver

SPIN_SPEED = 0.6         # RED maneuver spin speed
SPIN_360_MS = 1600       # approx. time for one full turn at SPIN_SPEED (tune!)
# ==========================================

LED = {"RED": (255, 0, 0), "GREEN": (0, 255, 0), "BLUE": (0, 0, 255)}


# ---------------- station hook (ESP-NOW goes here later) ----------------
def notify_station(color):
    print("COLOR DETECTED:", color)
    # TODO: send `color` to the station ESP32 with ESP-NOW and wait for ACK


# ---------------- maneuvers ----------------
def maneuver_red(robot, cal):
    """Spin 360 degrees in place, then stop when the sensors find the line/patch."""
    robot.leds(*LED["RED"])
    robot.tone(880, 120)
    robot.drive(SPIN_SPEED, -SPIN_SPEED)
    t0 = time.ticks_ms()
    time.sleep_ms(int(SPIN_360_MS * 0.75))      # most of the turn blind
    # finish the turn: stop when a sensor sees dark tape or the red patch again
    while time.ticks_diff(time.ticks_ms(), t0) < int(SPIN_360_MS * 1.5):
        l, r = robot.read_sensors()
        dark = (sensing.brightness(l, cal["left"]) < 0.5 or
                sensing.brightness(r, cal["right"]) < 0.5)
        red = sensing.classify(sensing.chroma(l, r, cal), cal, COLOR_MAX_DIST) == "RED"
        if dark or red:
            break
        time.sleep_ms(robot.sample_ms)
    robot.stop()
    robot.leds(0, 0, 0)


def maneuver_green(robot, cal):
    """Stop and play the 'Charge!' bugle call with green lights."""
    robot.leds(*LED["GREEN"])
    for f, ms in ((392, 150), (523, 150), (659, 150), (784, 300),
                  (659, 150), (784, 600)):
        robot.tone(f, ms, 30)
    robot.leds(0, 0, 0)


def maneuver_blue(robot, cal):
    """Stop and flash the two NeoPixels blue, alternating, with chirps."""
    for i in range(8):
        robot.leds(*LED["BLUE"], which=i % 2)
        robot.tone(1500 if i % 2 else 1800, 90, 60)
    robot.leds(0, 0, 0)


MANEUVERS = {"RED": maneuver_red, "GREEN": maneuver_green, "BLUE": maneuver_blue}


# ---------------- main follow loop ----------------
def follow(robot, cal):
    loop_ms = robot.sample_ms + 2       # a bit longer than one sensor reading
    integral = 0.0
    prev_err = None                     # None = no previous error yet (no D kick)
    last_side = 1                       # +1 = line was last to the right
    lost_since = None
    streak_color, streak = None, 0
    cooldown_until = time.ticks_ms()
    t_prev = time.ticks_ms()

    while True:
        t0 = time.ticks_ms()
        if robot.button_b():
            print("Stopped by button B")
            return

        raw_l, raw_r = robot.read_sensors()

        # ----- 1. color patches -----
        if time.ticks_diff(t0, cooldown_until) >= 0:
            col = sensing.classify(sensing.chroma(raw_l, raw_r, cal), cal, COLOR_MAX_DIST)
            if col is not None and col == streak_color:
                streak += 1
            else:
                streak_color, streak = col, (1 if col else 0)

            if streak >= COLOR_CONFIRM:
                robot.stop()
                notify_station(streak_color)
                MANEUVERS[streak_color](robot, cal)
                streak_color, streak = None, 0
                integral, prev_err = 0.0, None
                cooldown_until = time.ticks_add(time.ticks_ms(), COLOR_COOLDOWN_MS)
                t_prev = time.ticks_ms()
                continue

            if streak > 0:
                # probably on a patch: go straight & slow while confirming,
                # since colored tape confuses the brightness-based steering
                robot.drive(BASE_SPEED * 0.7, BASE_SPEED * 0.7)
                prev_err = None
                _pace(t0, loop_ms)
                continue

        # ----- 2. line position -----
        L = sensing.brightness(raw_l, cal["left"])
        R = sensing.brightness(raw_r, cal["right"])

        if L > LOST_THRESHOLD and R > LOST_THRESHOLD:
            # Both white: line slipped outside both sensors. Turn hard toward
            # the side it was last seen on.
            if lost_since is None:
                lost_since = t0
            elif time.ticks_diff(t0, lost_since) > LOST_TIMEOUT_MS:
                robot.stop()
                print("Line lost - stopping")
                for _ in range(3):
                    robot.tone(300, 200, 100)
                return
            if last_side > 0:
                robot.drive(SEARCH_FAST, SEARCH_SLOW)
            else:
                robot.drive(SEARCH_SLOW, SEARCH_FAST)
            integral = 0.0
            prev_err = float(last_side)
            t_prev = t0
            _pace(t0, loop_ms)
            continue
        lost_since = None

        # error > 0 : right sensor darker -> line is to the right
        error = (L - R) - cal["center_offset"]
        if abs(error) > 0.1:
            last_side = 1 if error > 0 else -1

        # ----- 3. PID -----
        # dt never smaller than one loop, so the first step after a start /
        # maneuver doesn't make a huge derivative spike
        dt = max(time.ticks_diff(t0, t_prev), loop_ms) / 1000
        t_prev = t0
        integral = max(-I_LIMIT, min(I_LIMIT, integral + error * dt))
        deriv = 0.0 if prev_err is None else (error - prev_err) / dt
        prev_err = error

        correction = KP * error + KI * integral + KD * deriv
        robot.drive(BASE_SPEED + correction, BASE_SPEED - correction)

        _pace(t0, loop_ms)


def _pace(t0, loop_ms):
    left = loop_ms - time.ticks_diff(time.ticks_ms(), t0)
    if left > 0:
        time.sleep_ms(left)


# ---------------- startup ----------------
def run():
    robot = Robot()
    try:
        cal = sensing.load()
    except OSError:
        print("No calib.json found - run calibrate.py first.")
        for _ in range(5):
            robot.leds(255, 0, 0)
            time.sleep_ms(200)
            robot.leds(0, 0, 0)
            time.sleep_ms(200)
        return

    try:
        while True:
            robot.stop()
            robot.leds(30, 30, 30)       # dim white = ready
            print("Ready. Press button A to start.")
            robot.wait_button_a()
            robot.leds(0, 0, 0)
            robot.tone(1000 + 50, 100)   # (avoid exactly 1000 Hz = motor PWM freq)
            time.sleep_ms(400)
            robot.tone(1568, 150)
            follow(robot, cal)
    finally:
        robot.stop()                     # always stop motors on error / Ctrl-C
        robot.leds(0, 0, 0)


run()
