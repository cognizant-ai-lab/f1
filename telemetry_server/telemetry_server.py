"""WebSocket bridge that streams live F1 25 telemetry from UDP to the
race_engineer_hub web app.

Usage:
    python telemetry_server.py

Listens on UDP 20777 for F1 25 telemetry packets and exposes a WebSocket
server on port 8765.  The web app connects to ws://localhost:8765 and
receives JSON frames with the latest telemetry state (tyres + power unit).
"""

import argparse
import asyncio
import csv
import json
import os
import socket
import time
from pathlib import Path

import websockets

from telemetry_server.agents.damage_agent import DamageAgent
from telemetry_server.agents.power_unit_agent import PowerUnitAgent
from telemetry_server.agents.race_engineer_agent import RaceEngineerAgent
from telemetry_server.agents.tyres_agent import TyresAgent

# ---------------------------------------------------------------------------
# Re-use constants, struct definitions, and parser from f1_telemetry_parser.py
# ---------------------------------------------------------------------------
from telemetry_server.f1_telemetry_parser import (
    F1TelemetryParser,
    PACKET_ID_SESSION,
    NUM_CARS,
    PACKET_ID_CAR_TELEMETRY,
    WHEEL_NAMES,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
UDP_IP = "0.0.0.0"
UDP_PORT = 20777
WS_HOST = "0.0.0.0"
WS_PORT = 8765

# ---------------------------------------------------------------------------
# Shared state – written by the UDP reader, read by WebSocket handlers
# ---------------------------------------------------------------------------
lap_state: dict = {}
status_state: dict = {}
damage_state: dict = {}
telemetry_state: dict = {}
setup_state: dict = {}
motion_ex_state: dict = {}
session_state: dict = {}
session_time: float = 0.0
prev_session_uid: int = 0

# Track map state – world positions for all cars + all-car lap data
motion_positions: list[dict] = []
all_lap_data: list[dict] = []
participants: list[dict] = []
player_car_idx: int = 0

# Alert state – computed server-side and sent pre-computed via WebSocket
aero_alert_conditions: dict = {}   # key -> {"level": "warn"|"crit", "value": float}
aero_alerts_log: list = []         # accumulated alerts
prev_aero_session_time: float = 0.0

tyre_alert_conditions: dict = {}
tyre_alerts_log: list = []
prev_tyre_session_time: float = 0.0
prev_tyre_compound: str = ""

pu_alert_conditions: dict = {}
pu_alerts_log: list = []
prev_pu_session_time: float = 0.0
prev_pu_ers_mode: str = ""
prev_pu_fuel_mix: str = ""

# DamageAgent state
damage_agent: DamageAgent | None = None
damage_agent_response: str | None = None
damage_agent_response_time: str | None = None
damage_agent_in_flight: bool = False
damage_agent_pending: list[str] = []
damage_agent_batch_handle: asyncio.TimerHandle | None = None
DAMAGE_AGENT_BATCH_DELAY: float = 1.0  # seconds to wait before flushing

# TyresAgent state
tyres_agent: TyresAgent | None = None
tyres_agent_response: str | None = None
tyres_agent_response_time: str | None = None
tyres_agent_in_flight: bool = False
tyres_agent_pending: list[str] = []
tyres_agent_batch_handle: asyncio.TimerHandle | None = None
TYRES_AGENT_BATCH_DELAY: float = 1.0  # seconds to wait before flushing

# PowerUnitAgent state
pu_agent: PowerUnitAgent | None = None
pu_agent_response: str | None = None
pu_agent_response_time: str | None = None
pu_agent_in_flight: bool = False
pu_agent_pending: list[str] = []
pu_agent_batch_handle: asyncio.TimerHandle | None = None
PU_AGENT_BATCH_DELAY: float = 1.0  # seconds to wait before flushing

# RaceEngineerAgent state
re_agent: RaceEngineerAgent | None = None
re_agent_in_flight: bool = False
re_agent_pending: list[str] = []
re_agent_batch_handle: asyncio.TimerHandle | None = None
re_alerts_log: list = []       # accumulated messages received by the race engineer
re_responses_log: list = []    # accumulated race engineer responses (split per target)
RE_AGENT_BATCH_DELAY: float = 2.0  # longer window to batch multiple engineer reports

# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------
SESSION_TYPE_LABELS = {
    0: "UNKNOWN", 1: "P1", 2: "P2", 3: "P3", 4: "SHORT PRACTICE",
    5: "Q1", 6: "Q2", 7: "Q3", 8: "SHORT QUALIFYING", 9: "OSQ",
    10: "RACE", 11: "RACE 2", 12: "RACE 3", 13: "TIME TRIAL",
    14: "SQ1", 15: "RACE SHORT", 16: "SQ3", 17: "SPRINT",
}

TRACK_NAMES = {
    0: "AUSTRALIAN GP", 1: "FRENCH GP", 2: "CHINESE GP", 3: "BAHRAIN GP",
    4: "SPANISH GP", 5: "MONACO GP", 6: "CANADIAN GP", 7: "BRITISH GP",
    8: "GERMAN GP", 9: "HUNGARIAN GP", 10: "BELGIAN GP", 11: "ITALIAN GP",
    12: "SINGAPORE GP", 13: "JAPANESE GP", 14: "ABU DHABI GP", 15: "UNITED STATES GP",
    16: "BRAZILIAN GP", 17: "AUSTRIAN GP", 18: "RUSSIAN GP", 19: "MEXICAN GP",
    20: "AZERBAIJAN GP", 21: "BAHRAIN SHORT", 22: "BRITISH SHORT",
    23: "US SHORT", 24: "JAPANESE SHORT", 25: "VIETNAMESE GP", 26: "DUTCH GP",
    27: "EMILIA ROMAGNA GP", 28: "PORTUGUESE GP", 29: "SAUDI ARABIAN GP", 30: "MIAMI GP",
    31: "LAS VEGAS GP", 32: "QATAR GP", 33: "QATAR GP",
}

connected_clients: set = set()

# ---------------------------------------------------------------------------
# CSV capture
# ---------------------------------------------------------------------------
CSV_FIELDNAMES = [
    "wall_time", "session_uid", "session_time", "frame_id",
    # Session
    "session_type", "track_name", "session_time_left", "track_length",
    "player_car_index",
    # Lap
    "current_lap_num", "car_position", "lap_distance_m",
    "last_lap_time_ms", "current_lap_time_ms",
    # Car dynamics
    "speed_kmh", "gear", "drs",
    # Tyres
    "tyre_compound_actual", "tyre_compound_visual", "tyres_age_laps",
]
for _metric in (
    "tyre_wear", "tyre_damage", "tyre_blisters",
    "tyre_surface_temp", "tyre_inner_temp", "tyre_pressure", "brake_temp",
):
    for _wn in WHEEL_NAMES:
        CSV_FIELDNAMES.append(f"{_metric}_{_wn}")
CSV_FIELDNAMES += [
    # Power unit
    "engine_rpm", "engine_temp",
    "fuel_in_tank", "fuel_remaining_laps", "fuel_mix",
    "engine_power_ice_w", "engine_power_mguk_w",
    "ers_store_energy_j", "ers_deploy_mode",
    "ers_deployed_this_lap_j", "ers_harvested_mguk_j", "ers_harvested_mguh_j",
    "engine_damage", "gearbox_damage",
    # Aero
    "front_wing_setup", "rear_wing_setup", "brake_bias",
    "front_ride_height_mm", "rear_ride_height_mm",
    "front_left_wing_damage", "front_right_wing_damage", "rear_wing_damage",
    "floor_damage", "diffuser_damage", "sidepod_damage", "drs_fault",
]
# Per-car track map columns (22 cars)
for _ci in range(NUM_CARS):
    CSV_FIELDNAMES += [
        f"car{_ci}_x", f"car{_ci}_z",
        f"car{_ci}_position", f"car{_ci}_lap_distance",
        f"car{_ci}_driver_status", f"car{_ci}_result_status",
        f"car{_ci}_driver_id", f"car{_ci}_team_id",
        f"car{_ci}_abbreviation", f"car{_ci}_team_abbreviation",
    ]


class CsvCapture:
    """Manages one CSV file per session_uid."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(exist_ok=True)
        self._current_uid: int | None = None
        self._file = None
        self._writer: csv.DictWriter | None = None

    def _open_file(self, session_uid: int):
        """Open a new CSV for the given session."""
        self.close()
        self._current_uid = session_uid

        track_id = session_state.get("track_id", -1)
        session_type = session_state.get("session_type", 0)
        gp = TRACK_NAMES.get(track_id, f"track_{track_id}").replace(" ", "_").lower()
        sess = SESSION_TYPE_LABELS.get(session_type, f"session_{session_type}").replace(" ", "_").lower()
        ts = time.strftime("%Y%m%d-%H%M%S")

        path = self.data_dir / f"f1_25_{gp}_{sess}_{ts}.csv"
        self._file = path.open("w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._file, fieldnames=CSV_FIELDNAMES)
        self._writer.writeheader()
        self._file.flush()
        print(f"CSV capture started: {path}")

    def write_row(self, session_uid: int, session_time: float, frame_id: int):
        if not session_state:
            return  # Wait until session packet provides GP/session info
        if session_uid != self._current_uid:
            self._open_file(session_uid)

        row = {
            "wall_time": time.time(),
            "session_uid": session_uid,
            "session_time": session_time,
            "frame_id": frame_id,
            # Session
            "session_type": SESSION_TYPE_LABELS.get(
                session_state.get("session_type", 0), "unknown"
            ),
            "track_name": TRACK_NAMES.get(session_state.get("track_id", -1), "unknown"),
            "session_time_left": session_state.get("session_time_left", 0),
            "track_length": session_state.get("track_length", 0),
            "player_car_index": player_car_idx,
            # Lap
            "current_lap_num": lap_state.get("current_lap_num", ""),
            "car_position": lap_state.get("car_position", ""),
            "lap_distance_m": lap_state.get("lap_distance_m", ""),
            "last_lap_time_ms": lap_state.get("last_lap_time_ms", ""),
            "current_lap_time_ms": lap_state.get("current_lap_time_ms", ""),
            # Car dynamics
            "speed_kmh": telemetry_state.get("speed_kmh", ""),
            "gear": telemetry_state.get("gear", ""),
            "drs": telemetry_state.get("drs", ""),
            # Tyres
            "tyre_compound_actual": status_state.get("tyre_compound_actual", ""),
            "tyre_compound_visual": status_state.get("tyre_compound_visual", ""),
            "tyres_age_laps": status_state.get("tyres_age_laps", ""),
            # Power unit
            "engine_rpm": telemetry_state.get("engine_rpm", ""),
            "engine_temp": telemetry_state.get("engine_temp", ""),
            "fuel_in_tank": status_state.get("fuel_in_tank", ""),
            "fuel_remaining_laps": status_state.get("fuel_remaining_laps", ""),
            "fuel_mix": status_state.get("fuel_mix", ""),
            "engine_power_ice_w": status_state.get("engine_power_ice", ""),
            "engine_power_mguk_w": status_state.get("engine_power_mguk", ""),
            "ers_store_energy_j": status_state.get("ers_store_energy", ""),
            "ers_deploy_mode": status_state.get("ers_deploy_mode", ""),
            "ers_deployed_this_lap_j": status_state.get("ers_deployed_this_lap", ""),
            "ers_harvested_mguk_j": status_state.get("ers_harvested_mguk", ""),
            "ers_harvested_mguh_j": status_state.get("ers_harvested_mguh", ""),
            "engine_damage": damage_state.get("engine_damage", ""),
            "gearbox_damage": damage_state.get("gearbox_damage", ""),
            # Aero
            "front_wing_setup": setup_state.get("front_wing", ""),
            "rear_wing_setup": setup_state.get("rear_wing", ""),
            "brake_bias": status_state.get("front_brake_bias", ""),
            "front_ride_height_mm": motion_ex_state.get("front_aero_height", ""),
            "rear_ride_height_mm": motion_ex_state.get("rear_aero_height", ""),
            "front_left_wing_damage": damage_state.get("front_left_wing_damage", ""),
            "front_right_wing_damage": damage_state.get("front_right_wing_damage", ""),
            "rear_wing_damage": damage_state.get("rear_wing_damage", ""),
            "floor_damage": damage_state.get("floor_damage", ""),
            "diffuser_damage": damage_state.get("diffuser_damage", ""),
            "sidepod_damage": damage_state.get("sidepod_damage", ""),
            "drs_fault": damage_state.get("drs_fault", ""),
        }
        # Per-wheel tyre metrics
        for wn in WHEEL_NAMES:
            row[f"tyre_wear_{wn}"] = damage_state.get(f"tyre_wear_{wn}", "")
            row[f"tyre_damage_{wn}"] = damage_state.get(f"tyre_damage_{wn}", "")
            row[f"tyre_blisters_{wn}"] = damage_state.get(f"tyre_blisters_{wn}", "")
            row[f"tyre_surface_temp_{wn}"] = telemetry_state.get(f"tyre_surface_temp_{wn}", "")
            row[f"tyre_inner_temp_{wn}"] = telemetry_state.get(f"tyre_inner_temp_{wn}", "")
            row[f"tyre_pressure_{wn}"] = telemetry_state.get(f"tyre_pressure_{wn}", "")
            row[f"brake_temp_{wn}"] = telemetry_state.get(f"brake_temp_{wn}", "")

        # Per-car track map data
        for ci in range(NUM_CARS):
            m = motion_positions[ci] if ci < len(motion_positions) else {}
            lap = all_lap_data[ci] if ci < len(all_lap_data) else {}
            part = participants[ci] if ci < len(participants) else {}
            row[f"car{ci}_x"] = m.get("world_position_x", "")
            row[f"car{ci}_z"] = m.get("world_position_z", "")
            row[f"car{ci}_position"] = lap.get("position", "")
            row[f"car{ci}_lap_distance"] = lap.get("lap_distance", "")
            row[f"car{ci}_driver_status"] = lap.get("driver_status", "")
            row[f"car{ci}_result_status"] = lap.get("result_status", "")
            row[f"car{ci}_driver_id"] = part.get("driver_id", "")
            row[f"car{ci}_team_id"] = part.get("team_id", "")
            row[f"car{ci}_abbreviation"] = part.get("abbreviation", "")
            row[f"car{ci}_team_abbreviation"] = part.get("team_abbreviation", "")

        self._writer.writerow(row)
        self._file.flush()

    def close(self):
        if self._file:
            self._file.close()
            self._file = None
            self._writer = None
            self._current_uid = None


csv_capture: CsvCapture | None = None


# ---------------------------------------------------------------------------
# Aero alert constants & processing
# ---------------------------------------------------------------------------
DAMAGE_REFIRE_STEP = 10  # re-alert every 10 % worsening

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


def _format_session_time(seconds: float) -> str:
    """Format session time in seconds as MM:SS."""
    total = int(seconds)
    m = total // 60
    s = total % 60
    return f"{m:02d}:{s:02d}"


def _is_copy_ack(text: str) -> bool:
    """Return True if the text is a bare 'Copy' acknowledgment, ignoring markdown bold."""
    return text.strip().strip("*").strip().lower() == "copy"


WEATHER_LABELS = {
    0: "Clear", 1: "Light Cloud", 2: "Overcast",
    3: "Light Rain", 4: "Heavy Rain", 5: "Storm",
}


def _build_session_context() -> str:
    """Build a human-readable session context string from the current session state."""
    session_type = SESSION_TYPE_LABELS.get(session_state.get("session_type", 0), "Unknown")
    track = TRACK_NAMES.get(session_state.get("track_id", -1), "Unknown Track")
    total_laps = session_state.get("total_laps", 0)
    weather = WEATHER_LABELS.get(session_state.get("weather", 0), "Unknown")
    air_temp = session_state.get("air_temperature", 0)
    track_temp = session_state.get("track_temperature", 0)

    lines = [
        "## Current Session Context",
        f"- Session: {session_type}",
        f"- Track: {track}",
        f"- Weather: {weather}",
        f"- Air temperature: {air_temp}°C",
        f"- Track temperature: {track_temp}°C",
    ]
    if total_laps > 0:
        lines.append(f"- Total laps: {total_laps}")
    return "\n".join(lines)


def _reinit_agents(context: str) -> None:
    """Re-instantiate all agents with the given session context."""
    global damage_agent, tyres_agent, pu_agent, re_agent

    for name, cls, var_name in [
        ("DamageAgent", DamageAgent, "damage_agent"),
        ("TyresAgent", TyresAgent, "tyres_agent"),
        ("PowerUnitAgent", PowerUnitAgent, "pu_agent"),
        ("RaceEngineerAgent", RaceEngineerAgent, "re_agent"),
    ]:
        try:
            globals()[var_name] = cls(session_context=context)
            print(f"{name} re-initialized with session context")
        except Exception as exc:
            print(f"{name} re-init failed: {exc}")


def _process_aero_alerts(aero: dict) -> None:
    """Port of useAeroAlerts.ts — accumulates alerts into aero_alerts_log."""
    global aero_alert_conditions, aero_alerts_log, prev_aero_session_time
    global damage_agent_response, damage_agent_response_time, damage_agent_pending, damage_agent_batch_handle
    global re_agent_pending, re_agent_batch_handle
    global re_alerts_log, re_responses_log

    st = aero.get("sessionTime", 0.0)

    # Detect new session (session time resets)
    if st < prev_aero_session_time:
        aero_alert_conditions = {}
        aero_alerts_log = []
        damage_agent_response = None
        damage_agent_response_time = None
        damage_agent_pending = []
        if damage_agent_batch_handle is not None:
            damage_agent_batch_handle.cancel()
            damage_agent_batch_handle = None
        re_agent_pending = []
        re_alerts_log = []
        re_responses_log = []
        if re_agent_batch_handle is not None:
            re_agent_batch_handle.cancel()
            re_agent_batch_handle = None
    prev_aero_session_time = st

    new_alerts: list[dict] = []
    current_conditions: dict = {}
    ts = _format_session_time(st)

    # Damage conditions
    for part in DAMAGE_PARTS:
        val = aero.get(part["key"], 0)
        if val > 50:
            current_conditions[part["key"]] = {"level": "crit", "value": val}
        elif val > 20:
            current_conditions[part["key"]] = {"level": "warn", "value": val}

    # Brake temperatures
    for brk in BRAKE_TEMPS:
        val = aero.get(brk["key"], 0)
        if val > 1000:
            current_conditions[brk["key"]] = {"level": "crit", "value": val}
        elif val > 800:
            current_conditions[brk["key"]] = {"level": "warn", "value": val}

    # DRS fault
    if aero.get("drsFault"):
        current_conditions["drsFault"] = {"level": "crit", "value": 1}

    # Fire alerts for new, escalated, or worsened conditions
    for key, cur in current_conditions.items():
        prev = aero_alert_conditions.get(key)
        is_new = prev is None
        is_escalation = prev is not None and prev["level"] == "warn" and cur["level"] == "crit"

        part = next((p for p in DAMAGE_PARTS if p["key"] == key), None)
        is_worsened = (
            part is not None
            and prev is not None
            and prev["level"] == cur["level"]
            and cur["value"] >= prev["value"] + DAMAGE_REFIRE_STEP
        )

        if is_new or is_escalation or is_worsened:
            alert_level = "critical" if cur["level"] == "crit" else "warning"

            if key == "drsFault":
                new_alerts.append({
                    "level": "critical",
                    "message": "DRS system fault detected",
                    "time": f"{ts} DRS",
                })
            elif part is not None:
                msg = (
                    f"{part['label']} damage critical ({cur['value']}%)"
                    if cur["level"] == "crit"
                    else f"{part['label']} damage detected ({cur['value']}%)"
                )
                new_alerts.append({"level": alert_level, "message": msg, "time": f"{ts} {part['tag']}"})
            else:
                brk = next((b for b in BRAKE_TEMPS if b["key"] == key), None)
                if brk is not None:
                    msg = (
                        f"{brk['label']} temp {cur['value']}\u00b0C \u2014 overheating"
                        if cur["level"] == "crit"
                        else f"{brk['label']} temp {cur['value']}\u00b0C \u2014 running hot"
                    )
                    new_alerts.append({"level": alert_level, "message": msg, "time": f"{ts} {brk['tag']}"})
        elif prev is not None:
            # Keep the previous alerted value as baseline when no alert fires
            cur["value"] = prev["value"]

    # Detect fully cleared conditions
    for key in aero_alert_conditions:
        if key not in current_conditions:
            if key == "drsFault":
                new_alerts.append({"level": "info", "message": "DRS fault cleared", "time": f"{ts} DRS"})
            else:
                part = next((p for p in DAMAGE_PARTS if p["key"] == key), None)
                if part is not None:
                    new_alerts.append({"level": "info", "message": part["clearMsg"], "time": f"{ts} {part['tag']}"})
                else:
                    brk = next((b for b in BRAKE_TEMPS if b["key"] == key), None)
                    if brk is not None:
                        new_alerts.append({"level": "info", "message": f"{brk['label']} temp back to normal", "time": f"{ts} {brk['tag']}"})

    aero_alert_conditions = current_conditions
    aero_alerts_log.extend(new_alerts)
    return new_alerts


# ---------------------------------------------------------------------------
# Tyre alert constants & processing
# ---------------------------------------------------------------------------
TYRE_DAMAGE_REFIRE_STEP = 25  # re-alert every step when worsening (0-255 scale)

TYRE_WHEEL_LABELS = {"fl": "FL", "fr": "FR", "rl": "RL", "rr": "RR"}
TYRE_WHEELS = ("fl", "fr", "rl", "rr")
TYRE_DAMAGE_METRICS = {"dmg", "blst", "wear"}

TYRE_CLEAR_LABELS = {
    "temp": "temp back to normal",
    "wear": "tyre wear stabilised",
    "dmg": "tyre damage stabilised",
    "blst": "blistering subsided",
}


def _process_tyre_alerts(tyre_snapshot: dict) -> None:
    """Port of useTyreAlerts.ts — accumulates alerts into tyre_alerts_log."""
    global tyre_alert_conditions, tyre_alerts_log, prev_tyre_session_time, prev_tyre_compound
    global tyres_agent_response, tyres_agent_response_time, tyres_agent_pending, tyres_agent_batch_handle

    st = tyre_snapshot.get("sessionTime", 0.0)

    # Detect new session (session time resets)
    if st < prev_tyre_session_time:
        tyre_alert_conditions = {}
        tyre_alerts_log = []
        prev_tyre_compound = ""
        tyres_agent_response = None
        tyres_agent_response_time = None
        tyres_agent_pending = []
        if tyres_agent_batch_handle is not None:
            tyres_agent_batch_handle.cancel()
            tyres_agent_batch_handle = None
    prev_tyre_session_time = st

    new_alerts: list[dict] = []
    current_conditions: dict = {}
    ts = _format_session_time(st)
    tyres = tyre_snapshot.get("tyres", {})

    for wn in TYRE_WHEELS:
        t = tyres.get(wn, {})
        surface_temp = t.get("surfaceTemp", 0)
        wear = t.get("wear", 0)
        damage = t.get("damage", 0)
        blisters = t.get("blisters", 0)
        life = round(100 - wear)

        # Surface temperature
        if surface_temp > 108:
            current_conditions[f"{wn}_temp"] = {"level": "crit", "value": surface_temp}
        elif surface_temp > 103:
            current_conditions[f"{wn}_temp"] = {"level": "warn", "value": surface_temp}

        # Wear (value = wear amount, higher = worse)
        if life <= 10:
            current_conditions[f"{wn}_wear"] = {"level": "crit", "value": wear}
        elif life <= 25:
            current_conditions[f"{wn}_wear"] = {"level": "warn", "value": wear}

        # Damage
        if damage > 150:
            current_conditions[f"{wn}_dmg"] = {"level": "crit", "value": damage}
        elif damage > 50:
            current_conditions[f"{wn}_dmg"] = {"level": "warn", "value": damage}

        # Blisters
        if blisters > 150:
            current_conditions[f"{wn}_blst"] = {"level": "crit", "value": blisters}
        elif blisters > 50:
            current_conditions[f"{wn}_blst"] = {"level": "warn", "value": blisters}

    # Fire alerts for new, escalated, or worsened conditions
    for key, cur in current_conditions.items():
        prev = tyre_alert_conditions.get(key)
        underscore_idx = key.index("_")
        wn = key[:underscore_idx]
        metric = key[underscore_idx + 1:]
        label = TYRE_WHEEL_LABELS[wn]
        t = tyres.get(wn, {})
        life = round(100 - t.get("wear", 0))
        tag = metric.upper()

        is_new = prev is None
        is_escalation = prev is not None and prev["level"] == "warn" and cur["level"] == "crit"
        is_worsened = (
            metric in TYRE_DAMAGE_METRICS
            and prev is not None
            and prev["level"] == cur["level"]
            and cur["value"] >= prev["value"] + TYRE_DAMAGE_REFIRE_STEP
        )

        if is_new or is_escalation or is_worsened:
            alert_level = "critical" if cur["level"] == "crit" else "warning"

            if metric == "temp":
                msg = (
                    f"{label} surface temp {t.get('surfaceTemp', 0)}\u00b0C \u2014 overheating"
                    if cur["level"] == "crit"
                    else f"{label} surface temp {t.get('surfaceTemp', 0)}\u00b0C \u2014 approaching limit"
                )
                new_alerts.append({"level": alert_level, "message": msg, "time": f"{ts} {tag}"})
            elif metric == "wear":
                msg = (
                    f"{label} tyre life critically low at {life}%"
                    if cur["level"] == "crit"
                    else f"{label} tyre life low at {life}%"
                )
                new_alerts.append({"level": alert_level, "message": msg, "time": f"{ts} {tag}"})
            elif metric == "dmg":
                msg = (
                    f"{label} tyre damage critical ({t.get('damage', 0)}/255)"
                    if cur["level"] == "crit"
                    else f"{label} tyre damage detected ({t.get('damage', 0)}/255)"
                )
                new_alerts.append({"level": alert_level, "message": msg, "time": f"{ts} {tag}"})
            elif metric == "blst":
                msg = (
                    f"{label} severe blistering ({t.get('blisters', 0)}/255)"
                    if cur["level"] == "crit"
                    else f"{label} blistering detected ({t.get('blisters', 0)}/255)"
                )
                new_alerts.append({"level": alert_level, "message": msg, "time": f"{ts} {tag}"})
        elif prev is not None:
            # Keep the previous alerted value as baseline
            cur["value"] = prev["value"]

    # Detect fully cleared conditions
    for key in tyre_alert_conditions:
        if key not in current_conditions:
            underscore_idx = key.index("_")
            wn = key[:underscore_idx]
            metric = key[underscore_idx + 1:]
            label = TYRE_WHEEL_LABELS.get(wn, wn.upper())
            tag = metric.upper()
            clear_msg = TYRE_CLEAR_LABELS.get(metric)
            if clear_msg:
                new_alerts.append({"level": "info", "message": f"{label} {clear_msg}", "time": f"{ts} {tag}"})

    # Compound change
    compound = tyre_snapshot.get("compound", "")
    compound_visual = tyre_snapshot.get("compoundVisual", "")
    compound_key = f"{compound}_{compound_visual}"
    if compound and compound_key != prev_tyre_compound:
        prev_tyre_compound = compound_key
        new_alerts.append({
            "level": "info",
            "message": f"{compound_visual.upper()} ({compound}) fitted",
            "time": f"{ts} TYRE",
        })

    tyre_alert_conditions = current_conditions
    tyre_alerts_log.extend(new_alerts)
    return new_alerts


# ---------------------------------------------------------------------------
# Power unit alert constants & processing
# ---------------------------------------------------------------------------
PU_DAMAGE_REFIRE_STEP = 10  # re-alert every 10% worsening
PU_DAMAGE_KEYS = {"eng_dmg", "gbx_dmg"}

PU_ALERT_DEFS = {
    "eng_temp": {"tag": "TEMP", "clearMsg": "engine temp back to normal"},
    "eng_dmg":  {"tag": "ICE",  "clearMsg": "engine damage stabilised"},
    "gbx_dmg":  {"tag": "GBX",  "clearMsg": "gearbox damage stabilised"},
    "fuel":     {"tag": "FUEL", "clearMsg": "fuel delta recovered"},
    "battery":  {"tag": "ERS",  "clearMsg": "battery SOC recovered"},
}


def _process_pu_alerts(pu: dict) -> None:
    """Port of usePowerUnitAlerts.ts — accumulates alerts into pu_alerts_log."""
    global pu_alert_conditions, pu_alerts_log, prev_pu_session_time
    global prev_pu_ers_mode, prev_pu_fuel_mix
    global pu_agent_response, pu_agent_response_time, pu_agent_pending, pu_agent_batch_handle

    st = pu.get("sessionTime", 0.0)

    # Detect new session (session time resets)
    if st < prev_pu_session_time:
        pu_alert_conditions = {}
        pu_alerts_log = []
        prev_pu_ers_mode = ""
        prev_pu_fuel_mix = ""
        pu_agent_response = None
        pu_agent_response_time = None
        pu_agent_pending = []
        if pu_agent_batch_handle is not None:
            pu_agent_batch_handle.cancel()
            pu_agent_batch_handle = None
    prev_pu_session_time = st

    new_alerts: list[dict] = []
    current_conditions: dict = {}
    ts = _format_session_time(st)

    engine_temp = pu.get("engineTemp", 0)
    engine_damage = pu.get("engineDamage", 0)
    gearbox_damage = pu.get("gearboxDamage", 0)
    fuel_remaining_laps = pu.get("fuelRemainingLaps", 0)
    battery_pct = pu.get("batteryPct", 0)

    # Engine temperature
    if engine_temp > 130:
        current_conditions["eng_temp"] = {"level": "crit", "value": engine_temp}
    elif engine_temp > 120:
        current_conditions["eng_temp"] = {"level": "warn", "value": engine_temp}

    # Engine damage (0-100)
    if engine_damage > 20:
        current_conditions["eng_dmg"] = {"level": "crit", "value": engine_damage}
    elif engine_damage > 5:
        current_conditions["eng_dmg"] = {"level": "warn", "value": engine_damage}

    # Gearbox damage (0-100)
    if gearbox_damage > 20:
        current_conditions["gbx_dmg"] = {"level": "crit", "value": gearbox_damage}
    elif gearbox_damage > 5:
        current_conditions["gbx_dmg"] = {"level": "warn", "value": gearbox_damage}

    # Fuel remaining laps
    if fuel_remaining_laps < 1:
        current_conditions["fuel"] = {"level": "crit", "value": fuel_remaining_laps}
    elif fuel_remaining_laps < 3:
        current_conditions["fuel"] = {"level": "warn", "value": fuel_remaining_laps}

    # Battery SOC
    if battery_pct < 15:
        current_conditions["battery"] = {"level": "crit", "value": battery_pct}
    elif battery_pct < 30:
        current_conditions["battery"] = {"level": "warn", "value": battery_pct}

    # Fire alerts for new, escalated, or worsened conditions
    for key, cur in current_conditions.items():
        prev = pu_alert_conditions.get(key)
        defn = PU_ALERT_DEFS.get(key)
        if not defn:
            continue

        is_new = prev is None
        is_escalation = prev is not None and prev["level"] == "warn" and cur["level"] == "crit"
        is_worsened = (
            key in PU_DAMAGE_KEYS
            and prev is not None
            and prev["level"] == cur["level"]
            and cur["value"] >= prev["value"] + PU_DAMAGE_REFIRE_STEP
        )

        if is_new or is_escalation or is_worsened:
            alert_level = "critical" if cur["level"] == "crit" else "warning"

            if key == "eng_temp":
                msg = (
                    f"Engine temp {engine_temp}\u00b0C \u2014 overheating"
                    if cur["level"] == "crit"
                    else f"Engine temp {engine_temp}\u00b0C \u2014 running hot"
                )
            elif key == "eng_dmg":
                msg = (
                    f"Engine damage critical ({engine_damage}%)"
                    if cur["level"] == "crit"
                    else f"Engine damage detected ({engine_damage}%)"
                )
            elif key == "gbx_dmg":
                msg = (
                    f"Gearbox damage critical ({gearbox_damage}%)"
                    if cur["level"] == "crit"
                    else f"Gearbox damage detected ({gearbox_damage}%)"
                )
            elif key == "fuel":
                msg = (
                    f"Fuel critically low \u2014 {fuel_remaining_laps:.1f} laps remaining"
                    if cur["level"] == "crit"
                    else f"Fuel running low \u2014 {fuel_remaining_laps:.1f} laps remaining"
                )
            elif key == "battery":
                msg = (
                    f"Battery SOC critically low at {battery_pct}%"
                    if cur["level"] == "crit"
                    else f"Battery SOC low at {battery_pct}%"
                )
            else:
                continue

            new_alerts.append({"level": alert_level, "message": msg, "time": f"{ts} {defn['tag']}"})
        elif prev is not None:
            # Keep the previous alerted value as baseline
            cur["value"] = prev["value"]

    # Detect fully cleared conditions
    for key in pu_alert_conditions:
        if key not in current_conditions:
            defn = PU_ALERT_DEFS.get(key)
            if defn:
                new_alerts.append({"level": "info", "message": defn["clearMsg"], "time": f"{ts} {defn['tag']}"})

    # ERS deploy mode change
    ers_mode = pu.get("ersDeployMode", "")
    if ers_mode and ers_mode != prev_pu_ers_mode:
        if prev_pu_ers_mode:
            new_alerts.append({
                "level": "info",
                "message": f"ERS mode \u2192 {ers_mode.upper()}",
                "time": f"{ts} ERS",
            })
        prev_pu_ers_mode = ers_mode

    # Fuel mix change
    fuel_mix = pu.get("fuelMix", "")
    if fuel_mix and fuel_mix != prev_pu_fuel_mix:
        if prev_pu_fuel_mix:
            new_alerts.append({
                "level": "info",
                "message": f"Fuel mix \u2192 {fuel_mix.upper()}",
                "time": f"{ts} FUEL",
            })
        prev_pu_fuel_mix = fuel_mix

    pu_alert_conditions = current_conditions
    pu_alerts_log.extend(new_alerts)
    return new_alerts


def _queue_damage_alerts(alert_texts: list[str]) -> None:
    """Add alert texts to the pending list and (re)start the batch timer.

    Alerts that arrive within DAMAGE_AGENT_BATCH_DELAY seconds of each
    other are grouped into a single DamageAgent call.
    """
    global damage_agent_batch_handle

    damage_agent_pending.extend(alert_texts)

    # Reset the debounce timer so we keep waiting for more alerts
    if damage_agent_batch_handle is not None:
        damage_agent_batch_handle.cancel()

    loop = asyncio.get_running_loop()
    damage_agent_batch_handle = loop.call_later(
        DAMAGE_AGENT_BATCH_DELAY,
        lambda: asyncio.ensure_future(_flush_damage_agent()),
    )


async def _flush_damage_agent() -> None:
    """Drain the pending list and send the batch to the DamageAgent.

    Uses an in-flight guard so only one agent call runs at a time.
    If new alerts accumulate while the agent is busy, they are
    dispatched when the current call completes.
    """
    global damage_agent_response, damage_agent_response_time, damage_agent_in_flight, damage_agent_pending
    global damage_agent_batch_handle

    damage_agent_batch_handle = None

    if damage_agent is None or not damage_agent_pending:
        return

    if damage_agent_in_flight:
        # The in-flight call's finally-block will re-flush.
        return

    batch = damage_agent_pending
    damage_agent_pending = []

    damage_agent_in_flight = True
    try:
        response = await asyncio.to_thread(damage_agent.process_messages, batch)
        # Skip bare "Copy" acknowledgments
        if response and not _is_copy_ack(response):
            damage_agent_response = response
            damage_agent_response_time = _format_session_time(prev_aero_session_time)
            _queue_race_engineer([f"From Damage Engineer: {response}"])
    except Exception as exc:
        print(f"DamageAgent error: {exc}")
    finally:
        damage_agent_in_flight = False

    # If more alerts arrived while we were busy, flush again
    if damage_agent_pending:
        await _flush_damage_agent()


def _queue_tyres_alerts(alert_texts: list[str]) -> None:
    """Add alert texts to the pending list and (re)start the batch timer."""
    global tyres_agent_batch_handle

    tyres_agent_pending.extend(alert_texts)

    if tyres_agent_batch_handle is not None:
        tyres_agent_batch_handle.cancel()

    loop = asyncio.get_running_loop()
    tyres_agent_batch_handle = loop.call_later(
        TYRES_AGENT_BATCH_DELAY,
        lambda: asyncio.ensure_future(_flush_tyres_agent()),
    )


async def _flush_tyres_agent() -> None:
    """Drain the pending list and send the batch to the TyresAgent."""
    global tyres_agent_response, tyres_agent_response_time, tyres_agent_in_flight, tyres_agent_pending
    global tyres_agent_batch_handle

    tyres_agent_batch_handle = None

    if tyres_agent is None or not tyres_agent_pending:
        return

    if tyres_agent_in_flight:
        return

    batch = tyres_agent_pending
    tyres_agent_pending = []

    tyres_agent_in_flight = True
    try:
        response = await asyncio.to_thread(tyres_agent.process_messages, batch)
        # Skip bare "Copy" acknowledgments
        if response and not _is_copy_ack(response):
            tyres_agent_response = response
            tyres_agent_response_time = _format_session_time(prev_tyre_session_time)
            _queue_race_engineer([f"From Tyres Engineer: {response}"])
    except Exception as exc:
        print(f"TyresAgent error: {exc}")
    finally:
        tyres_agent_in_flight = False

    if tyres_agent_pending:
        await _flush_tyres_agent()


def _queue_pu_alerts(alert_texts: list[str]) -> None:
    """Add alert texts to the pending list and (re)start the batch timer."""
    global pu_agent_batch_handle

    pu_agent_pending.extend(alert_texts)

    if pu_agent_batch_handle is not None:
        pu_agent_batch_handle.cancel()

    loop = asyncio.get_running_loop()
    pu_agent_batch_handle = loop.call_later(
        PU_AGENT_BATCH_DELAY,
        lambda: asyncio.ensure_future(_flush_pu_agent()),
    )


async def _flush_pu_agent() -> None:
    """Drain the pending list and send the batch to the PowerUnitAgent."""
    global pu_agent_response, pu_agent_response_time, pu_agent_in_flight, pu_agent_pending
    global pu_agent_batch_handle

    pu_agent_batch_handle = None

    if pu_agent is None or not pu_agent_pending:
        return

    if pu_agent_in_flight:
        return

    batch = pu_agent_pending
    pu_agent_pending = []

    pu_agent_in_flight = True
    try:
        response = await asyncio.to_thread(pu_agent.process_messages, batch)
        # Skip bare "Copy" acknowledgments
        if response and not _is_copy_ack(response):
            pu_agent_response = response
            pu_agent_response_time = _format_session_time(prev_pu_session_time)
            _queue_race_engineer([f"From Power Unit Engineer: {response}"])
    except Exception as exc:
        print(f"PowerUnitAgent error: {exc}")
    finally:
        pu_agent_in_flight = False

    if pu_agent_pending:
        await _flush_pu_agent()


def _queue_race_engineer(messages: list[str]) -> None:
    """Add engineer reports to the pending list and (re)start the batch timer."""
    global re_agent_batch_handle

    re_agent_pending.extend(messages)

    # Log incoming messages so they appear in the Race Engineer panel
    ts = _format_session_time(session_time)
    for msg in messages:
        re_alerts_log.append({"level": "info", "message": msg, "time": ts})

    if re_agent_batch_handle is not None:
        re_agent_batch_handle.cancel()

    loop = asyncio.get_running_loop()
    re_agent_batch_handle = loop.call_later(
        RE_AGENT_BATCH_DELAY,
        lambda: asyncio.ensure_future(_flush_race_engineer()),
    )


def _route_race_engineer_response(response: str) -> None:
    """Parse the race engineer's response and route follow-up questions to specialists.

    Handles multi-line messages per target: lines without a known prefix are
    appended to the most recently matched target. This way the race engineer
    can send multi-line messages to a single specialist or address multiple
    specialists in one response.
    """
    route_targets = {
        "To Damage Engineer:": (_queue_damage_alerts, aero_alerts_log),
        "To Tyres Engineer:": (_queue_tyres_alerts, tyre_alerts_log),
        "To Power Unit Engineer:": (_queue_pu_alerts, pu_alerts_log),
    }
    ts = _format_session_time(session_time)

    # Accumulate (target_key, lines) blocks so multi-line messages stay together
    current_target: str | None = None
    accumulated_lines: list[str] = []
    blocks: list[tuple[str, str]] = []  # (target_key, full_message)

    def _flush_block() -> None:
        if current_target and accumulated_lines:
            blocks.append((current_target, " ".join(accumulated_lines)))

    for line in response.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        matched = False
        for prefix in route_targets:
            if line.startswith(prefix):
                _flush_block()
                current_target = prefix
                accumulated_lines = []
                remainder = line[len(prefix):].strip()
                if remainder:
                    accumulated_lines.append(remainder)
                matched = True
                break
        if not matched and current_target:
            # Continuation line for the current target
            accumulated_lines.append(line)

    _flush_block()

    # Dispatch each block to the appropriate specialist
    for target_key, msg in blocks:
        queue_fn, alerts_log = route_targets[target_key]
        prefixed = f"From Race Engineer: {msg}"
        queue_fn([prefixed])
        alerts_log.append({"level": "info", "message": prefixed, "time": ts})


def _split_race_engineer_response(response: str) -> list[str]:
    """Split a race engineer response into individual messages per target.

    Each block starts with a known prefix (e.g. "To Fernando:", "To Damage Engineer:").
    Continuation lines (no prefix) are appended to the current block.
    Text without any prefix is kept as a standalone block.
    """
    prefixes = ("To Fernando:", "To Damage Engineer:", "To Tyres Engineer:", "To Power Unit Engineer:")
    blocks: list[str] = []
    current_lines: list[str] = []

    for line in response.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        if any(line.startswith(p) for p in prefixes):
            if current_lines:
                blocks.append(" ".join(current_lines))
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        blocks.append(" ".join(current_lines))

    return blocks


async def _flush_race_engineer() -> None:
    """Drain the pending list and send the batch to the RaceEngineerAgent."""
    global re_agent_in_flight, re_agent_pending
    global re_agent_batch_handle

    re_agent_batch_handle = None

    if re_agent is None or not re_agent_pending:
        return

    if re_agent_in_flight:
        return

    batch = re_agent_pending
    re_agent_pending = []

    re_agent_in_flight = True
    response = None
    try:
        response = await asyncio.to_thread(re_agent.process_messages, batch)
        # Don't send bare "Copy" acknowledgments to the frontend
        if response and not _is_copy_ack(response):
            ts = _format_session_time(session_time)
            for msg in _split_race_engineer_response(response):
                re_responses_log.append({"text": msg, "time": ts})
    except Exception as exc:
        print(f"RaceEngineerAgent error: {exc}")
    finally:
        re_agent_in_flight = False

    # Route follow-up questions back to specialist agents
    if response:
        _route_race_engineer_response(response)

    if re_agent_pending:
        await _flush_race_engineer()


def build_message() -> tuple[str, list[dict], list[dict], list[dict]]:
    """Build a JSON message from the latest merged state."""

    # -- Aero alerts (must run before we build the aero dict) --
    # We build the aero snapshot first so _process_aero_alerts can read it,
    # then include it in the final payload.
    aero_snapshot = {
        "sessionTime": session_time,
        "frontLeftWingDamage": damage_state.get("front_left_wing_damage", 0),
        "frontRightWingDamage": damage_state.get("front_right_wing_damage", 0),
        "rearWingDamage": damage_state.get("rear_wing_damage", 0),
        "floorDamage": damage_state.get("floor_damage", 0),
        "diffuserDamage": damage_state.get("diffuser_damage", 0),
        "sidepodDamage": damage_state.get("sidepod_damage", 0),
        "drsFault": bool(damage_state.get("drs_fault", 0)),
        "brakeTempFL": telemetry_state.get("brake_temp_fl", 0),
        "brakeTempFR": telemetry_state.get("brake_temp_fr", 0),
        "brakeTempRL": telemetry_state.get("brake_temp_rl", 0),
        "brakeTempRR": telemetry_state.get("brake_temp_rr", 0),
    }
    new_aero_alerts = _process_aero_alerts(aero_snapshot)

    tyres = {}
    for wn in WHEEL_NAMES:
        tyres[wn] = {
            "surfaceTemp": telemetry_state.get(f"tyre_surface_temp_{wn}", 0),
            "innerTemp": telemetry_state.get(f"tyre_inner_temp_{wn}", 0),
            "pressure": telemetry_state.get(f"tyre_pressure_{wn}", 0),
            "wear": damage_state.get(f"tyre_wear_{wn}", 0),
            "damage": damage_state.get(f"tyre_damage_{wn}", 0),
            "blisters": damage_state.get(f"tyre_blisters_{wn}", 0),
            "brakeTemp": telemetry_state.get(f"brake_temp_{wn}", 0),
        }

    # -- Tyre alerts --
    new_tyre_alerts = _process_tyre_alerts({
        "sessionTime": session_time,
        "tyres": tyres,
        "compound": status_state.get("tyre_compound_actual", ""),
        "compoundVisual": status_state.get("tyre_compound_visual", ""),
    })

    # -- Power Unit --
    ERS_MAX_ENERGY_J = 4_000_000  # 4 MJ per F1 regulations
    ers_store = status_state.get("ers_store_energy", 0)
    battery_pct = round((ers_store / ERS_MAX_ENERGY_J) * 100, 1) if ERS_MAX_ENERGY_J else 0

    FUEL_MIX_LABELS = {0: "LEAN", 1: "STANDARD", 2: "RICH", 3: "MAX"}
    ERS_MODE_LABELS = {0: "NONE", 1: "MEDIUM", 2: "HOTLAP", 3: "OVERTAKE"}

    power_unit = {
        "rpm": telemetry_state.get("engine_rpm", 0),
        "engineTemp": telemetry_state.get("engine_temp", 0),
        "gear": telemetry_state.get("gear", 0),
        "fuelInTank": round(status_state.get("fuel_in_tank", 0), 2),
        "fuelRemainingLaps": round(status_state.get("fuel_remaining_laps", 0), 1),
        "fuelMix": FUEL_MIX_LABELS.get(status_state.get("fuel_mix", 1), "STANDARD"),
        "icePowerKW": round(status_state.get("engine_power_ice", 0), 1),
        "mgukPowerKW": round(status_state.get("engine_power_mguk", 0), 1),
        "ersStoreEnergy": round(ers_store, 0),
        "batteryPct": battery_pct,
        "ersDeployMode": ERS_MODE_LABELS.get(
            status_state.get("ers_deploy_mode", 0), "NONE"
        ),
        "ersDeployedThisLap": round(status_state.get("ers_deployed_this_lap", 0), 0),
        "ersHarvestedMGUK": round(status_state.get("ers_harvested_mguk", 0), 0),
        "ersHarvestedMGUH": round(status_state.get("ers_harvested_mguh", 0), 0),
        "engineDamage": damage_state.get("engine_damage", 0),
        "gearboxDamage": damage_state.get("gearbox_damage", 0),
    }

    # -- Power unit alerts --
    new_pu_alerts = _process_pu_alerts({**power_unit, "sessionTime": session_time})

    # -- Aero --
    aero = {
        "speed": telemetry_state.get("speed_kmh", 0),
        "drs": bool(telemetry_state.get("drs", 0)),
        "drsAllowed": bool(status_state.get("drs_allowed", 0)),
        "drsActivationDistance": status_state.get("drs_activation_distance", 0),
        "frontWing": setup_state.get("front_wing", 0),
        "rearWing": setup_state.get("rear_wing", 0),
        "frontRideHeight": motion_ex_state.get("front_aero_height", 0),
        "rearRideHeight": motion_ex_state.get("rear_aero_height", 0),
        "brakeBias": status_state.get("front_brake_bias", 0),
        "frontLeftWingDamage": damage_state.get("front_left_wing_damage", 0),
        "frontRightWingDamage": damage_state.get("front_right_wing_damage", 0),
        "rearWingDamage": damage_state.get("rear_wing_damage", 0),
        "floorDamage": damage_state.get("floor_damage", 0),
        "diffuserDamage": damage_state.get("diffuser_damage", 0),
        "sidepodDamage": damage_state.get("sidepod_damage", 0),
        "drsFault": bool(damage_state.get("drs_fault", 0)),
        "brakeTempFL": telemetry_state.get("brake_temp_fl", 0),
        "brakeTempFR": telemetry_state.get("brake_temp_fr", 0),
        "brakeTempRL": telemetry_state.get("brake_temp_rl", 0),
        "brakeTempRR": telemetry_state.get("brake_temp_rr", 0),
    }

    # -- Session --
    session_type = session_state.get("session_type", 0)
    track_id = session_state.get("track_id", -1)
    last_lap_ms = lap_state.get("last_lap_time_ms", 0)

    # Use 5000 m default for replay (CSV may not have track_length_m)
    track_length_m = session_state.get("track_length_m", 5000) or 5000
    session = {
        "sessionType": SESSION_TYPE_LABELS.get(session_type, f"SESSION {session_type}"),
        "trackName": TRACK_NAMES.get(track_id, f"TRACK {track_id}"),
        "totalLaps": session_state.get("total_laps", 0),
        "trackLengthM": track_length_m,
        "sessionTimeLeft": session_state.get("session_time_left", 0),
        "sessionDuration": session_state.get("session_duration", 0),
        "trackLength": session_state.get("track_length", 0),
        "trackTemp": session_state.get("track_temperature", 0),
        "airTemp": session_state.get("air_temperature", 0),
        "weather": session_state.get("weather", 0),
        "carPosition": lap_state.get("car_position", 0),
        "currentLapTimeMs": lap_state.get("current_lap_time_ms", 0),
        "lastLapTimeMs": last_lap_ms,
    }

    lap_distance_m = lap_state.get("lap_distance_m", 0)
    total_distance_m = lap_state.get("total_distance_m")
    if total_distance_m is None and track_length_m > 0:
        current_lap = lap_state.get("current_lap_num", 1)
        total_distance_m = (current_lap - 1) * track_length_m + lap_distance_m
    total_distance_m = round(total_distance_m, 2) if total_distance_m is not None else lap_distance_m

    # -- Track map: merge motion positions with per-car lap data --
    track_map = None
    if motion_positions:
        track_map_cars = []
        for i in range(len(motion_positions)):
            m = motion_positions[i]
            lap = all_lap_data[i] if i < len(all_lap_data) else {}
            participant = participants[i] if i < len(participants) else {}
            wx = m.get("world_position_x", 0)
            wz = m.get("world_position_z", 0)
            track_map_cars.append({
                "x": wx,
                "z": wz,
                "position": lap.get("position", 0),
                "lapDistance": lap.get("lap_distance", 0),
                "active": (wx != 0 or wz != 0) and lap.get("driver_status", 0) >= 1,
                "abbreviation": participant.get("abbreviation", ""),
                "teamAbbreviation": participant.get("team_abbreviation", ""),
            })
        track_map = {
            "playerIndex": player_car_idx,
            "cars": track_map_cars,
        }

    msg = json.dumps({
        "tyres": tyres,
        "compound": status_state.get("tyre_compound_actual", ""),
        "compoundVisual": status_state.get("tyre_compound_visual", ""),
        "tyresAgeLaps": status_state.get("tyres_age_laps", 0),
        "currentLap": lap_state.get("current_lap_num", 0),
        "lapDistanceM": lap_distance_m,
        "totalDistanceM": total_distance_m,
        "speed": telemetry_state.get("speed_kmh", 0),
        "sessionTime": session_time,
        "powerUnit": power_unit,
        "aero": aero,
        "session": session,
        "trackMap": track_map,
        "tyreAlerts": {
            "alerts": tyre_alerts_log,
            "activeCount": len(tyre_alert_conditions),
        },
        "puAlerts": {
            "alerts": pu_alerts_log,
            "activeCount": len(pu_alert_conditions),
        },
        "aeroAlerts": {
            "alerts": aero_alerts_log,
            "activeCount": len(aero_alert_conditions),
        },
        "damageReport": {
            "response": damage_agent_response,
            "time": damage_agent_response_time,
        },
        "tyresReport": {
            "response": tyres_agent_response,
            "time": tyres_agent_response_time,
        },
        "puReport": {
            "response": pu_agent_response,
            "time": pu_agent_response_time,
        },
        "raceEngineerReport": {
            "responses": re_responses_log,
            "alerts": re_alerts_log,
        },
    })
    return msg, new_aero_alerts, new_tyre_alerts, new_pu_alerts


async def broadcast(message: str):
    """Send a message to every connected WebSocket client."""
    if not connected_clients:
        return
    await asyncio.gather(
        *(client.send(message) for client in connected_clients),
        return_exceptions=True,
    )


async def ws_handler(websocket):
    """Handle a new WebSocket connection."""
    connected_clients.add(websocket)
    print(f"Client connected ({len(connected_clients)} total)")
    try:
        # Send current state immediately so the UI isn't blank
        msg, _new_aero_alerts, _new_tyre_alerts, _new_pu_alerts = build_message()
        await websocket.send(msg)
        # Listen for incoming messages (driver radio)
        async for raw in websocket:
            try:
                incoming = json.loads(raw)
                driver_msg = incoming.get("driverMessage")
                if driver_msg and isinstance(driver_msg, str):
                    _queue_race_engineer([f"From Fernando: {driver_msg}"])
            except (json.JSONDecodeError, AttributeError):
                pass
    finally:
        connected_clients.discard(websocket)
        print(f"Client disconnected ({len(connected_clients)} total)")


async def udp_reader():
    """Read F1 25 UDP packets and update shared state, broadcasting on each
    telemetry frame (packet 6)."""
    global lap_state, status_state, damage_state, telemetry_state, setup_state, motion_ex_state, session_state, session_time
    global prev_session_uid
    global motion_positions, all_lap_data, participants, player_car_idx

    loop = asyncio.get_running_loop()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if hasattr(socket, "SO_REUSEPORT"):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    sock.bind((UDP_IP, UDP_PORT))
    sock.setblocking(False)

    print(f"Listening for F1 25 UDP on {UDP_IP}:{UDP_PORT}")

    parser = F1TelemetryParser()

    while True:
        try:
            data = await loop.sock_recv(sock, 4096)
        except BlockingIOError:
            await asyncio.sleep(0.001)
            continue

        packet_id = parser.parse_packet(data)
        if packet_id is None:
            continue

        # Copy parser state into globals for non-telemetry packets
        if packet_id != PACKET_ID_CAR_TELEMETRY:
            session_state = parser.session_state
            lap_state = parser.lap_state
            status_state = parser.status_state
            damage_state = parser.damage_state
            setup_state = parser.setup_state
            motion_ex_state = parser.motion_ex_state
            motion_positions = parser.motion_data
            all_lap_data = parser.all_cars_lap_data
            participants = parser.participants_data
            player_car_idx = parser.player_car_index

            # Detect new session and re-instantiate agents with session context
            if packet_id == PACKET_ID_SESSION and parser.session_uid != prev_session_uid:
                prev_session_uid = parser.session_uid
                context = _build_session_context()
                print(f"New session detected — re-initializing agents\n{context}")
                await asyncio.to_thread(_reinit_agents, context)

            continue

        # -- Car Telemetry (main trigger) --
        telemetry_state = parser.telemetry_state
        session_time = parser.session_time

        # Broadcast merged state to all WS clients
        msg, new_aero_alerts, new_tyre_alerts, new_pu_alerts = build_message()
        await broadcast(msg)

        # Dispatch new aero alerts to DamageAgent
        if new_aero_alerts:
            alert_texts = [
                f"ALERT {a['level'].upper()} {a['message']} {a['time']}"
                for a in new_aero_alerts
            ]
            _queue_damage_alerts(alert_texts)

        # Dispatch new tyre alerts to TyresAgent
        if new_tyre_alerts:
            alert_texts = [
                f"ALERT {a['level'].upper()} {a['message']} {a['time']}"
                for a in new_tyre_alerts
            ]
            _queue_tyres_alerts(alert_texts)

        # Dispatch new PU alerts to PowerUnitAgent
        if new_pu_alerts:
            alert_texts = [
                f"ALERT {a['level'].upper()} {a['message']} {a['time']}"
                for a in new_pu_alerts
            ]
            _queue_pu_alerts(alert_texts)

        # Write CSV row if capture is enabled
        if csv_capture is not None:
            csv_capture.write_row(parser.session_uid, session_time, 0)


# ---------------------------------------------------------------------------
# CSV replay
# ---------------------------------------------------------------------------
REVERSE_SESSION_TYPE = {v: k for k, v in SESSION_TYPE_LABELS.items()}
REVERSE_TRACK = {v: k for k, v in TRACK_NAMES.items()}


def _float(val, default=0.0):
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _int(val, default=0):
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def _populate_state_from_row(row: dict):
    """Fill the shared state dicts from a single CSV row."""
    global lap_state, status_state, damage_state, telemetry_state
    global setup_state, motion_ex_state, session_state, session_time
    global motion_positions, all_lap_data, participants, player_car_idx

    session_time = _float(row.get("session_time"))

    player_car_idx = _int(row.get("player_car_index"))

    session_state = {
        "session_type": REVERSE_SESSION_TYPE.get(row.get("session_type", ""), 0),
        "track_id": REVERSE_TRACK.get(row.get("track_name", ""), -1),
        "session_time_left": _int(row.get("session_time_left")),
        "track_length": _int(row.get("track_length")),
        "total_laps": 0,
        "session_duration": 0,
        "track_temperature": 0,
        "air_temperature": 0,
        "weather": 0,
    }

    lap_state = {
        "current_lap_num": _int(row.get("current_lap_num")),
        "lap_distance_m": _float(row.get("lap_distance_m")),
        "car_position": _int(row.get("car_position")),
        "last_lap_time_ms": _int(row.get("last_lap_time_ms")),
        "current_lap_time_ms": _int(row.get("current_lap_time_ms")),
    }

    status_state = {
        "tyre_compound_actual": row.get("tyre_compound_actual", ""),
        "tyre_compound_visual": row.get("tyre_compound_visual", ""),
        "tyres_age_laps": _int(row.get("tyres_age_laps")),
        "fuel_in_tank": _float(row.get("fuel_in_tank")),
        "fuel_remaining_laps": _float(row.get("fuel_remaining_laps")),
        "fuel_mix": _int(row.get("fuel_mix")),
        "engine_power_ice": _float(row.get("engine_power_ice_w")),
        "engine_power_mguk": _float(row.get("engine_power_mguk_w")),
        "ers_store_energy": _float(row.get("ers_store_energy_j")),
        "ers_deploy_mode": _int(row.get("ers_deploy_mode")),
        "ers_harvested_mguk": _float(row.get("ers_harvested_mguk_j")),
        "ers_harvested_mguh": _float(row.get("ers_harvested_mguh_j")),
        "ers_deployed_this_lap": _float(row.get("ers_deployed_this_lap_j")),
        "front_brake_bias": _int(row.get("brake_bias")),
        "drs_allowed": 0,
        "drs_activation_distance": 0,
    }

    new_damage = {}
    for wn in WHEEL_NAMES:
        new_damage[f"tyre_wear_{wn}"] = _float(row.get(f"tyre_wear_{wn}"))
        new_damage[f"tyre_damage_{wn}"] = _int(row.get(f"tyre_damage_{wn}"))
        new_damage[f"tyre_blisters_{wn}"] = _int(row.get(f"tyre_blisters_{wn}"))
    new_damage["engine_damage"] = _int(row.get("engine_damage"))
    new_damage["gearbox_damage"] = _int(row.get("gearbox_damage"))
    new_damage["front_left_wing_damage"] = _int(row.get("front_left_wing_damage"))
    new_damage["front_right_wing_damage"] = _int(row.get("front_right_wing_damage"))
    new_damage["rear_wing_damage"] = _int(row.get("rear_wing_damage"))
    new_damage["floor_damage"] = _int(row.get("floor_damage"))
    new_damage["diffuser_damage"] = _int(row.get("diffuser_damage"))
    new_damage["sidepod_damage"] = _int(row.get("sidepod_damage"))
    new_damage["drs_fault"] = _int(row.get("drs_fault"))
    damage_state = new_damage

    telem = {
        "speed_kmh": _int(row.get("speed_kmh")),
        "engine_rpm": _int(row.get("engine_rpm")),
        "engine_temp": _int(row.get("engine_temp")),
        "gear": _int(row.get("gear")),
        "drs": _int(row.get("drs")),
    }
    for wn in WHEEL_NAMES:
        telem[f"brake_temp_{wn}"] = _int(row.get(f"brake_temp_{wn}"))
        telem[f"tyre_surface_temp_{wn}"] = _int(row.get(f"tyre_surface_temp_{wn}"))
        telem[f"tyre_inner_temp_{wn}"] = _int(row.get(f"tyre_inner_temp_{wn}"))
        telem[f"tyre_pressure_{wn}"] = _float(row.get(f"tyre_pressure_{wn}"))
    telemetry_state = telem

    setup_state = {
        "front_wing": _int(row.get("front_wing_setup")),
        "rear_wing": _int(row.get("rear_wing_setup")),
        "brake_bias": _int(row.get("brake_bias")),
    }

    motion_ex_state = {
        "front_aero_height": _float(row.get("front_ride_height_mm")),
        "rear_aero_height": _float(row.get("rear_ride_height_mm")),
    }

    # Reconstruct per-car track map data from CSV (new-format CSVs only)
    new_motion: list[dict] = []
    new_laps: list[dict] = []
    new_parts: list[dict] = []
    for ci in range(NUM_CARS):
        x_val = row.get(f"car{ci}_x", "")
        if x_val == "":
            break  # Old CSV without per-car columns
        new_motion.append({
            "world_position_x": _float(x_val),
            "world_position_z": _float(row.get(f"car{ci}_z")),
        })
        new_laps.append({
            "position": _int(row.get(f"car{ci}_position")),
            "lap_distance": _float(row.get(f"car{ci}_lap_distance")),
            "driver_status": _int(row.get(f"car{ci}_driver_status")),
            "result_status": _int(row.get(f"car{ci}_result_status")),
        })
        new_parts.append({
            "driver_id": _int(row.get(f"car{ci}_driver_id")),
            "team_id": _int(row.get(f"car{ci}_team_id")),
            "abbreviation": row.get(f"car{ci}_abbreviation", ""),
            "team_abbreviation": row.get(f"car{ci}_team_abbreviation", ""),
        })
    if new_motion:
        motion_positions = new_motion
        all_lap_data = new_laps
        participants = new_parts


async def csv_replay(filepath: str, speed: int = 1):
    """Replay a captured CSV file as if it were live telemetry."""
    global prev_session_uid
    path = Path(filepath)
    if not path.exists():
        print(f"ERROR: file not found: {filepath}")
        return

    print(f"Replaying {filepath} ({speed}x) ...")

    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        prev_wall_time = None
        row_count = 0

        for row in reader:
            wall_time = _float(row.get("wall_time"))

            # Pace replay using original timing, scaled by speed
            if prev_wall_time is not None and wall_time > prev_wall_time:
                delta = (wall_time - prev_wall_time) / speed
                # Cap to 1s to skip long pauses (e.g. game paused)
                await asyncio.sleep(min(delta, 1.0))
            prev_wall_time = wall_time

            _populate_state_from_row(row)

            # Detect new session in replay and re-init agents
            row_uid = _int(row.get("session_uid"))
            if row_uid and row_uid != prev_session_uid:
                prev_session_uid = row_uid
                context = _build_session_context()
                print(f"New session detected in replay — re-initializing agents\n{context}")
                await asyncio.to_thread(_reinit_agents, context)

            msg, new_aero_alerts, new_tyre_alerts, new_pu_alerts = build_message()
            await broadcast(msg)

            # Dispatch new aero alerts to DamageAgent
            if new_aero_alerts:
                alert_texts = [
                    f"ALERT {a['level'].upper()} {a['message']} {a['time']}"
                    for a in new_aero_alerts
                ]
                _queue_damage_alerts(alert_texts)

            # Dispatch new tyre alerts to TyresAgent
            if new_tyre_alerts:
                alert_texts = [
                    f"ALERT {a['level'].upper()} {a['message']} {a['time']}"
                    for a in new_tyre_alerts
                ]
                _queue_tyres_alerts(alert_texts)

            # Dispatch new PU alerts to PowerUnitAgent
            if new_pu_alerts:
                alert_texts = [
                    f"ALERT {a['level'].upper()} {a['message']} {a['time']}"
                    for a in new_pu_alerts
                ]
                _queue_pu_alerts(alert_texts)

            row_count += 1

    print(f"Replay complete — {row_count} frames sent.")


async def main():
    global csv_capture, damage_agent, tyres_agent, pu_agent, re_agent

    parser = argparse.ArgumentParser(description="F1 25 telemetry WebSocket bridge")
    parser.add_argument(
        "--capture",
        action="store_true",
        help="Save telemetry to CSV files in the data/ folder (one file per session)",
    )
    parser.add_argument(
        "--replay",
        metavar="FILE",
        help="Replay a captured CSV file instead of listening for live UDP",
    )
    parser.add_argument(
        "--speed",
        metavar="Nx",
        default="1x",
        help="Replay speed multiplier, e.g. 2x, 10x (default: 1x)",
    )
    args = parser.parse_args()

    if args.capture and args.replay:
        parser.error("--capture and --replay cannot be used together")

    if args.speed != "1x" and not args.replay:
        parser.error("--speed can only be used with --replay")

    if args.capture:
        csv_capture = CsvCapture(Path("data"))
        print("CSV capture enabled → data/")

    os.environ.setdefault("AGENT_MANIFEST_FILE", "registries/manifest.hocon")
    try:
        damage_agent = DamageAgent()
        print("DamageAgent initialized")
    except Exception as exc:
        print(f"DamageAgent unavailable: {exc}")

    try:
        tyres_agent = TyresAgent()
        print("TyresAgent initialized")
    except Exception as exc:
        print(f"TyresAgent unavailable: {exc}")

    try:
        pu_agent = PowerUnitAgent()
        print("PowerUnitAgent initialized")
    except Exception as exc:
        print(f"PowerUnitAgent unavailable: {exc}")

    try:
        re_agent = RaceEngineerAgent()
        print("RaceEngineerAgent initialized")
    except Exception as exc:
        print(f"RaceEngineerAgent unavailable: {exc}")

    print(f"Starting WebSocket server on ws://{WS_HOST}:{WS_PORT}")
    try:
        async with websockets.serve(ws_handler, WS_HOST, WS_PORT):
            if args.replay:
                speed_str = args.speed.rstrip("x")
                try:
                    speed = int(speed_str)
                except ValueError:
                    parser.error(f"invalid --speed value: {args.speed} (expected Nx, e.g. 2x, 10x)")
                await csv_replay(args.replay, speed)
            else:
                await udp_reader()
    finally:
        if csv_capture is not None:
            csv_capture.close()


if __name__ == "__main__":
    asyncio.run(main())
