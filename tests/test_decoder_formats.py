"""Format-specific decoding: 2026 Season Pack alongside base F1 25."""

import pytest
from f1_packet_builder import build_packet
from f1_spec_sizes import MAX_CARS_2025
from f1_spec_sizes import MAX_CARS_2026

from common.f1_decoder.packet_decoder import PacketDecoder


def test_2026_motion_decodes_all_24_cars():
    """2026 Motion carries 24 cars and quantised int16 g-forces."""
    packet = build_packet(
        2026,
        0,
        m_packetFormat=2026,
        m_packetId=0,
        **{"m_carMotionData[23].m_gForceLateral": 1500},
    )

    decoded = PacketDecoder().decode(packet)

    assert len(decoded["m_carMotionData"]) == MAX_CARS_2026
    assert decoded["m_carMotionData"][23]["m_gForceLateral"] == 1500


def test_2025_motion_still_decodes_22_cars():
    """The base 2025 layout is unchanged."""
    packet = build_packet(2025, 0, m_packetFormat=2025, m_packetId=0)
    decoded = PacketDecoder().decode(packet)

    assert len(decoded["m_carMotionData"]) == MAX_CARS_2025


def test_2026_car_status_decodes_per_lap_ers_harvest_limit():
    """2026 adds m_ersHarvestLimitPerLap to CarStatusData."""
    packet = build_packet(
        2026,
        7,
        m_packetFormat=2026,
        m_packetId=7,
        **{"m_carStatusData[5].m_ersHarvestLimitPerLap": 4000000.0},
    )

    decoded = PacketDecoder().decode(packet)

    assert len(decoded["m_carStatusData"]) == MAX_CARS_2026
    assert decoded["m_carStatusData"][5]["m_ersHarvestLimitPerLap"] == 4000000.0


def test_2026_car_telemetry_engine_temperature_is_uint8():
    """2026 narrows m_engineTemperature to a single byte."""
    packet = build_packet(
        2026,
        6,
        m_packetFormat=2026,
        m_packetId=6,
        **{"m_carTelemetryData[2].m_engineTemperature": 220},
    )

    decoded = PacketDecoder().decode(packet)

    assert decoded["m_carTelemetryData"][2]["m_engineTemperature"] == 220


def test_2026_participant_ids_are_uint16():
    """2026 widens driver, network and team ids to 16 bits."""
    packet = build_packet(
        2026,
        4,
        m_packetFormat=2026,
        m_packetId=4,
        **{"m_participants[1].m_driverId": 65535, "m_participants[1].m_teamId": 4000},
    )

    decoded = PacketDecoder().decode(packet)

    assert decoded["m_participants"][1]["m_driverId"] == 65535
    assert decoded["m_participants"][1]["m_teamId"] == 4000


def test_2026_session_decodes_new_tail_fields():
    """2026 appends aero/DRS zones and assist settings to the session packet."""
    packet = build_packet(
        2026,
        1,
        m_packetFormat=2026,
        m_packetId=1,
        **{
            "m_numActiveAeroZonesFull": 2,
            "m_activeAeroZonesFull[1].m_zoneEnd": 0.75,
            "m_startReactionTime": 0.21,
            "m_tractionControlAssist": 2,
        },
    )

    decoded = PacketDecoder().decode(packet)

    assert decoded["m_numActiveAeroZonesFull"] == 2
    assert decoded["m_activeAeroZonesFull"][1]["m_zoneEnd"] == pytest.approx(0.75)
    assert decoded["m_startReactionTime"] == pytest.approx(0.21)
    assert decoded["m_tractionControlAssist"] == 2


def test_2026_car_telemetry2_packet_decodes():
    """Packet 16 (Car Telemetry 2) is new in 2026 and must decode."""
    packet = build_packet(
        2026,
        16,
        m_packetFormat=2026,
        m_packetId=16,
        **{
            "m_carTelemetry2Data[0].m_activeAeroMode": 1,
            "m_carTelemetry2Data[0].m_overtakeAvailable": 1,
            "m_carTelemetry2Data[23].m_2026Regulations": 1,
        },
    )

    decoded = PacketDecoder().decode(packet)

    assert len(decoded["m_carTelemetry2Data"]) == MAX_CARS_2026
    assert decoded["m_carTelemetry2Data"][0]["m_activeAeroMode"] == 1
    assert decoded["m_carTelemetry2Data"][0]["m_overtakeAvailable"] == 1
    assert decoded["m_carTelemetry2Data"][23]["m_2026Regulations"] == 1


def test_2026_lap_positions_widened_to_24_cars():
    """Lap Positions packs 24 car slots per lap in 2026."""
    packet = build_packet(
        2026,
        15,
        m_packetFormat=2026,
        m_packetId=15,
    )

    decoded = PacketDecoder().decode(packet)

    # 50 laps x 24 cars, versus 50 x 22 in 2025.
    assert len(decoded["m_positionForVehicleIdx"]) == 50 * MAX_CARS_2026
