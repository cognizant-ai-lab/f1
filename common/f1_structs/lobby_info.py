"""
F1 25 UDP Telemetry — Lobby Info Packet (954 bytes).

Source: F1 25 Telemetry Output Structures (c) 2025 Electronic Arts Inc.
"""

# Data about one lobby participant
LOBBY_INFO_DATA = {
    "m_aiControlled": "B",                   # uint8    - Whether the vehicle is AI (1) or Human (0) controlled
    "m_teamId": "B",                         # uint8    - Team id - see appendix (255 if no team currently selected)
    "m_nationality": "B",                    # uint8    - Nationality of the driver
    "m_platform": "B",                       # uint8    - 1 = Steam, 3 = PlayStation, 4 = Xbox, 6 = Origin, 255 = unknown
    "m_name": "32s",                         # char[32] - Name of participant in UTF-8 format, null terminated
                                             #            Will be truncated with ... (U+2026) if too long
    "m_carNumber": "B",                      # uint8    - Car number of the player
    "m_yourTelemetry": "B",                  # uint8    - The player's UDP setting, 0 = restricted, 1 = public
    "m_showOnlineNames": "B",                # uint8    - The player's show online names setting, 0 = off, 1 = on
    "m_techLevel": "H",                      # uint16   - F1 World tech level
    "m_readyStatus": "B",                    # uint8    - 0 = not ready, 1 = ready, 2 = spectating
}

# Packet-level leading field (after header, before lobby array)
PACKET_LOBBY_INFO_HEAD = {
    "m_numPlayers": "B",                     # uint8    - Number of players in the lobby data
}

# PacketLobbyInfoData: PACKET_HEADER + PACKET_LOBBY_INFO_HEAD + LOBBY_INFO_DATA[22]

# ---------------------------------------------------------------------------
# 2026 Season Pack (packet format 2026): 43 bytes per player, 24 players.
# m_teamId widens from uint8 to uint16.
# Source: 2026 Season Pack Telemetry Output Structures (c) 2026 Electronic Arts Inc.
# ---------------------------------------------------------------------------

LOBBY_INFO_DATA_2026 = {
    **LOBBY_INFO_DATA,
    "m_teamId": "H",                         # uint16   - Team id - see appendix (65535 if no team selected)
}

# PacketLobbyInfoData: PACKET_HEADER + PACKET_LOBBY_INFO_HEAD + LOBBY_INFO_DATA_2026[24]
