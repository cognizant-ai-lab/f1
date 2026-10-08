"""
F1 25 UDP Telemetry — Lap Positions Packet (1131 bytes).

Packet to send UDP data about the lap positions in a session.
It details the positions of all the drivers at the start of each lap.

Source: F1 25 Telemetry Output Structures (c) 2025 Electronic Arts Inc.
"""

# Packet-level fields (after header)
PACKET_LAP_POSITIONS_DATA = {
    "m_numLaps": "B",                        # uint8        - Number of laps in the data
    "m_lapStart": "B",                       # uint8        - Index of the lap where the data starts, 0 indexed
    "m_positionForVehicleIdx": "1100B",      # uint8[50][22] - Position of each car per lap, 0 if no record
                                             #                 Outer: cs_maxNumLapsInLapPositionsHistoryPacket (50)
                                             #                 Inner: cs_maxNumCarsInUDPData (22)
}

# PacketLapPositionsData: PACKET_HEADER + PACKET_LAP_POSITIONS_DATA

# ---------------------------------------------------------------------------
# 2026 Season Pack (packet format 2026): 24 car slots per lap instead of 22
# (50 laps x 24 cars = 1200 bytes).
# Source: 2026 Season Pack Telemetry Output Structures (c) 2026 Electronic Arts Inc.
# ---------------------------------------------------------------------------

PACKET_LAP_POSITIONS_DATA_2026 = {
    **PACKET_LAP_POSITIONS_DATA,
    "m_positionForVehicleIdx": "1200B",      # uint8[50][24] - Position of each car per lap, 0 if no record
}
