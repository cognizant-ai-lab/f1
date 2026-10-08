"""
Packet layout registry — describes the wire-format structure of each F1 25 UDP packet.

Each packet is a list of Segments processed in order. A Segment references an f1_structs
field dict, a repeat count, and whether it produces a nested array or merges into the
parent dict.

Source: F1 25 Telemetry Output Structures (c) 2025 Electronic Arts Inc.
"""

from dataclasses import dataclass

from common.f1_structs.car_damage import CAR_DAMAGE_DATA
from common.f1_structs.car_setups import CAR_SETUP_DATA
from common.f1_structs.car_setups import PACKET_CAR_SETUP_TAIL
from common.f1_structs.car_status import CAR_STATUS_DATA
from common.f1_structs.car_status import CAR_STATUS_DATA_2026
from common.f1_structs.car_telemetry import CAR_TELEMETRY_DATA
from common.f1_structs.car_telemetry import CAR_TELEMETRY_DATA_2026
from common.f1_structs.car_telemetry import PACKET_CAR_TELEMETRY_TAIL
from common.f1_structs.car_telemetry2 import CAR_TELEMETRY2_DATA
from common.f1_structs.event import PACKET_EVENT_CODE
from common.f1_structs.final_classification import FINAL_CLASSIFICATION_DATA
from common.f1_structs.final_classification import PACKET_FINAL_CLASSIFICATION_HEAD
from common.f1_structs.header import PACKET_HEADER
from common.f1_structs.lap import LAP_DATA
from common.f1_structs.lap import PACKET_LAP_DATA_TAIL
from common.f1_structs.lap_positions import PACKET_LAP_POSITIONS_DATA
from common.f1_structs.lap_positions import PACKET_LAP_POSITIONS_DATA_2026
from common.f1_structs.lobby_info import LOBBY_INFO_DATA
from common.f1_structs.lobby_info import LOBBY_INFO_DATA_2026
from common.f1_structs.lobby_info import PACKET_LOBBY_INFO_HEAD
from common.f1_structs.motion import CAR_MOTION_DATA
from common.f1_structs.motion import CAR_MOTION_DATA_2026
from common.f1_structs.motion_ex import PACKET_MOTION_EX_DATA
from common.f1_structs.participants import PACKET_PARTICIPANTS_HEAD
from common.f1_structs.participants import PARTICIPANT_DATA
from common.f1_structs.participants import PARTICIPANT_DATA_2026
from common.f1_structs.session import ACTIVE_AERO_ZONE
from common.f1_structs.session import DRS_ZONE
from common.f1_structs.session import MARSHAL_ZONE
from common.f1_structs.session import SESSION_2026_AERO_FULL_HEAD
from common.f1_structs.session import SESSION_2026_AERO_PARTIAL_HEAD
from common.f1_structs.session import SESSION_2026_DRS_HEAD
from common.f1_structs.session import SESSION_2026_POST_ZONES
from common.f1_structs.session import SESSION_FIELDS_MID
from common.f1_structs.session import SESSION_FIELDS_POST
from common.f1_structs.session import SESSION_FIELDS_PRE_MARSHAL
from common.f1_structs.session import WEATHER_FORECAST_SAMPLE
from common.f1_structs.session_history import LAP_HISTORY_DATA
from common.f1_structs.session_history import PACKET_SESSION_HISTORY_HEAD
from common.f1_structs.session_history import TYRE_STINT_HISTORY_DATA
from common.f1_structs.time_trial import TIME_TRIAL_DATA_SET
from common.f1_structs.time_trial import TIME_TRIAL_DATA_SET_2026
from common.f1_structs.tyre_sets import PACKET_TYRE_SETS_HEAD
from common.f1_structs.tyre_sets import PACKET_TYRE_SETS_TAIL
from common.f1_structs.tyre_sets import TYRE_SET_DATA


@dataclass(frozen=True)
class Segment:
    """One contiguous section in a packet's wire format.

    Attributes:
        name: Key name in the decoded result dict.
        fields: An f1_structs field dictionary.
        count: How many times this struct repeats (1 = scalar, >1 = array).
        merge: If True, scalar fields merge into the parent dict instead of nesting.
               Only meaningful when count == 1.
    """

    name: str
    fields: dict[str, str]
    count: int = 1
    merge: bool = False


# ---------------------------------------------------------------------------
# Packet layouts — ordered list of Segments per packet ID
# ---------------------------------------------------------------------------

PACKET_LAYOUTS: dict[int, list[Segment]] = {

    # 0 — Motion (1349 bytes)
    0: [
        Segment("header", PACKET_HEADER, merge=True),
        Segment("m_carMotionData", CAR_MOTION_DATA, count=22),
    ],

    # 1 — Session (753 bytes)
    1: [
        Segment("header", PACKET_HEADER, merge=True),
        Segment("session", SESSION_FIELDS_PRE_MARSHAL, merge=True),
        Segment("m_marshalZones", MARSHAL_ZONE, count=21),
        Segment("session_mid", SESSION_FIELDS_MID, merge=True),
        Segment("m_weatherForecastSamples", WEATHER_FORECAST_SAMPLE, count=64),
        Segment("session_post", SESSION_FIELDS_POST, merge=True),
    ],

    # 2 — Lap Data (1285 bytes)
    2: [
        Segment("header", PACKET_HEADER, merge=True),
        Segment("m_lapData", LAP_DATA, count=22),
        Segment("tail", PACKET_LAP_DATA_TAIL, merge=True),
    ],

    # 3 — Event (45 bytes)
    # Note: Event details are a union — only the event code is decoded here.
    # The caller should interpret the remaining bytes based on the event code.
    3: [
        Segment("header", PACKET_HEADER, merge=True),
        Segment("event", PACKET_EVENT_CODE, merge=True),
    ],

    # 4 — Participants (1284 bytes)
    4: [
        Segment("header", PACKET_HEADER, merge=True),
        Segment("head", PACKET_PARTICIPANTS_HEAD, merge=True),
        Segment("m_participants", PARTICIPANT_DATA, count=22),
    ],

    # 5 — Car Setups (1133 bytes)
    5: [
        Segment("header", PACKET_HEADER, merge=True),
        Segment("m_carSetupData", CAR_SETUP_DATA, count=22),
        Segment("tail", PACKET_CAR_SETUP_TAIL, merge=True),
    ],

    # 6 — Car Telemetry (1352 bytes)
    6: [
        Segment("header", PACKET_HEADER, merge=True),
        Segment("m_carTelemetryData", CAR_TELEMETRY_DATA, count=22),
        Segment("tail", PACKET_CAR_TELEMETRY_TAIL, merge=True),
    ],

    # 7 — Car Status (1239 bytes)
    7: [
        Segment("header", PACKET_HEADER, merge=True),
        Segment("m_carStatusData", CAR_STATUS_DATA, count=22),
    ],

    # 8 — Final Classification (1042 bytes)
    8: [
        Segment("header", PACKET_HEADER, merge=True),
        Segment("head", PACKET_FINAL_CLASSIFICATION_HEAD, merge=True),
        Segment("m_classificationData", FINAL_CLASSIFICATION_DATA, count=22),
    ],

    # 9 — Lobby Info (954 bytes)
    9: [
        Segment("header", PACKET_HEADER, merge=True),
        Segment("head", PACKET_LOBBY_INFO_HEAD, merge=True),
        Segment("m_lobbyPlayers", LOBBY_INFO_DATA, count=22),
    ],

    # 10 — Car Damage (1041 bytes)
    10: [
        Segment("header", PACKET_HEADER, merge=True),
        Segment("m_carDamageData", CAR_DAMAGE_DATA, count=22),
    ],

    # 11 — Session History (1460 bytes)
    11: [
        Segment("header", PACKET_HEADER, merge=True),
        Segment("head", PACKET_SESSION_HISTORY_HEAD, merge=True),
        Segment("m_lapHistoryData", LAP_HISTORY_DATA, count=100),
        Segment("m_tyreStintsHistoryData", TYRE_STINT_HISTORY_DATA, count=8),
    ],

    # 12 — Tyre Sets (231 bytes)
    12: [
        Segment("header", PACKET_HEADER, merge=True),
        Segment("head", PACKET_TYRE_SETS_HEAD, merge=True),
        Segment("m_tyreSetData", TYRE_SET_DATA, count=20),
        Segment("tail", PACKET_TYRE_SETS_TAIL, merge=True),
    ],

    # 13 — Motion Ex (273 bytes)
    13: [
        Segment("header", PACKET_HEADER, merge=True),
        Segment("motion_ex", PACKET_MOTION_EX_DATA, merge=True),
    ],

    # 14 — Time Trial (101 bytes)
    14: [
        Segment("header", PACKET_HEADER, merge=True),
        Segment("m_playerSessionBestDataSet", TIME_TRIAL_DATA_SET),
        Segment("m_personalBestDataSet", TIME_TRIAL_DATA_SET),
        Segment("m_rivalDataSet", TIME_TRIAL_DATA_SET),
    ],

    # 15 — Lap Positions (1131 bytes)
    15: [
        Segment("header", PACKET_HEADER, merge=True),
        Segment("lap_positions", PACKET_LAP_POSITIONS_DATA, merge=True),
    ],
}

# ---------------------------------------------------------------------------
# 2026 Season Pack layouts (packet format 2026)
#
# Differences from the 2025 layouts:
#   * up to 24 cars instead of 22
#   * Motion g-forces are quantised int16
#   * Car Status gains m_ersHarvestLimitPerLap
#   * Car Telemetry narrows m_engineTemperature to uint8
#   * Participants/Lobby Info/Time Trial widen driver and team ids to uint16
#   * Session gains active aero and DRS zone lists plus assist settings
#   * Lap Positions packs 24 car slots per lap
#   * packet 16 (Car Telemetry 2) is new
#
# Source: 2026 Season Pack Telemetry Output Structures (c) 2026 Electronic Arts Inc.
# ---------------------------------------------------------------------------

PACKET_LAYOUTS_2026: dict[int, list[Segment]] = {

    # 0 — Motion (1325 bytes)
    0: [
        Segment("header", PACKET_HEADER, merge=True),
        Segment("m_carMotionData", CAR_MOTION_DATA_2026, count=24),
    ],

    # 1 — Session (926 bytes)
    1: [
        Segment("header", PACKET_HEADER, merge=True),
        Segment("session", SESSION_FIELDS_PRE_MARSHAL, merge=True),
        Segment("m_marshalZones", MARSHAL_ZONE, count=21),
        Segment("session_mid", SESSION_FIELDS_MID, merge=True),
        Segment("m_weatherForecastSamples", WEATHER_FORECAST_SAMPLE, count=64),
        Segment("session_post", SESSION_FIELDS_POST, merge=True),
        Segment("session_2026_aero_full", SESSION_2026_AERO_FULL_HEAD, merge=True),
        Segment("m_activeAeroZonesFull", ACTIVE_AERO_ZONE, count=8),
        Segment("session_2026_aero_partial", SESSION_2026_AERO_PARTIAL_HEAD, merge=True),
        Segment("m_activeAeroZonesPartial", ACTIVE_AERO_ZONE, count=8),
        Segment("session_2026_drs", SESSION_2026_DRS_HEAD, merge=True),
        Segment("m_drsZones", DRS_ZONE, count=4),
        Segment("session_2026_post_zones", SESSION_2026_POST_ZONES, merge=True),
    ],

    # 2 — Lap Data (1399 bytes)
    2: [
        Segment("header", PACKET_HEADER, merge=True),
        Segment("m_lapData", LAP_DATA, count=24),
        Segment("tail", PACKET_LAP_DATA_TAIL, merge=True),
    ],

    # 3 — Event (45 bytes) — event details are a union; only the code is decoded.
    3: [
        Segment("header", PACKET_HEADER, merge=True),
        Segment("event", PACKET_EVENT_CODE, merge=True),
    ],

    # 4 — Participants (1470 bytes)
    4: [
        Segment("header", PACKET_HEADER, merge=True),
        Segment("head", PACKET_PARTICIPANTS_HEAD, merge=True),
        Segment("m_participants", PARTICIPANT_DATA_2026, count=24),
    ],

    # 5 — Car Setups (1233 bytes)
    5: [
        Segment("header", PACKET_HEADER, merge=True),
        Segment("m_carSetupData", CAR_SETUP_DATA, count=24),
        Segment("tail", PACKET_CAR_SETUP_TAIL, merge=True),
    ],

    # 6 — Car Telemetry (1448 bytes)
    6: [
        Segment("header", PACKET_HEADER, merge=True),
        Segment("m_carTelemetryData", CAR_TELEMETRY_DATA_2026, count=24),
        Segment("tail", PACKET_CAR_TELEMETRY_TAIL, merge=True),
    ],

    # 7 — Car Status (1445 bytes)
    7: [
        Segment("header", PACKET_HEADER, merge=True),
        Segment("m_carStatusData", CAR_STATUS_DATA_2026, count=24),
    ],

    # 8 — Final Classification (1134 bytes)
    8: [
        Segment("header", PACKET_HEADER, merge=True),
        Segment("head", PACKET_FINAL_CLASSIFICATION_HEAD, merge=True),
        Segment("m_classificationData", FINAL_CLASSIFICATION_DATA, count=24),
    ],

    # 9 — Lobby Info (1062 bytes)
    9: [
        Segment("header", PACKET_HEADER, merge=True),
        Segment("head", PACKET_LOBBY_INFO_HEAD, merge=True),
        Segment("m_lobbyPlayers", LOBBY_INFO_DATA_2026, count=24),
    ],

    # 10 — Car Damage (1133 bytes)
    10: [
        Segment("header", PACKET_HEADER, merge=True),
        Segment("m_carDamageData", CAR_DAMAGE_DATA, count=24),
    ],

    # 11 — Session History (1460 bytes, unchanged)
    11: [
        Segment("header", PACKET_HEADER, merge=True),
        Segment("head", PACKET_SESSION_HISTORY_HEAD, merge=True),
        Segment("m_lapHistoryData", LAP_HISTORY_DATA, count=100),
        Segment("m_tyreStintsHistoryData", TYRE_STINT_HISTORY_DATA, count=8),
    ],

    # 12 — Tyre Sets (231 bytes, unchanged)
    12: [
        Segment("header", PACKET_HEADER, merge=True),
        Segment("head", PACKET_TYRE_SETS_HEAD, merge=True),
        Segment("m_tyreSetData", TYRE_SET_DATA, count=20),
        Segment("tail", PACKET_TYRE_SETS_TAIL, merge=True),
    ],

    # 13 — Motion Ex (273 bytes, unchanged)
    13: [
        Segment("header", PACKET_HEADER, merge=True),
        Segment("motion_ex", PACKET_MOTION_EX_DATA, merge=True),
    ],

    # 14 — Time Trial (104 bytes)
    14: [
        Segment("header", PACKET_HEADER, merge=True),
        Segment("m_playerSessionBestDataSet", TIME_TRIAL_DATA_SET_2026),
        Segment("m_personalBestDataSet", TIME_TRIAL_DATA_SET_2026),
        Segment("m_rivalDataSet", TIME_TRIAL_DATA_SET_2026),
    ],

    # 15 — Lap Positions (1231 bytes)
    15: [
        Segment("header", PACKET_HEADER, merge=True),
        Segment("lap_positions", PACKET_LAP_POSITIONS_DATA_2026, merge=True),
    ],

    # 16 — Car Telemetry 2 (269 bytes) — new in 2026
    16: [
        Segment("header", PACKET_HEADER, merge=True),
        Segment("m_carTelemetry2Data", CAR_TELEMETRY2_DATA, count=24),
    ],
}

# Packet format field (m_packetFormat) -> layout table. Packets of an unknown
# format are rejected rather than decoded against the wrong byte layout.
PACKET_LAYOUTS_BY_FORMAT: dict[int, dict[int, list[Segment]]] = {
    2025: PACKET_LAYOUTS,
    2026: PACKET_LAYOUTS_2026,
}
