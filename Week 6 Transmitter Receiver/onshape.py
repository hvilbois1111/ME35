"""
Tiny Onshape API helper for MicroPython (ESP32).

  connect_wifi()          -> join the network in config.py
  get_mates()             -> GET  .../matevalues  (list of mate dicts)
  find_mate(mates, name)  -> pick one mate out of that list by its name
  set_mates(entries)      -> POST .../matevalues
  entry(mate, rad)        -> the POST entry that sets that mate to rad

Mate angles in the API are radians, in the 'rotationZ' field.

Speed: instead of the requests library (which opens a new HTTPS connection,
with a slow TLS handshake, for every call), this keeps ONE connection open
and reuses it (HTTP/1.1 keep-alive). If it drops, it reconnects and retries
once automatically.
"""

import network
import socket
import ssl
import time
import json
import gc
import ubinascii

import config

HOST = "cad.onshape.com"
PATH = ("/api/v10/assemblies/d/%s/w/%s/e/%s/matevalues"
        % (config.DID, config.WID, config.EID))

# Basic auth with API keys: base64("access_key:secret_key")
_token = ubinascii.b2a_base64(
    ("%s:%s" % (config.ACCESS_KEY, config.SECRET_KEY)).encode()
).decode().strip()


# =====================================================================
# WIFI
# =====================================================================
def _reset_radio(wlan):
    # A soft reboot (Stop/Run in Thonny) leaves the radio mid-connect, and
    # calling connect() again then raises "Wifi Internal State Error".
    # Power-cycling the interface clears that.
    try:
        wlan.disconnect()
    except OSError:
        pass
    wlan.active(False)
    time.sleep_ms(500)
    wlan.active(True)
    time.sleep_ms(500)


def connect_wifi(timeout_ms=20000, attempts=3):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if wlan.isconnected():
        print("WiFi OK:", wlan.ifconfig()[0])
        return wlan

    for attempt in range(1, attempts + 1):
        print("Connecting to %s (try %d)..." % (config.WIFI_SSID, attempt))
        _reset_radio(wlan)
        try:
            wlan.connect(config.WIFI_SSID, config.WIFI_PASS)
        except OSError as e:
            print("  connect() error:", e)
            continue
        t0 = time.ticks_ms()
        while not wlan.isconnected():
            if time.ticks_diff(time.ticks_ms(), t0) > timeout_ms:
                print("  timed out, status =", wlan.status())
                break
            time.sleep_ms(200)
        if wlan.isconnected():
            print("WiFi OK:", wlan.ifconfig()[0])
            return wlan
    raise RuntimeError("WiFi failed after %d tries" % attempts)


# =====================================================================
# PERSISTENT HTTPS CONNECTION
# =====================================================================
def _readn(s, n):
    buf = b""
    while len(buf) < n:
        chunk = s.read(n - len(buf))
        if not chunk:
            raise OSError("connection closed mid-body")
        buf += chunk
    return buf


class _Conn:
    def __init__(self):
        self.s = None

    def close(self):
        if self.s:
            try:
                self.s.close()
            except Exception:
                pass
        self.s = None

    def _open(self):
        gc.collect()
        ai = socket.getaddrinfo(HOST, 443, 0, socket.SOCK_STREAM)[0]
        s = socket.socket(ai[0], ai[1], ai[2])
        s.settimeout(10)
        s.connect(ai[-1])
        self.s = ssl.wrap_socket(s, server_hostname=HOST)

    def _do(self, method, data):
        s = self.s
        head = ("%s %s HTTP/1.1\r\n"
                "Host: %s\r\n"
                "Authorization: Basic %s\r\n"
                "Accept: application/json;charset=UTF-8; qs=0.09\r\n"
                "Content-Type: application/json\r\n"
                "Content-Length: %d\r\n"
                "Connection: keep-alive\r\n\r\n"
                % (method, PATH, HOST, _token, len(data)))
        s.write(head.encode())
        if data:
            s.write(data)

        line = s.readline()
        if not line:
            raise OSError("connection closed")
        status = int(line.split(None, 2)[1])

        length = None
        chunked = False
        close = False
        while True:
            l = s.readline()
            if not l or l == b"\r\n":
                break
            k, _, v = l.decode().partition(":")
            k = k.strip().lower()
            v = v.strip().lower()
            if k == "content-length":
                length = int(v)
            elif k == "transfer-encoding" and "chunked" in v:
                chunked = True
            elif k == "connection" and v == "close":
                close = True

        if chunked:
            parts = []
            while True:
                n = int(s.readline().split(b";")[0].strip(), 16)
                if n == 0:
                    while True:            # skip trailers
                        l = s.readline()
                        if not l or l == b"\r\n":
                            break
                    break
                parts.append(_readn(s, n))
                s.readline()               # CRLF after each chunk
            body = b"".join(parts)
        elif length is not None:
            body = _readn(s, length)
        else:
            body = s.read()                # no length: read to EOF
            close = True

        if close:
            self.close()
        return status, body

    def request(self, method, body=None):
        data = body.encode() if body else b""
        for attempt in (1, 2):
            try:
                if self.s is None:
                    self._open()
                return self._do(method, data)
            except Exception:
                self.close()               # stale connection: reopen, retry once
                if attempt == 2:
                    raise


_conn = _Conn()


def _check(status, body, what):
    if status != 200:
        raise RuntimeError("%s failed (%d): %s" % (what, status, body[:300]))


# =====================================================================
# API CALLS
# =====================================================================
def get_mates():
    """Return the assembly's mate list, e.g.
    [{'featureId': 'Mxx...', 'mateName': 'Shoulder',
      'jsonType': 'Cylindrical', 'rotationZ': 1.5708, ...}, ...]"""
    status, body = _conn.request("GET")
    _check(status, body, "GET matevalues")
    return json.loads(body)["mateValues"]


def set_mates(entries):
    """POST a list of mate entries (build them with entry())."""
    status, body = _conn.request("POST", json.dumps({"mateValues": entries}))
    _check(status, body, "POST matevalues")


def find_mate(mates, name):
    for m in mates:
        if m.get("mateName") == name:
            return m
    names = [m.get("mateName") for m in mates]
    raise RuntimeError("No mate named %r. Mates found: %s" % (name, names))


def entry(mate, radians):
    """POST entry that sets a mate's rotationZ, copied from what GET returned.
    Works for Revolute and Cylindrical mates; a Cylindrical mate's
    translationZ is resent unchanged so the joint doesn't slide."""
    e = {"featureId": mate["featureId"], "rotationZ": radians,
         "ownerOccurrencePath": mate.get("ownerOccurrencePath", [])}  # required
    for k in ("mateName", "jsonType", "translationZ"):
        if k in mate:
            e[k] = mate[k]
    return e


def print_mates(mates):
    print("Mates in assembly:")
    for m in mates:
        rz = m.get("rotationZ")
        deg = "" if rz is None else "  rotationZ=%.1f deg" % (rz * 57.29578)
        print("  %-20s %-10s id=%s%s" % (m.get("mateName"), m.get("jsonType"),
                                         m.get("featureId"), deg))
