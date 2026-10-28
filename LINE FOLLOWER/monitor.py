# monitor.py
# Live readout after calibration (motors stay off). Move the robot by hand
# over the line and the patches and watch the numbers. NeoPixels light up
# with whatever color it currently thinks it sees. Stop with Thonny's Stop.

import time
from robot_hw import Robot
import sensing

COLOR_MAX_DIST = 0.15   # keep the same as in main.py

robot = Robot()
cal = sensing.load()
LED = {"RED": (255, 0, 0), "GREEN": (0, 255, 0), "BLUE": (0, 0, 255)}

print("  L      R     error   chroma (r, g, b)      color")
while True:
    l, r = robot.read_sensors()
    Ln = sensing.brightness(l, cal["left"])
    Rn = sensing.brightness(r, cal["right"])
    err = (Ln - Rn) - cal["center_offset"]
    c = sensing.chroma(l, r, cal)
    col = sensing.classify(c, cal, COLOR_MAX_DIST)
    print("%.2f   %.2f   %+.2f   (%.3f, %.3f, %.3f)   %s"
          % (Ln, Rn, err, c[0], c[1], c[2], col or "-"))
    if col:
        robot.leds(*LED[col])
    else:
        robot.leds(20, 20, 20)
    time.sleep_ms(150)
