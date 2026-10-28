# veml6040.py - minimal MicroPython driver for the Vishay VEML6040 RGBW color sensor
# (Seeed Grove 101021133). I2C address 0x10, 16-bit little-endian registers.
#   0x00 CONF : bits 6:4 integration time, bit 2 TRIG, bit 1 AF, bit 0 SD (1 = shutdown)
#   0x08 R, 0x09 G, 0x0A B, 0x0B W  (read-only, 16-bit)
import time

_ADDR = 0x10
_REG_CONF = 0x00
_REG_R, _REG_G, _REG_B, _REG_W = 0x08, 0x09, 0x0A, 0x0B
_IT_CODES = {40: 0, 80: 1, 160: 2, 320: 3, 640: 4, 1280: 5}


class VEML6040:
    def __init__(self, i2c, integration_ms=160):
        self.i2c = i2c
        if _ADDR not in i2c.scan():
            raise OSError("VEML6040 not found at 0x10 - check the Grove 2 cable")
        if integration_ms not in _IT_CODES:
            raise ValueError("integration_ms must be one of %s" % sorted(_IT_CODES))
        self.integration_ms = integration_ms
        conf = _IT_CODES[integration_ms] << 4          # auto mode, sensor enabled
        i2c.writeto_mem(_ADDR, _REG_CONF, bytes([conf, 0x00]))
        time.sleep_ms(integration_ms + 20)              # wait for first reading

    def _read(self, reg):
        data = self.i2c.readfrom_mem(_ADDR, reg, 2)
        return data[0] | (data[1] << 8)

    def rgbw(self):
        return (self._read(_REG_R), self._read(_REG_G),
                self._read(_REG_B), self._read(_REG_W))

    def brightness(self):
        """White channel = overall light level. Drops sharply when covered."""
        return self._read(_REG_W)
