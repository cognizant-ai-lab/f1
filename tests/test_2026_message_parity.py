"""A 2026 Season Pack session produces the same dashboard payload as 2025.

The two formats are built from identical logical values, decoded, and pushed
through the real server + message builder. If 2026 support is wrong (wrong
offsets, wrong car count) the dashboard payload diverges or decoding raises.
"""

import json

from f1_packet_builder import build_packet

from common.f1_decoder.packet_decoder import PacketDecoder
from telemetry_server.telemetry_server import TelemetryServer

PLAYER = 0


def _raw_packets(packet_format: int) -> dict:
    """Build one datagram per packet type for a fixed synthetic race session."""
    header = {"m_packetFormat": packet_format, "m_playerCarIndex": PLAYER, "m_sessionUID": 4242}
    return {
        0: build_packet(
            packet_format,
            0,
            m_packetId=0,
            **header,
            **{
                f"m_carMotionData[{PLAYER}].m_worldPositionX": 123.5,
                f"m_carMotionData[{PLAYER}].m_worldPositionZ": -45.25,
            },
        ),
        1: build_packet(
            packet_format,
            1,
            m_packetId=1,
            **header,
            m_weather=0,
            m_trackTemperature=40,
            m_airTemperature=25,
            m_totalLaps=57,
            m_trackLength=5412,
            m_sessionType=10,
            m_trackId=3,
            m_sessionTimeLeft=1800,
            m_sessionDuration=3600,
        ),
        2: build_packet(
            packet_format,
            2,
            m_packetId=2,
            **header,
            **{
                f"m_lapData[{PLAYER}].m_carPosition": 2,
                f"m_lapData[{PLAYER}].m_currentLapNum": 7,
                f"m_lapData[{PLAYER}].m_currentLapTimeInMS": 91234,
            },
        ),
        4: build_packet(
            packet_format,
            4,
            m_packetId=4,
            **header,
            m_numActiveCars=20,
            **{
                f"m_participants[{PLAYER}].m_driverId": 1,
                f"m_participants[{PLAYER}].m_teamId": 2,
            },
        ),
        6: build_packet(
            packet_format,
            6,
            m_packetId=6,
            **header,
            **{
                f"m_carTelemetryData[{PLAYER}].m_speed": 312,
                f"m_carTelemetryData[{PLAYER}].m_gear": 8,
                f"m_carTelemetryData[{PLAYER}].m_engineRPM": 12000,
                f"m_carTelemetryData[{PLAYER}].m_throttle": 1.0,
                f"m_carTelemetryData[{PLAYER}].m_brake": 0.0,
                f"m_carTelemetryData[{PLAYER}].m_engineTemperature": 110,
                f"m_carTelemetryData[{PLAYER}].m_brakesTemperature": [500, 510, 520, 530],
                f"m_carTelemetryData[{PLAYER}].m_tyresSurfaceTemperature": [90, 91, 92, 93],
            },
        ),
        7: build_packet(
            packet_format,
            7,
            m_packetId=7,
            **header,
            **{
                f"m_carStatusData[{PLAYER}].m_fuelInTank": 42.5,
                f"m_carStatusData[{PLAYER}].m_drsAllowed": 1,
                f"m_carStatusData[{PLAYER}].m_actualTyreCompound": 18,
                f"m_carStatusData[{PLAYER}].m_tyresAgeLaps": 12,
            },
        ),
        10: build_packet(
            packet_format,
            10,
            m_packetId=10,
            **header,
            **{f"m_carDamageData[{PLAYER}].m_frontLeftWingDamage": 15},
        ),
    }


def _dashboard_message(packet_format: int) -> dict:
    """Decode a synthetic session and build the dashboard JSON."""
    decoder = PacketDecoder()
    server = TelemetryServer()
    for packet_id, datagram in _raw_packets(packet_format).items():
        server.store_packet(packet_id, decoder.decode(datagram))
    message, _, _, _ = server.message_builder.build()
    return json.loads(message)


def test_2026_session_matches_2025_dashboard_payload():
    """Identical telemetry yields identical dashboard values in both formats."""
    baseline = _dashboard_message(2025)
    season_2026 = _dashboard_message(2026)

    for key in ("sessionTime", "currentLap", "lapDistance"):
        assert season_2026[key] == baseline[key], key

    assert baseline["aero"]["speed"] == 312
    assert season_2026["aero"]["speed"] == 312
    assert season_2026["aero"] == baseline["aero"]
    assert season_2026["session"]["trackName"] == baseline["session"]["trackName"]


def test_2026_engine_temperature_reaches_the_dashboard():
    """The narrowed uint8 engine temperature still reaches the payload."""
    payload = _dashboard_message(2026)

    assert payload["powerUnit"]["engineTemp"] == 110
    assert payload["powerUnit"]["engineTemp"] == _dashboard_message(2025)["powerUnit"]["engineTemp"]
