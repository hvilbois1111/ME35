# Line Follower V3 - 2 steering sensors + 1 color sensor (ME-35)

MicroPython for Cytron Robo ESP32 + 3x Grove Color Sensor V3.0 (VEML6040)
+ 2 TT motors + white illumination LED on GPIO 25.

## Sensor layout (top view, driving up the page)

                   [C]          MIDDLE: color ONLY, over the tape center
                                (ahead of or behind the other two)
            [L]   |####|   [R]  LEFT / RIGHT: steering ONLY,
                  |tape|        each straddling one tape edge (like V1)

## Wiring
| Part | Port / pins |
|---|---|
| Left steering sensor | Grove port 1 (GPIO 17/16) |
| Right steering sensor | Grove port 2 (GPIO 21/22) |
| Middle color sensor | **Grove port 5 (GPIO 33/32)** |
| White LED | GPIO 25 (with a current-limiting resistor) |
| Left motor / right motor | M1 (reversed in software) / M2 |

All three sensors have the same fixed I2C address, so each needs its own port.
Don't use Grove 3/4 (they use GPIO 25 = LED) or 6/7 (input-only pins).

## What changed from V1
- Third sensor for color; the straddling sensors only steer
  (same V1 steering: error = (L - R) - center_offset).
- Color uses the "tape signature" method (per-channel darkening vs. white),
  much better at black vs. blue.
- White LED is switched on in robot_hw.py, so calibrate / monitor / main all
  use the same lighting. NeoPixels stay off while measuring.
- calibrate.py checks contrast + color separation and sets the color match
  radius itself. New calib.json format: recalibrate.
- hw_test.py checks all three sensors.

## Order
1. `hw_test.py` (wheels off the table): cover L, middle, R in turn
2. `calibrate.py` on the real track, real lighting
3. `monitor.py`: line right -> error +, line left -> error -; patches light
   the NeoPixels
4. `main.py`: button A (GPIO34) = start, button B (GPIO35) = stop

## Tuning (top of main.py)
Kept from V1: BASE_SPEED 0.1, KP 0.8, KD 0.1. With better sensor contrast
the error gets larger per mm, so the same gains act stronger. If it shakes
or spins in place, lower KD first (try 0.03), then KP.
Keep COLOR_COOLDOWN_MS shorter than the time between two patches.
