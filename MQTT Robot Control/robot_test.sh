#!/bin/bash
# Mac version of robot_test.bat: pretend to be the professor and publish Homework 9 commands.
# Run in Terminal:   bash robot_test.sh            (broker on this Mac)
#              or:   bash robot_test.sh 10.5.x.x   (broker on another computer)

BROKER="${1:-localhost}"
PUB="$(command -v mosquitto_pub)"
[ -z "$PUB" ] && PUB=/opt/homebrew/bin/mosquitto_pub
[ -x "$PUB" ] || PUB=/usr/local/bin/mosquitto_pub
if [ ! -x "$PUB" ]; then
  echo "mosquitto_pub not found. Install it with: brew install mosquitto"
  exit 1
fi

pub() { "$PUB" -h "$BROKER" -p 1883 -t "$1" -m "$2" && echo "  sent $1 -> $2"; }
leds() { for i in 0 1; do pub "ME35/led/$i" "{\"r\": $1, \"g\": $2, \"b\": $3}"; done; }

echo "Publishing to broker at $BROKER"
while true; do
  echo
  echo " DIRECTION:  w=forward  s=backward  a=left  d=right  x=stop"
  echo " SPEED:      1=20  2=50  3=100  0=0  p=type a speed"
  echo " LEDS:       r=red  g=green  b=blue  m=magenta  o=off"
  echo " q=quit"
  read -rsn1 -p "Command: " k
  echo "$k"
  case "$k" in
    w|W) pub ME35/direction forward ;;
    s|S) pub ME35/direction backward ;;
    a|A) pub ME35/direction left ;;
    d|D) pub ME35/direction right ;;
    x|X) pub ME35/direction stop ;;
    1) pub ME35/speed 20 ;;
    2) pub ME35/speed 50 ;;
    3) pub ME35/speed 100 ;;
    0) pub ME35/speed 0 ;;
    p|P) read -rp "Speed (0-100): " spd; pub ME35/speed "$spd" ;;
    r|R) leds 255 0 0 ;;
    g|G) leds 0 255 0 ;;
    b|B) leds 0 0 255 ;;
    m|M) leds 255 0 122 ;;
    o|O) leds 0 0 0 ;;
    q|Q) exit 0 ;;
    *) echo "  unknown key" ;;
  esac
done
