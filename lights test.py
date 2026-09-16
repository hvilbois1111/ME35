import neopixel #importing the library
from machine import Pin # another way of importing a library
import time

np = neopixel.NeoPixel(Pin(15),2) # 0 is the Pin for neopixel and 4 is the number of lights

btn = Pin(34, Pin.IN, Pin.PULL_UP) 
DEBOUNCE_MS = 20

    
while True:
    if btn.value() == 0:
        time.sleep_ms(DEBOUNCE_MS)
        if btn.value() == 0:
            print("button.pressed")
            np[0] = (0,0,0)
            np.write()
            while btn.value() == 0:
                pass
