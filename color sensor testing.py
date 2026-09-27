from machine import Pin, I2C
from machine import SoftI2C
i2c = I2C(0, sda=Pin(21), scl=Pin(22), freq=400000)
print(i2c.scan())
import time

import veml6040

sensor = veml6040.VEML6040(i2c)

sensor.trigger_measurement()
while True:
    red, green, blue, white = sensor.read_rgbw()
    print(red, green, blue, white)
    print(red/white, green/white, blue/white)
    time.sleep(1)
