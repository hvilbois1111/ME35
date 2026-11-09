# monitor.py  (V2)
# Live readout after calibration (motors stay off, white LED on). Slide the
# robot by hand over the line and the patches and watch the numbers.
# NeoPixels light up with whatever color it thinks it sees.
# Stop with Thonny's Stop button.
#
# Check:  line slid to the RIGHT -> error goes POSITIVE
#         line slid to the LEFT  -> error goes NEGATIVE (side = LEFT)

import time
from robot_hw import Robot
import sensing

COLOR_MAX_DIST = 0.15   # keep the same as in main.py (upper cap on match radius)

robot = Robot()
cal = sensing.load()
tracker = sensing.LineTracker(cal)
LED = {"RED": (255, 0, 0), "GREEN": (0, 255, 0), "BLUE": (0, 0, 255)}
REFS = [("LINE", cal["line_chroma"])] + [(n, cal["colors"][n]) for n in sensing.COLORS]

print("match radius %.3f" % min(COLOR_MAX_DIST, cal.get("color_max_dist", 1)))
print("  L     R    r_off l_on  side   error   signature (r, g, b)    nearest (dist)  color")
while True:
    l, r = robot.read_sensors()
    L, R, r_off, l_on = sensing.line_terms(l, r, cal)
    err = tracker.error(l, r)
    side = "LEFT " if tracker.left_mode else "     "
    c = sensing.chroma(l, r, cal)
    col = sensing.classify(c, cal, COLOR_MAX_DIST)
    if c is None:
        sig, near = "   (no tape under R)    ", ""
    else:
        sig = "(%.3f, %.3f, %.3f)" % c
        name, d = min(((n, sensing.dist(c, ref)) for n, ref in REFS), key=lambda x: x[1])
        near = "%-5s (%.3f)" % (name, d)
    print("%.2f  %.2f  %.2f  %.2f  %s  %+.2f   %s   %-14s  %s"
          % (L, R, r_off, l_on, side, err, sig, near, col or "-"))
    if col:
        robot.leds(*LED[col])
    else:
        robot.leds(0, 0, 0)     # off when no color (keeps lighting like calibration)
    time.sleep_ms(150)
