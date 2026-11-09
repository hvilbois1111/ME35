# sensing.py
# Turns raw sensor counts into (1) line brightness for the PID and
# (2) a color decision for the RED / GREEN / BLUE patches.
# Calibration values live in calib.json (made by calibrate.py).

import json

CAL_FILE = "calib.json"
COLORS = ("RED", "GREEN", "BLUE")
NEUTRAL = (1 / 3, 1 / 3, 1 / 3)


def load():
    with open(CAL_FILE) as f:
        return json.load(f)


def save(cal):
    with open(CAL_FILE, "w") as f:
        json.dump(cal, f)


def brightness(raw, side_cal):
    """0.0 = black tape, 1.0 = white floor, using the W (clear) channel."""
    w = raw[3]
    span = max(1, side_cal["w_white"] - side_cal["w_black"])
    n = (w - side_cal["w_black"]) / span
    return min(1.0, max(0.0, n))


def chroma(raw_l, raw_r, cal):
    """Color 'direction' of what both sensors see together, as (r, g, b)
    fractions that add to 1. Each channel is first divided by that sensor's
    white reading (white balance), so white floor -> about (1/3, 1/3, 1/3)."""
    tot = [0.0, 0.0, 0.0]
    for raw, s in ((raw_l, cal["left"]), (raw_r, cal["right"])):
        wh = s["rgb_white"]
        for i in range(3):
            tot[i] += raw[i] / max(1, wh[i])
    t = tot[0] + tot[1] + tot[2]
    if t < 0.6:              # too dark to judge color reliably
        return NEUTRAL
    return (tot[0] / t, tot[1] / t, tot[2] / t)


def dist(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


def classify(c, cal, max_dist):
    """Nearest calibrated reference wins. Returns 'RED'/'GREEN'/'BLUE' or None."""
    refs = [("NONE", NEUTRAL), ("LINE", cal["line_chroma"])]
    for name in COLORS:
        refs.append((name, cal["colors"][name]))
    best, best_d = None, 99.0
    for name, ref in refs:
        d = dist(c, ref)
        if d < best_d:
            best, best_d = name, d
    if best in COLORS and best_d < max_dist:
        return best
    return None
