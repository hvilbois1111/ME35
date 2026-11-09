# sensing.py  (V3 - straddling steering sensors + middle color sensor)
#
# Sensor layout (top view, robot driving up the page):
#
#                     [C]            <- MIDDLE: color only (over tape center,
#                                       mounted ahead of or behind the others)
#              [L]   |####|   [R]    <- LEFT / RIGHT: steering only,
#                    |tape|             each straddling one tape edge
#
# Steering (V1 method): each steering sensor sees part tape, part white ->
# gray. error = (L - R) - center_offset, where 0 = black, 1 = white.
#   line drifts right -> right sensor darker -> error > 0 -> turn right.
#
# Color: only the MIDDLE sensor. For each channel, how much darker it is
# than white (deficit = 1 - reading/white). The pattern of those deficits
# depends on the tape color:
#   black ~(0.33, 0.33, 0.33)   blue: blue drops least   red: red drops least

import json

CAL_FILE = "calib.json"
CAL_VERSION = 4
COLORS = ("RED", "GREEN", "BLUE")


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


# ---------------------------------------------------------------- steering
def brightness(raw, side_cal):
    """0.0 = black tape, 1.0 = white floor, using the W (clear) channel."""
    span = max(1, side_cal["w_white"] - side_cal["w_black"])
    n = (raw[3] - side_cal["w_black"]) / span
    return min(1.0, max(0.0, n))


def line_error(raw_l, raw_r, cal):
    """Positive = line is to the RIGHT (turn right). Also returns L, R."""
    L = brightness(raw_l, cal["left"])
    R = brightness(raw_r, cal["right"])
    return (L - R) - cal["center_offset"], L, R


# ---------------------------------------------------------------- color
def deficits(raw, c_cal):
    """Per-channel darkening vs. white for the color sensor."""
    wh = c_cal["rgb_white"]
    return [max(0.0, 1.0 - raw[i] / max(1, wh[i])) for i in range(3)]


def chroma(raw_c, cal):
    """Tape color signature under the middle sensor, as (r, g, b) fractions
    adding to 1, or None when it sees too little tape to judge."""
    d = deficits(raw_c, cal["color"])
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
