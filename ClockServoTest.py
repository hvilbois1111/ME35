    # PHASE 1 of the clock project: prove the servo moves correctly before
# we add LEDs, buttons, or WiFi on top of it.

from machine import Pin, PWM   # Pin = control one GPIO pin, PWM = pulse-width modulation output
import time                    # gives us time.sleep() to pause between moves

# --- SETUP (runs once) ---

# Create a PWM object on GPIO4, the pin our servo's signal wire is on.
# freq=50 means 50 pulses per second (50Hz), which is the standard rate servos expect.
servo = PWM(Pin(4), freq=50)

# A servo doesn't understand "degrees" directly - it understands the WIDTH of each
# pulse it receives, measured in nanoseconds (ns):
#   500,000 ns  (0.5 ms) pulse  -> servo moves to 0 degrees
#   2,500,000 ns (2.5 ms) pulse -> servo moves to 180 degrees
# Everything in between scales linearly (a straight line between those two points).
MIN_NS = 500_000     # pulse width at 0 degrees
MAX_NS = 2_500_000   # pulse width at 180 degrees


def set_servo_angle(angle):
    """Move the servo to `angle` degrees (0-180)."""

    # Clamp: if some future calculation ever hands us -5 or 200, force it
    # back into the safe 0-180 range instead of confusing/damaging the servo.
    if angle < 0:
        angle = 0
    if angle > 180:
        angle = 180

    # Convert degrees -> nanoseconds using the linear scale described above.
    # angle/180 turns "angle" into a fraction from 0.0 to 1.0,
    # then we scale that fraction across the MIN_NS-MAX_NS range.
    pulse_ns = MIN_NS + (angle / 180) * (MAX_NS - MIN_NS)

    servo.duty_ns(int(pulse_ns))  # int() because duty_ns() needs a whole number


# --- TEST (runs every time you press Run) ---
# This just proves the function above actually works, the same sweep your
# class activity asked for, but now going through set_servo_angle() instead
# of hardcoded duty_ns() calls.

print("0 degrees (left edge)")
set_servo_angle(0)
time.sleep(1)

print("90 degrees (middle/top)")
set_servo_angle(90)
time.sleep(1)

print("180 degrees (right edge)")
set_servo_angle(180)
time.sleep(1)

print("Back to 0")
set_servo_angle(0)
