"""
Shared settings. Put this same file on BOTH ESP32s (yours and your partner's).
Don't post it publicly (Notion portfolio, GitHub): it holds your API keys.
"""

# ---- WiFi ----
#WIFI_SSID = "tufts_eecs"
#WIFI_PASS = "foundedin1883"

WIFI_SSID = "steezas n geezas"
WIFI_PASS = "steezers69!"

# ---- Onshape API keys (from dev-portal.onshape.com) ----
ACCESS_KEY = "on_oKT7cZzGzRijZXgJQ27am"
SECRET_KEY = "kBONYjS2E6T8EQZMrKCCyYRLFZ8dSnxb8GrLwUtrZw96HivU"

# ---- The assembly, taken from its URL ----
# https://cad.onshape.com/documents/<DID>/w/<WID>/e/<EID>
DID = "24f4c71469bc8dd4a6875393"
WID = "f1da27f458dbc80b354f8646"
EID = "88ad699ae43d8a930c28a0af"

# ---- Mate names, exactly as they appear in the assembly's mate list ----
# On startup both boards print every mate the API finds, so if these
# names are wrong you'll see the right ones in the REPL.
# NOTE: swapped on purpose. In the CAD, the mate named "Elbow" is the one
# that actually sits at the shoulder joint, and vice versa.
SHOULDER_MATE = "Elbow"      # Cylindrical, featureId MoMKhn3C7qV+kDBHU
ELBOW_MATE = "Shoulder"      # Cylindrical, featureId MKJjq7UEYoA3NRlAy
