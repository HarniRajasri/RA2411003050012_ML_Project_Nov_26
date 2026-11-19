"""Shared vocabulary. Wording is deliberate: these are *estimates*, never certainties."""

# Estimated attention states (backend fusion output)
ATTN_ENGAGED = "ENGAGED"                       # shown as "Estimated engaged"
ATTN_DRIFT = "POSSIBLE_ATTENTION_DRIFT"        # shown as "Possible attention drift"

# Motion states reported by the headband firmware
MOTION_STATES = ("NORMAL", "MOVING", "POSSIBLE_ATTENTION_DRIFT", "FEEDBACK")

# Device connection status
DEV_CONNECTED = "CONNECTED"
DEV_RECONNECTING = "RECONNECTING"     # heartbeat late, not yet timed out
DEV_DISCONNECTED = "DISCONNECTED"

# Data provenance
SRC_REAL = "REAL"
SRC_SIM = "SIMULATED"
SIM_PREFIX = "SIM-"

CLASS_ACTIVE = "ACTIVE"
CLASS_ENDED = "ENDED"

EV_CONNECTED = "CONNECTED"
EV_DISCONNECTED = "DISCONNECTED"
EV_RECONNECTED = "RECONNECTED"

FB_TRIGGERED = "FEEDBACK_TRIGGERED"
FB_ACKNOWLEDGED = "FEEDBACK_ACKNOWLEDGED"
