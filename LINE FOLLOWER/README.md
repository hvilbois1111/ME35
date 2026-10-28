# Line Follower (ME-35)

MicroPython for Cytron Robo ESP32 + 2x Grove Color Sensor V3.0 (VEML6040) + 2 TT motors.

## Wiring
- Left color sensor  -> Grove port 2 (GPIO 21/22)
- Right color sensor -> Grove port 1 (GPIO 17/16)
- Left motor -> M1, right motor -> M2
(The VEML6040 has a fixed I2C address, so each sensor needs its own port.)

## Files (upload ALL .py files to the ESP32 in Thonny)
| File | What it does |
|---|---|
| veml6040.py | sensor driver |
| robot_hw.py | pins, motors, LEDs, buzzer, buttons (wiring config at top) |
| sensing.py | brightness + color math, loads/saves calib.json |
| hw_test.py | check motors/sensors/buttons (wheels off the table) |
| calibrate.py | guided calibration -> writes calib.json on the ESP32 |
| monitor.py | live sensor readout, motors off |
| main.py | the line follower (auto-runs at boot) |

## Order
1. `hw_test.py` -> fix pin/direction flags in robot_hw.py if needed
2. `calibrate.py` (on the real track, real lighting)
3. `monitor.py` -> slide robot by hand, check error sign and colors
4. `main.py` -> button A (GPIO34) = start, button B (GPIO35) = stop

## Tuning (top of main.py)
Start: BASE_SPEED 0.35, KP 0.5, KD 0.02, KI 0.
- Drifts off on curves: raise KP (or lower BASE_SPEED)
- Wobbles: raise KD a little, or lower KP
- Shaking / spinning in place: KD or KP too high
- RED spin not a full turn: adjust SPIN_360_MS
