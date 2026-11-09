# calibrate.py  (V2 - "color sensor centered" layout)
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


def signature(l, r):
    """Color-sensor tape signature without the 'enough tape?' cutoff."""
    raw = r if sensing.COLOR_SIDE == "right" else l
    d = sensing.deficits(raw, cal[sensing.COLOR_SIDE])
    t = max(1e-6, d[0] + d[1] + d[2])
    return (d[0] / t, d[1] / t, d[2] / t), t


def fmt(v):
    return "(" + ", ".join("%.3f" % x for x in v) + ")"


print("\n=== LINE FOLLOWER CALIBRATION (V2: right sensor over tape) ===")
print("Sensors:", robot.sensor_info)
robot.leds(0, 0, 0)   # NeoPixels OFF so they don't tint the readings

# ---------- 1. sweep across the tape ----------
input("\nSTEP 1: Set the robot on the track (away from color patches).\n"
      "Press Enter, then for 8 seconds SLOWLY slide the robot sideways back\n"
      "and forth across the black tape, far enough that BOTH sensors pass\n"
      "fully over the tape and fully over white. Keep it flat. [Enter] ")
mx = {"left": [0, 0, 0, 0], "right": [0, 0, 0, 0]}
mn_w = {"left": 65535, "right": 65535}
t_end = time.ticks_add(time.ticks_ms(), 8000)
while time.ticks_diff(t_end, time.ticks_ms()) > 0:
    l, r = robot.read_sensors()
    for side, raw in (("left", l), ("right", r)):
        for i in range(4):
            if raw[i] > mx[side][i]:
                mx[side][i] = raw[i]
        if raw[3] < mn_w[side]:
            mn_w[side] = raw[3]
    time.sleep_ms(robot.sample_ms + 2)
robot.tone(1500, 80)

cal = {}
for side in ("left", "right"):
    w_white, w_black = mx[side][3], mn_w[side]
    cal[side] = {"w_white": w_white, "w_black": w_black,
                 "rgb_white": mx[side][:3]}
    ratio = w_white / max(1, w_black)
    print("  %-5s sensor: white W=%d  black W=%d  (contrast %.2fx, want > 3x)"
          % (side, w_white, w_black, ratio))
    if ratio < 2.0:
        print("  !! LOW CONTRAST on %s sensor: it can barely tell black from white.\n"
              "     Lower it to ~3-5 mm, put a black tube/shroud around it, and make\n"
              "     sure the LED lights the floor but can't shine straight into it." % side)

# ---------- 2. centered on the line ----------
input("\nSTEP 2: Put the robot on a STRAIGHT piece of line with the RIGHT sensor\n"
      "directly over the MIDDLE of the tape and the LEFT sensor over white. [Enter] ")
l, r = average()
Ln = sensing.brightness(l, cal["left"])
Rn = sensing.brightness(r, cal["right"])
cal["r_center"] = Rn            # right sensor brightness when centered (~0)
cal["dl_center"] = 1.0 - Ln     # left sensor darkness when centered (~0)
sig, amount = signature(l, r)
cal["line_chroma"] = sig
cal["tape_min"] = 0.4 * amount  # less darkening than this = "no tape in view"
robot.tone(1500, 80)
print("  left=%.2f (want ~1.0, white)   right=%.2f (want ~0.0, black)" % (Ln, Rn))
print("  black-line signature %s, tape amount %.2f" % (fmt(sig), amount))
if Rn > 0.3:
    print("  !! RIGHT sensor isn't fully over the tape. Center it over the tape"
          " (or lower it so it sees a smaller spot).")
if Ln < 0.8:
    print("  !! LEFT sensor already sees some tape. Move it a little further left"
          " so it sits over white.")
if amount < 0.3:
    print("  !! The right sensor hardly sees the tape (amount < 0.3). Fix the"
          " optics (see step 1) before trusting color detection.")

# ---------- 3. color patches ----------
cal["colors"] = {}
for name in sensing.COLORS:
    input("\nSTEP 3: Put the robot with the RIGHT sensor directly over the middle\n"
          "of the %s patch. [Enter] " % name)
    l, r = average()
    sig, amount = signature(l, r)
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
