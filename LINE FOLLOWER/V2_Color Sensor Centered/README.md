# Line Follower V2 - "Color Sensor Centered" (ME-35)

MicroPython for Cytron Robo ESP32 + 2x Grove Color Sensor V3.0 (VEML6040)
+ 2 TT motors + white illumination LED on GPIO 25.

## Sensor layout (top view, driving up the page)

        LEFT sensor          RIGHT sensor
           [L]                  [R]
       white floor        |####tape####|

- RIGHT sensor: directly over the MIDDLE of the tape (steering + color).
- LEFT sensor: over white, just left of the tape (tells which way the line went).
- Keep them as close together as they fit (~20 mm center to center or less),
  same height, ~3-5 mm off the floor, ideally each in a short black shroud.

## What changed from V1
- Steering math (sensing.LineTracker) for the offset layout:
  line right -> right sensor sees white -> error +;
  line left  -> left sensor sees tape   -> error -.
- Color detection uses only the RIGHT sensor, with the "tape signature"
  method (per-channel darkening vs. white), much better at black vs. blue.
- White LED (GPIO 25) is switched on in robot_hw.py, so calibrate,
  monitor and main all see the same light. NeoPixels are kept off while
  measuring.
- calibrate.py checks contrast and color separation and sets the color
  match radius itself. calib.json format changed: recalibrate.

## Wiring
- Left color sensor  -> Grove port 1 (GPIO 17/16)
- Right color sensor -> Grove port 2 (GPIO 21/22)
- Left motor -> M1 (reversed in software), right motor -> M2
- White LED -> GPIO 25 (with a resistor)

## Order
1. `hw_test.py` (wheels off the table)
2. `calibrate.py` on the real track, real lighting
3. `monitor.py`: slide the robot by hand. Line to the right -> error +,
   line to the left -> error - and "LEFT" shown. Patches light the NeoPixels.
4. `main.py`: button A (GPIO34) = start, button B (GPIO35) = stop

## Tuning (top of main.py)
Carried over from V1: BASE_SPEED 0.1, KP 0.8, KD 0.1, KI 0.
The error has the same -1..+1 range as V1, but retune once on the track.
Keep COLOR_COOLDOWN_MS shorter than the time between two patches.
