# ============================================================
#  LEGO COLOR SORTER - PART 2
#  Training data + KNN color guessing + LEDs + servos
#
#  How to use:
#    1. Upload veml6040.py AND this file to the ESP32.
#    2. Run this file and watch the printed messages.
#    3. TRAINING: put a brick on the sensor, press the button.
#       Do 5 blue, then 5 red, then 5 misc (X) bricks.
#    4. SORTING: put any brick on the sensor, press the button,
#       the program guesses the color, flashes an LED, turns the
#       head over the right bin, and drops the brick.
# ============================================================

from machine import Pin, SoftI2C, PWM
import time
import math
import veml6040


# ============================================================
#  SECTION 1: SETTINGS  (change these numbers if needed)
# ============================================================

SDA_PIN = 21          # color sensor data wire
SCL_PIN = 22          # color sensor clock wire
BUTTON_PIN = 19       # button wire (other side of button goes to GND)
                      # (moved from pin 4 - pin 4 is now the hatch servo)

WHITE_LED_PIN = 16    # white LED that lights up the brick while scanning
BLUE_LED_PIN = 17     # blue LED that flashes when a blue brick is found
RED_LED_PIN = 18      # red LED that flashes when a red brick is found

FLASH_COUNT = 3       # how many times the blue/red LED flashes
FLASH_TIME = 0.2      # seconds the LED stays on (and off) for each flash

HATCH_SERVO_PIN = 4   # D4: servo that opens/closes the hatch
HEAD_SERVO_PIN = 5    # D5: servo that rotates the head

# Servo angles (0 to 180 degrees)
HATCH_CLOSED = 0      # hatch closed
HATCH_OPEN = 90       # hatch open (90 degrees from closed)

HEAD_CENTER = 90      # head pointing at the middle
HEAD_BLUE = 30         # 90 degrees clockwise from center
HEAD_RED = 160        # 90 degrees counterclockwise from center
# If the head turns the wrong way, swap the HEAD_BLUE and HEAD_RED numbers

HATCH_OPEN_TIME = 1.0 # seconds the hatch stays open
SERVO_MOVE_TIME = 0.6 # seconds to wait for a servo to finish moving

BRICKS_PER_COLOR = 5  # how many training bricks for each color
K = 3                 # how many nearest neighbors KNN looks at

# The order the colors are trained in
TRAINING_COLORS = ["blue", "red", "X"]

# The sensor needs about 1.3 seconds to take a fresh reading
SENSOR_WAIT = 1.5     # seconds


# ============================================================
#  SECTION 2: HARDWARE SETUP
# ============================================================

# Button: PULL_UP means the pin reads 1 normally and 0 when pressed
button = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)

# LEDs: Pin.OUT means the ESP32 controls them (1 = on, 0 = off)
white_led = Pin(WHITE_LED_PIN, Pin.OUT)
blue_led = Pin(BLUE_LED_PIN, Pin.OUT)
red_led = Pin(RED_LED_PIN, Pin.OUT)

# Make sure all LEDs start off
white_led.value(0)
blue_led.value(0)
red_led.value(0)

# Servos: they are controlled with a PWM signal at 50 Hz
hatch_servo = PWM(Pin(HATCH_SERVO_PIN), freq=50)
head_servo = PWM(Pin(HEAD_SERVO_PIN), freq=50)

# Color sensor on the I2C bus
i2c = SoftI2C(scl=Pin(SCL_PIN), sda=Pin(SDA_PIN))
print("I2C devices found:", i2c.scan())   # should show [16] (that's 0x10)
sensor = veml6040.VEML6040(i2c)


# ============================================================
#  SECTION 3: HELPER FUNCTIONS
# ============================================================

def wait_for_button():
    # Wait until the button is pressed...
    while button.value() == 1:
        time.sleep(0.01)
    # ...then wait until it is let go (so one press = one action)
    while button.value() == 0:
        time.sleep(0.01)
    time.sleep(0.05)  # small pause to ignore button "bounce"


def read_color():
    # Give the sensor time to take a fresh reading of the new brick
    time.sleep(SENSOR_WAIT)

    red, green, blue, white = sensor.read_rgbw()
    print("  raw reading  R:", red, " G:", green, " B:", blue, " W:", white)

    # Avoid dividing by zero if the sensor sees total darkness
    if white == 0:
        white = 1

    # Divide by white so the result depends on COLOR, not brightness
    r = red / white
    g = green / white
    b = blue / white
    print("  color ratios r: %.3f  g: %.3f  b: %.3f" % (r, g, b))
    return r, g, b


def set_servo_angle(servo, angle):
    # A servo's position is set by how long each pulse is:
    #   0.5 ms pulse = 0 degrees,  2.5 ms pulse = 180 degrees
    pulse_ms = 0.5 + (angle / 180) * 2.0

    # One full PWM cycle at 50 Hz is 20 ms.
    # duty_u16 wants the "on" part as a number from 0 to 65535.
    duty = int(pulse_ms / 20 * 65535)
    servo.duty_u16(duty)


def drop_brick(head_angle):
    # Step 1: turn the head over the correct bin
    set_servo_angle(head_servo, head_angle)
    time.sleep(SERVO_MOVE_TIME)

    # Step 2: open the hatch and hold it open so the brick falls out
    set_servo_angle(hatch_servo, HATCH_OPEN)
    time.sleep(SERVO_MOVE_TIME + HATCH_OPEN_TIME)

    # Step 3: close the hatch AND turn the head back to center together
    set_servo_angle(hatch_servo, HATCH_CLOSED)
    set_servo_angle(head_servo, HEAD_CENTER)
    time.sleep(SERVO_MOVE_TIME)


def flash_led(led):
    # Blink the given LED on and off FLASH_COUNT times
    for i in range(FLASH_COUNT):
        led.value(1)
        time.sleep(FLASH_TIME)
        led.value(0)
        time.sleep(FLASH_TIME)


def knn_guess(r, g, b, data, k):
    # Step 1: find the distance from the new brick to EVERY training brick
    distances = []
    for point in data:
        dist = math.sqrt((r - point[0])**2 + (g - point[1])**2 + (b - point[2])**2)
        distances.append([dist, point[3]])   # [distance, color name]

    # Step 2: sort so the closest bricks come first, keep only the k closest
    distances.sort()
    closest = distances[:k]

    # Step 3: collect the color names of those k closest bricks
    votes = []
    for item in closest:
        votes.append(item[1])
    print("  closest", k, "neighbors:", votes)

    # Step 4: the color with the most votes wins
    winner = max(set(votes), key=votes.count)
    return winner


# ============================================================
#  SECTION 4: TRAINING MODE
#  Builds the data set: each entry is (r, g, b, color_name)
# ============================================================

# Start with the hatch closed and the head in the center
# (this has to come AFTER Section 3, where set_servo_angle is created)
set_servo_angle(hatch_servo, HATCH_CLOSED)
set_servo_angle(head_servo, HEAD_CENTER)

data = []

print("")
print("===== TRAINING MODE =====")

for color in TRAINING_COLORS:
    print("")
    print("--- Now training:", color, "---")

    for count in range(1, BRICKS_PER_COLOR + 1):
        print("Place", color, "brick", count, "of", BRICKS_PER_COLOR, "and press the button")
        wait_for_button()

        # Light up the brick so training readings match sorting readings
        white_led.value(1)
        r, g, b = read_color()
        white_led.value(0)

        data.append((r, g, b, color))
        print("  saved as", color)

print("")
print("Training done! Data set:")
for point in data:
    print("  ", point)


# ============================================================
#  SECTION 5: SORTING MODE
#  Scan a brick and guess its color (servos will be added later)
# ============================================================

print("")
print("===== SORTING MODE =====")

while True:
    print("")
    print("Place a brick and press the button to identify it")
    wait_for_button()

    # White LED on while scanning, off once the result is printed
    white_led.value(1)
    r, g, b = read_color()
    guess = knn_guess(r, g, b, data, K)
    print(">>> I think this brick is:", guess)
    white_led.value(0)

    # Flash the matching LED, then sort the brick into its bin
    if guess == "blue":
        flash_led(blue_led)
        drop_brick(HEAD_BLUE)
    elif guess == "red":
        flash_led(red_led)
        drop_brick(HEAD_RED)
    else:
        # Misc "X" brick: no flash, head stays centered, just drop it
        drop_brick(HEAD_CENTER)
