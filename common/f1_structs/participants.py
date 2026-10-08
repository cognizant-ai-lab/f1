"""
F1 25 UDP Telemetry — Participants Packet (1284 bytes).

Source: F1 25 Telemetry Output Structures (c) 2025 Electronic Arts Inc.
"""

# RGB value of a colour
LIVERY_COLOUR = {
    "red": "B",                              # uint8  - Red component
    "green": "B",                            # uint8  - Green component
    "blue": "B",                             # uint8  - Blue component
}

# Data about one participant (57 bytes)
PARTICIPANT_DATA = {
    "m_aiControlled": "B",                   # uint8  - Whether the vehicle is AI (1) or Human (0) controlled
    "m_driverId": "B",                       # uint8  - Driver id - see appendix, 255 if network human
    "m_networkId": "B",                      # uint8  - Network id - unique identifier for network players
    "m_teamId": "B",                         # uint8  - Team id - see appendix
    "m_myTeam": "B",                         # uint8  - My team flag - 1 = My Team, 0 = otherwise
    "m_raceNumber": "B",                     # uint8  - Race number of the car
    "m_nationality": "B",                    # uint8  - Nationality of the driver
    "m_name": "32s",                         # char[32] - Name of participant in UTF-8 format, null terminated
                                             #            Will be truncated with ... (U+2026) if too long
    "m_yourTelemetry": "B",                  # uint8  - The player's UDP setting, 0 = restricted, 1 = public
    "m_showOnlineNames": "B",                # uint8  - The player's show online names setting, 0 = off, 1 = on
    "m_techLevel": "H",                      # uint16 - F1 World tech level
    "m_platform": "B",                       # uint8  - 1 = Steam, 3 = PlayStation, 4 = Xbox, 6 = Origin, 255 = unknown
    "m_numColours": "B",                     # uint8  - Number of colours valid for this car
    "m_liveryColours": "12s",                # LiveryColour[4] - 4 x RGB (3 bytes each = 12 bytes)
}

# Packet-level leading field (after header, before participant array)
PACKET_PARTICIPANTS_HEAD = {
    "m_numActiveCars": "B",                  # uint8  - Number of active cars in the data
}

# PacketParticipantsData: PACKET_HEADER + PACKET_PARTICIPANTS_HEAD + PARTICIPANT_DATA[22]

# ---------------------------------------------------------------------------
# 2026 Season Pack (packet format 2026): 60 bytes per participant, 24 participants.
# m_driverId, m_networkId and m_teamId widen from uint8 to uint16.
# Source: 2026 Season Pack Telemetry Output Structures (c) 2026 Electronic Arts Inc.
# ---------------------------------------------------------------------------

PARTICIPANT_DATA_2026 = {
    **PARTICIPANT_DATA,
    "m_driverId": "H",                       # uint16 - Driver id - see appendix, 65535 if network human
    "m_networkId": "H",                      # uint16 - Network id - unique identifier for network players
    "m_teamId": "H",                         # uint16 - Team id - see appendix
}

# PacketParticipantsData: PACKET_HEADER + PACKET_PARTICIPANTS_HEAD + PARTICIPANT_DATA_2026[24]
