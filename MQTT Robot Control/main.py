# main.py - ME35 Homework 9: robot controlled over MQTT (the robot is the subscriber)
#
# Topics (from the assignment):
#   ME35/speed       "0".."100"                     sets speed only, never starts the motors
#   ME35/direction   forward|backward|left|right|stop   the only thing that makes the robot move
#   ME35/led/0       {"r":255,"g":0,"b":122}        NeoPixel 0 (GPIO 15)
#   ME35/led/1       {"r":255,"g":0,"b":122}        NeoPixel 1 (GPIO 15)
# If the connection to the broker is lost: motors STOP and both LEDs blink RED until it reconnects.
#
# Save this file on the ESP32 as main.py so it runs on power-up without Thonny.

import network
import time
import json
import machine
import ubinascii
import neopixel
from machine import Pin, PWM
from umqtt.simple import MQTTClient
import secrets

# ------------------------- robot configuration -------------------------
# Cytron Robo ESP32 motor terminals: M1 = GPIO 12/13, M2 = GPIO 14/27
LEFT_PINS = (12, 13)        # (A, B) pins of the LEFT wheel motor
RIGHT_PINS = (14, 27)       # (A, B) pins of the RIGHT wheel motor
LEFT_REVERSED = False       # set True if this wheel spins backward on "forward"
RIGHT_REVERSED = False
PWM_FREQ = 1000
MIN_PCT = 0                 # raise (e.g. 30) if the motors hum but don't turn at low speeds

NEOPIXEL_PIN = 15
NUM_LEDS = 2

DEFAULT_SPEED = 20          # used until the first ME35/speed message arrives

HEARTBEAT_PERIOD_MS = 1000  # we send ourselves a tiny message through the broker this often...
LOST_TIMEOUT_MS = 3000      # ...and if nothing comes back for this long, the connection is lost

# A unique ID per board, since every bot connects to the same broker at the same time
CLIENT_ID = "me35-bot-" + ubinascii.hexlify(machine.unique_id()).decode()
HEARTBEAT_TOPIC = "hb/" + CLIENT_ID
SUB_TOPICS = ("ME35/speed", "ME35/direction", "ME35/led/+")

# ------------------------------ motors ---------------------------------
class Motor:
    """One DC motor on the Cytron driver (PWM_PWM mode: drive A forward, B backward)."""

    def __init__(self, pins, reversed_=False):
        self.a = PWM(Pin(pins[0]))
        self.b = PWM(Pin(pins[1]))
        for p in (self.a, self.b):
            p.freq(PWM_FREQ)
            p.duty_u16(0)
        self.reversed = reversed_

    def set(self, pct):
        """pct from -100 (full backward) to 100 (full forward); 0 = stop."""
        if self.reversed:
            pct = -pct
        if pct == 0:
            self.a.duty_u16(0)
            self.b.duty_u16(0)
            return
        mag = MIN_PCT + abs(pct) * (100 - MIN_PCT) / 100
        duty = int(min(mag, 100) * 65535 / 100)
        if pct > 0:
            self.b.duty_u16(0)
            self.a.duty_u16(duty)
        else:
            self.a.duty_u16(0)
            self.b.duty_u16(duty)


left = Motor(LEFT_PINS, LEFT_REVERSED)
right = Motor(RIGHT_PINS, RIGHT_REVERSED)

# (left wheel, right wheel) multipliers. left/right rotate in place.
DIRECTIONS = {
    "forward": (1, 1),
    "backward": (-1, -1),
    "left": (-1, 1),
    "right": (1, -1),
    "stop": (0, 0),
}

speed = DEFAULT_SPEED
direction = "stop"


def apply_motion():
    l, r = DIRECTIONS[direction]
    left.set(l * speed)
    right.set(r * speed)


def stop_motors():
    global direction
    direction = "stop"
    left.set(0)
    right.set(0)

# ------------------------------ LEDs -----------------------------------
np = neopixel.NeoPixel(Pin(NEOPIXEL_PIN), NUM_LEDS)
led_colors = [(0, 0, 0)] * NUM_LEDS     # last colors the teacher set


def show_leds():
    for i in range(NUM_LEDS):
        np[i] = led_colors[i]
    np.write()


_blink_on = False
_last_blink = 0


def blink_red_step():
    """Toggle both LEDs between red and off every 250 ms. Call it often."""
    global _blink_on, _last_blink
    now = time.ticks_ms()
    if time.ticks_diff(now, _last_blink) >= 250:
        _last_blink = now
        _blink_on = not _blink_on
        c = (255, 0, 0) if _blink_on else (0, 0, 0)
        for i in range(NUM_LEDS):
            np[i] = c
        np.write()


def blink_red_for(ms):
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < ms:
        blink_red_step()
        time.sleep_ms(20)


def clamp255(v):
    return max(0, min(255, int(v)))

# ----------------------------- messages --------------------------------
last_rx = time.ticks_ms()


def on_message(topic, msg):
    global speed, direction, last_rx
    last_rx = time.ticks_ms()           # any message proves the broker is still there
    t = topic.decode()
    if t == HEARTBEAT_TOPIC:
        return
    m = msg.decode().strip()
    print(t, "->", m)
    try:
        if t == "ME35/speed":
            speed = max(0, min(100, int(float(m.strip('"')))))
            if direction != "stop":
                apply_motion()          # already driving: change speed now; never starts motion
        elif t == "ME35/direction":
            d = m.strip('"').lower()
            if d in DIRECTIONS:
                direction = d
                apply_motion()
            else:
                print("  unknown direction, ignored")
        elif t.startswith("ME35/led/"):
            i = int(t.split("/")[-1])
            c = json.loads(m)
            led_colors[i] = (clamp255(c.get("r", 0)), clamp255(c.get("g", 0)), clamp255(c.get("b", 0)))
            show_leds()
    except Exception as e:
        # a badly formatted message must never crash the robot
        print("  bad message ignored:", e)

# ---------------------------- connection -------------------------------
wlan = network.WLAN(network.STA_IF)


def connect_wifi(timeout_ms=10000):
    wlan.active(True)
    if wlan.isconnected():
        return True
    print("Connecting to WiFi", secrets.SSID, "...")
    try:
        wlan.connect(secrets.SSID, secrets.PWD)
    except OSError as e:
        print("  wifi connect error:", e)
    t0 = time.ticks_ms()
    while not wlan.isconnected() and time.ticks_diff(time.ticks_ms(), t0) < timeout_ms:
        blink_red_step()
        time.sleep_ms(50)
    if wlan.isconnected():
        print("WiFi connected, IP:", wlan.ifconfig()[0])
        return True
    print("WiFi failed")
    return False


def connect_mqtt():
    c = MQTTClient(CLIENT_ID, secrets.mqtt_url, port=secrets.port, keepalive=30)
    c.set_callback(on_message)
    c.connect()
    for t in SUB_TOPICS:
        c.subscribe(t)
    c.subscribe(HEARTBEAT_TOPIC)
    print("MQTT connected to", secrets.mqtt_url, "as", CLIENT_ID)
    return c


def connection_lost(client, reason):
    stop_motors()
    print("CONNECTION LOST:", reason, "-> stopped, blinking red")
    try:
        client.disconnect()
    except Exception:
        pass

# ------------------------------- main ----------------------------------
def main():
    global last_rx
    client = None
    last_hb = 0
    while True:
        if client is None:
            # offline: motors off, blink red, keep trying to reconnect
            stop_motors()
            if not connect_wifi():
                blink_red_for(1000)
                continue
            try:
                client = connect_mqtt()
                last_rx = time.ticks_ms()
                last_hb = 0
                show_leds()             # back online: restore the teacher's colors
            except Exception as e:
                print("MQTT connect failed:", e)
                client = None
                blink_red_for(2000)
            continue

        try:
            client.check_msg()          # non-blocking; runs on_message if something arrived
            now = time.ticks_ms()
            if time.ticks_diff(now, last_hb) >= HEARTBEAT_PERIOD_MS:
                client.publish(HEARTBEAT_TOPIC, b"1")
                last_hb = now
            if not wlan.isconnected():
                raise OSError("WiFi dropped")
            if time.ticks_diff(now, last_rx) > LOST_TIMEOUT_MS:
                raise OSError("no reply from broker")
        except Exception as e:
            connection_lost(client, e)
            client = None
        time.sleep_ms(10)


try:
    main()
finally:
    # also stops the wheels when you press Stop in Thonny
    left.set(0)
    right.set(0)
    for i in range(NUM_LEDS):
        np[i] = (0, 0, 0)
    np.write()
