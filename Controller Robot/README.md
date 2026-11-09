# BLE Joystick Robot (ME35 HW8)

Two ESP32s running MicroPython. They talk over BLE using the course `BLE_CEEO.py` library.

| ESP32 | Files to upload | BLE role |
|---|---|---|
| Controller (joystick) | `BLE_CEEO.py`, `controller.py` (save as `main.py` to auto-run) | Central / `Listen` |
| Robot (car) | `BLE_CEEO.py`, `veml6040.py`, `robot.py` (save as `main.py` to auto-run) | Peripheral / `Yell` |

## How it works
- **Controller → robot:** `"x,y\n"` every 50 ms, each from -100 to 100.
- **Robot driving:** the robot turns x and y into wheel speeds (`left = y + x`, `right = y - x`, scaled back to ±100).
  It sets each motor's PWM duty from `MIN_DUTY` up to 65535, so speed follows how far the stick is pushed.
- **Finish line:** the robot reads the VEML6040 white channel every 20 ms.
  At startup it measures the white floor. When a reading drops below 50% of that, it has crossed the black tape:
  it beeps and sends `"FINISH\n"` back. The controller then beeps and flashes its NeoPixels.
- **Safety:** the motors stop if the link drops or no command arrives for 500 ms. Both boards reconnect on their own.

## Pins
**Robot (Cytron Robo ESP32):**
- Right motor (terminal 1): D13 / D12.
- Left motor (terminal 2): D27 / D14.
  Motor PWM runs at 20 kHz, which is above hearing range, so the motors don't whine.
- Color sensor: Grove 5 = GPIO 33 / 32 (I2C). Both wire orders are tried.
- Buzzer: built-in, GPIO 23. The buzzer **mute switch must be OFF** to hear it.
  It chirps once at startup and plays a tune at the finish line.

**Controller:**
- Joystick VRx → GPIO32, VRy → GPIO33, VCC → **3.3V**.
- Buzzer: `BUZZER_PIN`.
- NeoPixels: GPIO15.

## Bring-up checklist
1. Set the same `ROBOT_NAME` (8 characters max) in both files.
2. The robot's buzzer is already set (GPIO 23). Set `BUZZER_PIN` in `controller.py` only if the controller has a buzzer too.
3. Controller: with `PRINT_VALUES = True`, stick forward should give y > 0 and right should give x > 0.
   If not, flip `INVERT_X` or `INVERT_Y`.
4. Robot on a stand: push forward. If a wheel spins backwards, flip `RIGHT_INVERT` or `LEFT_INVERT`.
   Adjust `MIN_DUTY` so a small push just starts the wheels.
5. Power the robot on while it sits on the **white** floor, because that's when it measures the floor.
   With `PRINT_SENSOR = True`, check the values on white and on the tape, and adjust `DARK_RATIO` if needed.
