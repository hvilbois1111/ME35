# veml6040.py
# Minimal MicroPython driver for the Vishay VEML6040 RGBW light sensor
# (the chip on the Seeed Grove Color Sensor V3.0).
#
# NOTE: the VEML6040 has a FIXED I2C address (0x10), so two of them cannot
# share one I2C bus. robot_hw.py puts each sensor on its own Grove port.

import time

ADDR = 0x10

REG_CONF = 0x00
REG_R = 0x08
REG_G = 0x09
REG_B = 0x0A
REG_W = 0x0B

# Integration time (ms) -> IT[6:4] bits of the config register.
# Shorter = faster updates but less sensitive.
IT_BITS = {40: 0, 80: 1, 160: 2, 320: 3, 640: 4, 1280: 5}


class VEML6040:
    def __init__(self, i2c, it_ms=40):
        self.i2c = i2c
        self.it_ms = it_ms
        self.set_integration(it_ms)

    def set_integration(self, it_ms):
        # AF=0 (auto / continuous measuring), TRIG=0, SD=0 (sensor on)
        conf = IT_BITS[it_ms] << 4
        self.i2c.writeto_mem(ADDR, REG_CONF, bytes([conf, 0x00]))
        self.it_ms = it_ms
        time.sleep_ms(it_ms + 10)  # let the first measurement finish

    def _read(self, reg):
        d = self.i2c.readfrom_mem(ADDR, reg, 2)  # little-endian 16-bit
        return d[0] | (d[1] << 8)

    def rgbw(self):
        """Return (red, green, blue, white) raw counts, 0..65535."""
        return (self._read(REG_R), self._read(REG_G),
                self._read(REG_B), self._read(REG_W))
