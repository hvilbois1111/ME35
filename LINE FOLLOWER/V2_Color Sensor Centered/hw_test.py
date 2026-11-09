# hw_test.py
# Run from Thonny with the WHEELS OFF THE TABLE.
# Checks sensors, buttons, LEDs, buzzer, and motor wiring/direction.

import time
import robot_hw
from robot_hw import Robot

robot = Robot(need_sensors=False)

print("\n--- Sensors ---")
for side, info in robot.sensor_info.items():
    print("  %s: %s" % (side, info))

print("\n--- LEDs and buzzer ---")
for c in ((255, 0, 0), (0, 255, 0), (0, 0, 255)):
    robot.leds(*c)
    robot.tone(1200, 150)
    time.sleep_ms(300)
robot.leds(0, 0, 0)
print("  You should have seen red, green, blue and heard 3 beeps")
print("  (no sound? check the buzzer mute switch).")

print("\n--- Motors (wheels off the table!) ---")
time.sleep(1)
print("  LEFT wheel forward...")
robot.drive(0.5, 0)
time.sleep(1.5)
robot.stop()
time.sleep(0.5)
print("  RIGHT wheel forward...")
robot.drive(0, 0.5)
time.sleep(1.5)
robot.stop()
print("  Wrong wheel turned?  -> swap LEFT_MOTOR_PINS and RIGHT_MOTOR_PINS in robot_hw.py")
print("  Turned backward?     -> set LEFT/RIGHT_MOTOR_REVERSED = True in robot_hw.py")

print("\n--- Slowest speed that still moves (for MIN_DUTY) ---")
print("  Each line is a raw PWM duty; note the lowest one where BOTH wheels turn.")
for duty in (0.15, 0.20, 0.25, 0.30, 0.35, 0.40):
    d = int(duty * 65535)
    for m in (robot.left_motor, robot.right_motor):
        m.a.duty_u16(d)
        m.b.duty_u16(0)
    print("  duty %.2f" % duty)
    time.sleep(1.2)
robot.stop()

if robot.sensor_l and robot.sensor_r:
    print("\n--- Which sensor is which ---")
    print("  For 8 s, cover the LEFT sensor with your finger, then the RIGHT one.")
    print("  The W value of the one you cover should drop a lot.")
    t_end = time.ticks_add(time.ticks_ms(), 8000)
    while time.ticks_diff(t_end, time.ticks_ms()) > 0:
        l, r = robot.read_sensors()
        print("  LEFT W=%5d   RIGHT W=%5d" % (l[3], r[3]))
        time.sleep_ms(250)
    print("  Backwards? swap LEFT_SENSOR_PORT and RIGHT_SENSOR_PORT in robot_hw.py")

print("\n--- Buttons ---")
print("  For 6 s, press button A (GPIO34) and B (GPIO35).")
t_end = time.ticks_add(time.ticks_ms(), 6000)
while time.ticks_diff(t_end, time.ticks_ms()) > 0:
    print("  A pressed=%s  B pressed=%s   (raw A=%d B=%d)"
          % (robot.button_a(), robot.button_b(),
             robot.btn_a.value(), robot.btn_b.value()))
    time.sleep_ms(300)
print("  If 'pressed' is backwards, set BUTTON_ACTIVE_LOW = False in robot_hw.py")
print("\nDone.")
