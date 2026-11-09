# calibrate.py  (V3 - straddling steering sensors + middle color sensor)
# Run this from Thonny (robot plugged in by USB, motors don't move).
# The white LED turns on automatically (robot_hw.ILLUM_LED_PIN).
# Saves everything to calib.json on the ESP32.
#
# Recalibrate whenever the lighting, LED, surface, or sensor height changes
# (definitely at the demo location).

import time
from robot_hw import Robot
import sensing

robot = Robot()
N_AVG = 12
SIDES = ("left", "right", "color")


def read_all():
    l, r = robot.read_sensors()
    return {"left": l, "right": r, "color": robot.read_color()}


def average(n=N_AVG):
    acc = {s: [0, 0, 0, 0] for s in SIDES}
    for _ in range(n):
        raw = read_all()
        for s in SIDES:
            for i in range(4):
                acc[s][i] += raw[s][i]
        time.sleep_ms(robot.sample_ms + 5)
    return {s: [x / n for x in acc[s]] for s in SIDES}


def signature(raw_c):
    """Color-sensor tape signature without the 'enough tape?' cutoff."""
    d = sensing.deficits(raw_c, cal["color"])
    t = max(1e-6, d[0] + d[1] + d[2])
    return (d[0] / t, d[1] / t, d[2] / t), t


def fmt(v):
    return "(" + ", ".join("%.3f" % x for x in v) + ")"


print("\n=== LINE FOLLOWER CALIBRATION (V3: 2 steering + 1 color sensor) ===")
print("Sensors:", robot.sensor_info)
robot.leds(0, 0, 0)   # NeoPixels OFF so they don't tint the readings

# ---------- 1. sweep across the tape ----------
input("\nSTEP 1: Set the robot on the track (away from color patches).\n"
      "Press Enter, then for 8 seconds SLOWLY slide the robot sideways back\n"
      "and forth across the black tape, far enough that ALL THREE sensors pass\n"
      "fully over the tape and fully over white. Keep it flat. [Enter] ")
mx = {s: [0, 0, 0, 0] for s in SIDES}
mn_w = {s: 65535 for s in SIDES}
t_end = time.ticks_add(time.ticks_ms(), 8000)
while time.ticks_diff(t_end, time.ticks_ms()) > 0:
    raw = read_all()
    for s in SIDES:
        for i in range(4):
            if raw[s][i] > mx[s][i]:
                mx[s][i] = raw[s][i]
        if raw[s][3] < mn_w[s]:
            mn_w[s] = raw[s][3]
    time.sleep_ms(robot.sample_ms + 2)
robot.tone(1500, 80)

cal = {}
for s in SIDES:
    w_white, w_black = mx[s][3], mn_w[s]
    cal[s] = {"w_white": w_white, "w_black": w_black, "rgb_white": mx[s][:3]}
    ratio = w_white / max(1, w_black)
    print("  %-5s sensor: white W=%d  black W=%d  (contrast %.2fx, want > 3x)"
          % (s, w_white, w_black, ratio))
    if ratio < 2.0:
        print("  !! LOW CONTRAST on %s sensor: it can barely tell black from white.\n"
              "     Lower it to ~3-5 mm, put a black tube/shroud around it, and make\n"
              "     sure the LED lights the floor but can't shine straight into it." % s)

# ---------- 2. centered on the line ----------
input("\nSTEP 2: Put the robot centered on a STRAIGHT piece of black line:\n"
      "left & right sensors straddling the tape edges, middle sensor over\n"
      "the middle of the tape. [Enter] ")
a = average()
Ln = sensing.brightness(a["left"], cal["left"])
Rn = sensing.brightness(a["right"], cal["right"])
Cn = sensing.brightness(a["color"], cal["color"])
cal["center_offset"] = Ln - Rn
sig, amount = signature(a["color"])
cal["line_chroma"] = sig
cal["tape_min"] = 0.4 * amount   # less darkening than this = "no tape under it"
robot.tone(1500, 80)
print("  left=%.2f  right=%.2f  -> center offset %.3f (subtracted from error)"
      % (Ln, Rn, cal["center_offset"]))
print("  middle=%.2f (want ~0.0, black)  black-line signature %s, tape amount %.2f"
      % (Cn, fmt(sig), amount))
if abs(cal["center_offset"]) > 0.3:
    print("  !! Steering sensors read very differently while centered. Check they're"
          " at the same height, evenly spaced around the tape, and equally lit.")
if Ln > 0.9 and Rn > 0.9:
    print("  !! Both steering sensors look white while centered: they may be too"
          " far apart or too high to see the tape edges.")
if Cn > 0.3:
    print("  !! The middle sensor isn't fully over the tape. Center it on the tape.")
if amount < 0.3:
    print("  !! The middle sensor hardly sees the tape (amount < 0.3). Fix the"
          " optics (see step 1) before trusting color detection.")

# ---------- 3. color patches ----------
cal["colors"] = {}
for name in sensing.COLORS:
    input("\nSTEP 3: Put the robot so the MIDDLE sensor is directly over the %s\n"
          "patch. [Enter] " % name)
    a = average()
    sig, amount = signature(a["color"])
    cal["colors"][name] = sig
    robot.tone(1500, 80)
    print("  %s signature %s, distance from black line %.3f"
          % (name, fmt(sig), sensing.dist(sig, cal["line_chroma"])))
    if amount < cal["tape_min"]:
        print("  !! This patch barely darkens the sensor, so it may not be detected."
              " (Very light tape? More light usually helps.)")

# ---------- how separable are the references? ----------
refs = [("LINE", cal["line_chroma"])] + [(n, cal["colors"][n]) for n in sensing.COLORS]
closest, pair = 99.0, None
for i in range(len(refs)):
    for j in range(i + 1, len(refs)):
        d = sensing.dist(refs[i][1], refs[j][1])
        if d < closest:
            closest, pair = d, (refs[i][0], refs[j][0])
cal["color_max_dist"] = min(0.25, max(0.02, 0.5 * closest))
print("\nClosest pair: %s vs %s, distance %.3f  (want > 0.06)" % (pair[0], pair[1], closest))
print("Match radius set to %.3f" % cal["color_max_dist"])
if closest < 0.06:
    print("  !! %s and %s look almost the same to the sensor. Improve the optics\n"
          "     (shroud, lower sensor, cool-white LED) and recalibrate." % pair)

sensing.save(cal)
robot.tone(1047, 100)
robot.tone(1319, 100)
robot.tone(1568, 200)
print("\nSaved to %s. Next: run monitor.py to check, then main.py." % sensing.CAL_FILE)
