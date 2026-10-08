"""
F1 25 UDP Telemetry — Car Telemetry Packet (1352 bytes).

Source: F1 25 Telemetry Output Structures (c) 2025 Electronic Arts Inc.
"""

# Telemetry data for one car
CAR_TELEMETRY_DATA = {
    "m_speed": "H",                          # uint16    - Speed of car in kilometres per hour
    "m_throttle": "f",                       # float     - Amount of throttle applied (0.0 to 1.0)
    "m_steer": "f",                          # float     - Steering (-1.0 full lock left to 1.0 full lock right)
    "m_brake": "f",                          # float     - Amount of brake applied (0.0 to 1.0)
    "m_clutch": "B",                         # uint8     - Amount of clutch applied (0 to 100)
    "m_gear": "b",                           # int8      - Gear selected (1-8, N=0, R=-1)
    "m_engineRPM": "H",                      # uint16    - Engine RPM
    "m_drs": "B",                            # uint8     - 0 = off, 1 = on
    "m_revLightsPercent": "B",               # uint8     - Rev lights indicator (percentage)
    "m_revLightsBitValue": "H",              # uint16    - Rev lights (bit 0 = leftmost LED, bit 14 = rightmost LED)
    "m_brakesTemperature": "4H",             # uint16[4] - Brakes temperature (celsius)
    "m_tyresSurfaceTemperature": "4B",       # uint8[4]  - Tyres surface temperature (celsius)
    "m_tyresInnerTemperature": "4B",         # uint8[4]  - Tyres inner temperature (celsius)
    "m_engineTemperature": "H",              # uint16    - Engine temperature (celsius)
    "m_tyresPressure": "4f",                 # float[4]  - Tyre pressure (PSI)
    "m_surfaceType": "4B",                   # uint8[4]  - Driving surface, see appendices
}

# Packet-level trailing fields (after CAR_TELEMETRY_DATA[22])
PACKET_CAR_TELEMETRY_TAIL = {
    "m_mfdPanelIndex": "B",                  # uint8     - Index of MFD panel open - 255 = MFD closed
                                             #             Single player, race: 0 = Car setup, 1 = Pits,
                                             #             2 = Damage, 3 = Engine, 4 = Temperatures
                                             #             May vary depending on game mode
    "m_mfdPanelIndexSecondaryPlayer": "B",   # uint8     - See above
    "m_suggestedGear": "b",                  # int8      - Suggested gear for the player (1-8), 0 if no gear suggested
}

# PacketCarTelemetryData: PACKET_HEADER + CAR_TELEMETRY_DATA[22] + PACKET_CAR_TELEMETRY_TAIL

# ---------------------------------------------------------------------------
# 2026 Season Pack (packet format 2026): 59 bytes per car, 24 cars.
# m_engineTemperature narrows from uint16 to uint8.
# Source: 2026 Season Pack Telemetry Output Structures (c) 2026 Electronic Arts Inc.
# ---------------------------------------------------------------------------

CAR_TELEMETRY_DATA_2026 = {
    **CAR_TELEMETRY_DATA,
    "m_engineTemperature": "B",              # uint8     - Engine temperature (celsius)
}

# PacketCarTelemetryData: PACKET_HEADER + CAR_TELEMETRY_DATA_2026[24] + PACKET_CAR_TELEMETRY_TAIL
