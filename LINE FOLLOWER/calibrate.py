# calibrate.py
# Run this from Thonny (robot plugged in by USB, motors don't move).
# It walks you through measuring white, black, the line, and the three
# color patches, then saves everything to calib.json on the ESP32.
#
# Recalibrate whenever the lighting, surface, or sensor height changes
# (definitely at the demo location).

import time
from robot_hw import Robot
import sensing

robot = Robot()
N_AVG = 12


def average(n=N_AVG):
    acc_l = [0, 0, 0, 0]
    acc_r = [0, 0, 0, 0]
    for _ in range(n):
        l, r = robot.read_sensors()
        for i in range(4):
            acc_l[i] += l[i]
            acc_r[i] += r[i]
        time.sleep_ms(robot.sample_ms + 5)
    return [x / n for x in acc_l], [x / n for x in acc_r]


def fmt(v):
    return "(" + ", ".join("%.3f" % x for x in v) + ")"


print("\n=== LINE FOLLOWER CALIBRATION ===")
print("Sensors:", robot.sensor_info)

# ---------- 1. sweep across the tape ----------
input("\nSTEP 1: Set the robot on the track (away from color patches).\n"
      "Press Enter, then for 6 seconds SLOWLY slide the robot sideways back\n"
      "and forth across the black tape so EACH sensor passes over pure white\n"
      "and pure black. Keep it flat on its wheels. [Enter] ")
robot.leds(255, 255, 0)
mx = {"left": [0, 0, 0, 0], "right": [0, 0, 0, 0]}
mn_w = {"left": 65535, "right": 65535}
t_end = time.ticks_add(time.ticks_ms(), 6000)
while time.ticks_diff(t_end, time.ticks_ms()) > 0:
    l, r = robot.read_sensors()
    for side, raw in (("left", l), ("right", r)):
        for i in range(4):
            if raw[i] > mx[side][i]:
                mx[side][i] = raw[i]
        if raw[3] < mn_w[side]:
            mn_w[side] = raw[3]
    time.sleep_ms(robot.sample_ms + 2)
robot.leds(0, 0, 0)
robot.tone(1500, 80)

cal = {}
for side in ("left", "right"):
    w_white, w_black = mx[side][3], mn_w[side]
    cal[side] = {"w_white": w_white, "w_black": w_black,
                 "rgb_white": mx[side][:3]}
    ratio = w_white / max(1, w_black)
    print("  %-5s sensor: white W=%d  black W=%d  (contrast %.1fx)"
          % (side, w_white, w_black, ratio))
    if w_white - w_black < 40 or ratio < 1.5:
        print("  !! LOW CONTRAST on %s sensor. Add light under the robot,"
              " lower the sensor, or use a longer SENSOR_IT_MS." % side)

# ---------- 2. centered on the line ----------
input("\nSTEP 2: Put the robot centered on a STRAIGHT piece of black line,\n"
      "sensors straddling the tape like when it drives. [Enter] ")
l, r = average()
Ln = sensing.brightness(l, cal["left"])
Rn = sensing.brightness(r, cal["right"])
cal["center_offset"] = Ln - Rn
cal["line_chroma"] = sensing.chroma(l, r, cal)
robot.tone(1500, 80)
print("  left=%.2f  right=%.2f  -> center offset %.3f (subtracted from error)"
      % (Ln, Rn, cal["center_offset"]))
if abs(cal["center_offset"]) > 0.3:
    print("  !! Sensors read very differently while centered. Check that they're"
          " at the same height and evenly spaced around the tape.")
if Ln > 0.9 and Rn > 0.9:
    print("  !! Both sensors look white while centered: they may be too far"
          " apart or too high to see the tape edges.")

# ---------- 3. color patches ----------
cal["colors"] = {}
for name in sensing.COLORS:
    input("\nSTEP 3: Put the robot centered on the %s patch, in normal driving\n"
          "position. [Enter] " % name)
    l, r = average()
    c = sensing.chroma(l, r, cal)
    cal["colors"][name] = c
    robot.tone(1500, 80)
    print("  %s chroma %s, distance from plain white %.3f"
          % (name, fmt(c), sensing.dist(c, sensing.NEUTRAL)))

# ---------- check how separable the references are ----------
refs = [("NONE", sensing.NEUTRAL), ("LINE", cal["line_chroma"])] + \
       [(n, cal["colors"][n]) for n in sensing.COLORS]
closest = 99
pair = None
for i in range(len(refs)):
    for j in range(i + 1, len(refs)):
        if refs[i][0] in sensing.COLORS or refs[j][0] in sensing.COLORS:
            d = sensing.dist(refs[i][1], refs[j][1])
            if d < closest:
                closest, pair = d, (refs[i][0], refs[j][0])
print("\nClosest pair: %s vs %s, distance %.3f" % (pair[0], pair[1], closest))
if closest < 0.03:
    print("  !! These are hard to tell apart. Better lighting usually fixes it.")

sensing.save(cal)
robot.tone(1047, 100)
robot.tone(1319, 100)
robot.tone(1568, 200)
print("\nSaved to %s. Next: run monitor.py to check, then main.py." % sensing.CAL_FILE)
