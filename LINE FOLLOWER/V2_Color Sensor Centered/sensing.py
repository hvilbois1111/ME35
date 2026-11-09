# sensing.py  (V2 - "color sensor centered" layout)
#
# Sensor layout (looking down, robot driving up the page):
#
#            LEFT sensor        RIGHT sensor
#               [L]                [R]
#             white floor     |####tape####|
#
#   * RIGHT sensor sits over the MIDDLE of the tape -> sees the full color
#     patch (used for color detection) and reads dark when centered.
#   * LEFT sensor sits over white, just left of the tape -> stays white
#     unless the line slides to the left.
#
# Steering error (positive = line is to the RIGHT -> turn right):
#   line drifts RIGHT : R sees more white, L stays white   -> error +0..+1
#   line drifts LEFT  : L starts seeing tape (and R sees
#                       more white too)                     -> error  0..-1
#   centered          : R dark, L white                     -> error  ~0
# R alone can't tell left from right (it gets lighter either way), so the
# LEFT sensor decides the side. LineTracker remembers that the line went
# left until the right sensor is back on the tape.
#
# Color ("tape signature"): for the RIGHT sensor, how much darker each
# channel is than white (deficit = 1 - reading/white). White floor adds ~0
# deficit, so the pattern depends only on the tape color:
#   black ~(0.33, 0.33, 0.33)  blue: blue drops least  red: red drops least

import json

CAL_FILE = "calib.json"
CAL_VERSION = 3
COLORS = ("RED", "GREEN", "BLUE")
COLOR_SIDE = "right"       # the sensor that sits over the tape

LEFT_ENTER = 0.15          # left-sensor "tape seen" level that means line went left
RIGHT_BACK_ON = 0.10       # right sensor this close to centered -> line is back


def load():
    with open(CAL_FILE) as f:
        cal = json.load(f)
    if cal.get("version") != CAL_VERSION:
        raise OSError("calib.json is from an older version - rerun calibrate.py")
    return cal


def save(cal):
    cal["version"] = CAL_VERSION
    with open(CAL_FILE, "w") as f:
        json.dump(cal, f)


def _clamp01(x):
    return 0.0 if x < 0 else (1.0 if x > 1 else x)


def brightness(raw, side_cal):
    """0.0 = black tape, 1.0 = white floor, using the W (clear) channel."""
    span = max(1, side_cal["w_white"] - side_cal["w_black"])
    return _clamp01((raw[3] - side_cal["w_black"]) / span)


# ---------------------------------------------------------------- steering
def line_terms(raw_l, raw_r, cal):
    """r_off: 0 = right sensor centered on tape ... 1 = right sensor on white.
       l_on : 0 = left sensor sees only white  ... 1 = left sensor on tape."""
    L = brightness(raw_l, cal["left"])
    R = brightness(raw_r, cal["right"])
    rc, dlc = cal["r_center"], cal["dl_center"]
    r_off = _clamp01((R - rc) / max(0.05, 1.0 - rc))
    l_on = _clamp01(((1.0 - L) - dlc) / max(0.05, 1.0 - dlc))
    return L, R, r_off, l_on


class LineTracker:
    def __init__(self, cal):
        self.cal = cal
        self.reset()

    def reset(self):
        self.left_mode = False      # True = line is known to be LEFT of center

    def error(self, raw_l, raw_r):
        L, R, r_off, l_on = line_terms(raw_l, raw_r, self.cal)
        left_err = -(r_off + l_on) / 2          # 0 .. -1, grows as line goes left

        if l_on >= LEFT_ENTER:
            self.left_mode = True
        elif self.left_mode and r_off < RIGHT_BACK_ON:
            self.left_mode = False              # right sensor is back on the tape

        if self.left_mode:
            return left_err
        # Not (yet) known to be left: blend from "line right" to "line left"
        # as the left sensor starts to see tape, so the error stays smooth.
        s = l_on / LEFT_ENTER
        return (1 - s) * r_off + s * left_err


# ---------------------------------------------------------------- color
def deficits(raw, side_cal):
    """Per-channel darkening vs. white for one sensor."""
    wh = side_cal["rgb_white"]
    return [max(0.0, 1.0 - raw[i] / max(1, wh[i])) for i in range(3)]


def chroma(raw_l, raw_r, cal):
    """Tape color signature seen by the color (right) sensor, as (r, g, b)
    fractions adding to 1, or None when it sees too little tape to judge."""
    raw = raw_r if COLOR_SIDE == "right" else raw_l
    d = deficits(raw, cal[COLOR_SIDE])
    t = d[0] + d[1] + d[2]
    if t < cal.get("tape_min", 0.3):
        return None
    return (d[0] / t, d[1] / t, d[2] / t)


def dist(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


def classify(c, cal, max_dist):
    """Nearest calibrated reference wins. Returns 'RED'/'GREEN'/'BLUE' or None.
    Must also be within the match radius: the smaller of max_dist and the
    radius calibrate.py computed from how far apart your references are."""
    if c is None:
        return None
    limit = min(max_dist, cal.get("color_max_dist", max_dist))
    refs = [("LINE", cal["line_chroma"])]
    for name in COLORS:
        refs.append((name, cal["colors"][name]))
    best, best_d = None, 99.0
    for name, ref in refs:
        d = dist(c, ref)
        if d < best_d:
            best, best_d = name, d
    if best in COLORS and best_d < limit:
        return best
    return None
