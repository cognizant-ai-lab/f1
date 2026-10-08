"""
F1 25 UDP Telemetry — Time Trial Packet (101 bytes).

Source: F1 25 Telemetry Output Structures (c) 2025 Electronic Arts Inc.
"""

# Time trial data set (one entry)
TIME_TRIAL_DATA_SET = {
    "m_carIdx": "B",                         # uint8  - Index of the car this data relates to
    "m_teamId": "B",                         # uint8  - Team id - see appendix
    "m_lapTimeInMS": "I",                    # uint32 - Lap time in milliseconds
    "m_sector1TimeInMS": "I",                # uint32 - Sector 1 time in milliseconds
    "m_sector2TimeInMS": "I",                # uint32 - Sector 2 time in milliseconds
    "m_sector3TimeInMS": "I",                # uint32 - Sector 3 time in milliseconds
    "m_tractionControl": "B",               # uint8  - 0 = assist off, 1 = assist on
    "m_gearboxAssist": "B",                 # uint8  - 0 = assist off, 1 = assist on
    "m_antiLockBrakes": "B",                # uint8  - 0 = assist off, 1 = assist on
    "m_equalCarPerformance": "B",           # uint8  - 0 = Realistic, 1 = Equal
    "m_customSetup": "B",                   # uint8  - 0 = No, 1 = Yes
    "m_valid": "B",                         # uint8  - 0 = invalid, 1 = valid
}

# PacketTimeTrialData: PACKET_HEADER
#                      + TIME_TRIAL_DATA_SET (m_playerSessionBestDataSet)
#                      + TIME_TRIAL_DATA_SET (m_personalBestDataSet)
#                      + TIME_TRIAL_DATA_SET (m_rivalDataSet)

# ---------------------------------------------------------------------------
# 2026 Season Pack (packet format 2026): m_teamId widens from uint8 to uint16.
# Source: 2026 Season Pack Telemetry Output Structures (c) 2026 Electronic Arts Inc.
# ---------------------------------------------------------------------------

TIME_TRIAL_DATA_SET_2026 = {
    **TIME_TRIAL_DATA_SET,
    "m_teamId": "H",                         # uint16 - Team id - see appendix
}
