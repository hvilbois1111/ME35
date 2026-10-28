# config.py - every pin and tunable number for the phone-jail robot lives here.
# Board: Cytron Robo ESP32 (NodeMCU ESP32), MicroPython.

# ---------------- Pins ----------------
SERVO_PIN = 4            # Servo port 1 (S pin)

MOTOR_A_PIN = 12         # MOTOR 1 terminal (driver input A)
MOTOR_B_PIN = 13         # MOTOR 1 terminal (driver input B)
ENC_A_PIN = 16           # Grove 1, yellow wire  (encoder A)
ENC_B_PIN = 17           # Grove 1, white wire   (encoder B)

I2C_SDA_PIN = 21         # Grove 2 (VEML6040 color sensor)
I2C_SCL_PIN = 22

JOY_X_PIN = 36           # Grove 7, yellow (X axis; clicking maxes this out)
JOY_Y_PIN = 39           # Grove 7, white  (Y axis = up/down)

SEG_PINS = (25, 26, 32, 33, 5, 14, 27)   # segments a, b, c, d, e, f, g
SEG_DP_PIN = None        # set to 19 if you wire the decimal point
SEG_COMMON_ANODE = False # 5161AS = common CATHODE: middle pins to GND, HIGH = lit

EYE_LEFT_PIN = 2
EYE_RIGHT_PIN = 18

BUZZER_PIN = 23          # on-board piezo (flip its switch ON)

# ---------------- Timer ----------------
TEST_MODE = True         # True: each step = 10 SECONDS (for demos/debugging)
                         # False: each step = 10 MINUTES (real use)
MINUTES_PER_STEP = 1
MIN_STEPS = 1            # display range 1..9
MAX_STEPS = 9
DEFAULT_STEPS = 1

# ---------------- Servo (phone jail arm) ----------------
SERVO_OPEN_ANGLE = 0     # arm out of the way
SERVO_LOCK_ANGLE = 90    # arm over the phone. If it turns the wrong way,
                         # swap these two numbers (e.g. OPEN=180, LOCK=90).
SERVO_MIN_US = 500       # pulse width at 0 deg  (tune if range is off)
SERVO_MAX_US = 2500      # pulse width at 180 deg

# ---------------- Candy tray (DC motor + encoder) ----------------
ENCODER_COUNTS_PER_REV = 960   # FIT0450 output shaft, A-channel rising edges
TRAY_ANGLE_DEG = 45
TRAY_OPEN_TIME_S = 5
MOTOR_CCW_SIGN = -1      # flipped after testing: tray was opening clockwise
MOTOR_MAX_SPEED = 60     # % PWM
MOTOR_MIN_SPEED = 30     # % PWM - lowest speed that still turns the gearbox
MOTOR_KP = 1.5           # proportional gain (% speed per encoder count of error)
MOTOR_TIMEOUT_MS = 3000  # safety stop if the encoder never reaches the target

# ---------------- Phone detection (color sensor) ----------------
PHONE_COVER_RATIO = 0.35 # "covered" when brightness < 35% of the empty-tray level
PHONE_CONFIRM_MS = 1000  # must stay covered/uncovered this long to count

# ---------------- Joystick ----------------
JOY_INVERT_Y = True      # flipped after testing: up/down were reversed
JOY_DEADZONE = 0.30      # fraction of full deflection ignored around center
JOY_CLICK_LEVEL = 0.93   # X above 93% of full scale = click
JOY_REPEAT_DELAY_MS = 500
JOY_REPEAT_RATE_MS = 250

# ---------------- Emergency release ----------------
EMERGENCY_HOLD_MS = 3000 # hold the joystick click this long while the timer
                         # runs to release the phone early (no candy). 0 = off.
