# LEGO Color Sorter – Project Notes (ME35)

## Hardware
- **Microcontroller:** ESP32 (ESP-WROOM-32 dev board), running MicroPython
- **Color sensor:** VEML6040 (RGBW), I2C address 0x10
  - Library: `veml6040.py` (must be uploaded to the ESP32)
  - Wiring used so far: **SDA = GPIO 21, SCL = GPIO 22** (the board's default I2C pins)
  - Library starts the sensor in *auto mode* with a **1280 ms integration time**,
    so a new reading is only ready about every 1.3 seconds.
- **Button:** 1 push button (one leg to the GPIO pin, other leg to GND, internal pull-up)
  - Pin: GPIO 19 (moved off GPIO 4 because the hatch servo uses it)
- **LEDs** – each switched by an N-channel logic-level MOSFET (low-side switch), powered from 3V3:
  - 3V3 → LED resistor → LED long leg; LED short leg → MOSFET drain; source → GND
  - GPIO → ~220 Ω → gate; 10 kΩ from gate → GND (keeps LED off at boot)
  - GPIO 1 = LED on, 0 = off (code unchanged from the direct-wired version)
  - White (lights brick during scan): GPIO 16, LED resistor ~22–47 Ω
  - Blue (flashes 3x for blue brick): GPIO 17, LED resistor ~22–47 Ω
  - Red (flashes 3x for red brick): GPIO 18, LED resistor ~68–100 Ω
  - White LED is on during BOTH training and sorting scans so readings match.
- **Servos:** 2, 50 Hz PWM, 0.5–2.5 ms pulse = 0–180 degrees
  - Hatch servo: GPIO 4 (D4). Closed 0, open 90; stays open 1 s
  - Head servo: GPIO 5 (D5). Center 90, blue 0 (clockwise), red 180 (counterclockwise)
  - Sort order: rotate head → open hatch 1 s → close hatch + return head to center together
  - Misc "X" bricks: head stays centered, hatch opens (assumed; confirm)
  - Power servos from 5 V (VIN) with a shared GND, not 3V3

### ESP32 pin gotchas
- GPIO 34, 35, 36, 39 are **input only** and have **no internal pull-up** resistors.
- GPIO 6–11 are connected to the board's flash memory – do not use.
- ADC2 pins can't be used for analog reads while WiFi is on.

## Program flow
1. **Training mode** – build the KNN data set, 15 button presses total:
   - Presses 1–5: blue bricks → class `"blue"`
   - Presses 6–10: red bricks → class `"red"`
   - Presses 11–15: miscellaneous bricks → class `"X"`
2. **Sorting mode** – place an unknown brick, press the button:
   scan → KNN decides the class → hopper servo rotates to that bin → drop servo releases the brick.

## Reference material
- Teacher's KNN example: `demo_color_KNN.py`
- Class Notion page (KNN info):
  https://milandahal.notion.site/8bfbcab56f1283829d5a011a5f3f6641?v=e4bbcab56f1283eea2a2085b5718c23a&p=8f2bcab56f1283618a37012df1e666b9&pm=s

## Build plan (step by step)
- [x] Part 1: button + sensor + training data + KNN guess (printed only) – `color_sorter.py`
- [x] Part 2: servo control (written, testing)
- [ ] Part 3: full sorting loop + debugging
