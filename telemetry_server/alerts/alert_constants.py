"""Constants for telemetry alert thresholds and definitions."""

# ---------------------------------------------------------------------------
# Aero / damage
# ---------------------------------------------------------------------------
DAMAGE_REFIRE_STEP = 20  # re-alert every 20 % worsening

DAMAGE_PARTS = [
    {"key": "frontLeftWingDamage",  "label": "Front left wing",  "tag": "FL WING",  "clearMsg": "front left wing damage stabilised"},
    {"key": "frontRightWingDamage", "label": "Front right wing", "tag": "FR WING",  "clearMsg": "front right wing damage stabilised"},
    {"key": "rearWingDamage",       "label": "Rear wing",        "tag": "RR WING",  "clearMsg": "rear wing damage stabilised"},
    {"key": "floorDamage",          "label": "Floor",            "tag": "FLOOR",    "clearMsg": "floor damage stabilised"},
    {"key": "diffuserDamage",       "label": "Diffuser",         "tag": "DIFF",     "clearMsg": "diffuser damage stabilised"},
    {"key": "sidepodDamage",        "label": "Sidepod",          "tag": "SIDEPOD",  "clearMsg": "sidepod damage stabilised"},
]

BRAKE_TEMPS = [
    {"key": "brakeTempFL", "label": "FL brake", "tag": "BRK FL"},
    {"key": "brakeTempFR", "label": "FR brake", "tag": "BRK FR"},
    {"key": "brakeTempRL", "label": "RL brake", "tag": "BRK RL"},
    {"key": "brakeTempRR", "label": "RR brake", "tag": "BRK RR"},
]

# ---------------------------------------------------------------------------
# Tyres
# ---------------------------------------------------------------------------
TYRE_DAMAGE_REFIRE_STEP = 50  # re-alert every step when worsening (0-255 scale)

TYRE_WHEEL_LABELS = {"fl": "FL", "fr": "FR", "rl": "RL", "rr": "RR"}
TYRE_WHEELS = ("fl", "fr", "rl", "rr")
TYRE_DAMAGE_METRICS = {"dmg", "blst", "wear"}

TYRE_CLEAR_LABELS = {
    "temp": "temp back to normal",
    "wear": "tyre wear stabilised",
    "dmg": "tyre damage stabilised",
    "blst": "blistering subsided",
}

# ---------------------------------------------------------------------------
# Power unit
# ---------------------------------------------------------------------------
PU_DAMAGE_REFIRE_STEP = 20  # re-alert every 20% worsening
PU_DAMAGE_KEYS = {"eng_dmg", "gbx_dmg"}
FUEL_RATE_MIN_LAP_FRACTION = 0.2  # drive 20 % of a lap before the first burn rate estimate
FUEL_MAX_DISTANCE_STEP = 200.0  # metres between two samples; a larger jump is a teleport (garage, flashback)
FUEL_MAX_DROP_STEP = 0.2  # kg between two samples; a larger drop is a game fuel deduction, not burn

PU_ALERT_DEFS = {
    "eng_temp": {"tag": "TEMP", "clearMsg": "engine temp back to normal"},
    "eng_dmg":  {"tag": "ICE",  "clearMsg": "engine damage stabilised"},
    "gbx_dmg":  {"tag": "GBX",  "clearMsg": "gearbox damage stabilised"},
    "fuel":     {"tag": "FUEL", "clearMsg": "fuel delta recovered"},
    "fuel_lap": {"tag": "FUEL", "clearMsg": "fuel sufficient to finish lap"},
    "battery":  {"tag": "ERS",  "clearMsg": "battery SOC recovered"},
}
