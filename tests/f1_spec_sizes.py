"""Packet sizes declared by the official Codemasters/EA UDP specifications.

These are transcribed from the packet tables, independently of the decoder's own
layout definitions, so a layout that drifts from the spec fails a test instead of
silently misreading packets.

  * 2025: F1 25 Telemetry Output Structures.
  * 2026: 2026 Season Pack Telemetry Output Structures (packet format 2026,
    24 cars, packet 16 "Car Telemetry 2" added).
"""

# packet_format -> {packet_id: declared packet size in bytes}
SPEC_PACKET_SIZES: dict[int, dict[int, int]] = {
    2025: {
        0: 1349,   # Motion
        1: 753,    # Session
        2: 1285,   # Lap
        3: 45,     # Event
        4: 1284,   # Participants
        5: 1133,   # Car Setups
        6: 1352,   # Car Telemetry
        7: 1239,   # Car Status
        8: 1042,   # Final Classification
        9: 954,    # Lobby Info
        10: 1041,  # Car Damage
        11: 1460,  # Session History
        12: 231,   # Tyre Sets
        13: 273,   # Motion Ex
        14: 101,   # Time Trial
        15: 1131,  # Lap Positions
    },
    2026: {
        0: 1325,   # Motion (g-forces quantised to int16)
        1: 926,    # Session (aero/DRS zones and assists added)
        2: 1399,   # Lap
        3: 45,     # Event
        4: 1470,   # Participants (16-bit driver/network/team ids)
        5: 1233,   # Car Setups
        6: 1448,   # Car Telemetry
        7: 1445,   # Car Status (per-lap ERS harvest limit added)
        8: 1134,   # Final Classification
        9: 1062,   # Lobby Info (16-bit team id)
        10: 1133,  # Car Damage
        11: 1460,  # Session History
        12: 231,   # Tyre Sets
        13: 273,   # Motion Ex
        14: 104,   # Time Trial (16-bit team id)
        15: 1231,  # Lap Positions
        16: 269,   # Car Telemetry 2
    },
}

MAX_CARS_2025 = 22
MAX_CARS_2026 = 24

# Packet 3 (Event) carries a 16-byte payload that is a union keyed by the event
# code. The decoder intentionally reads only the 4-byte event code, so its
# layout covers a prefix of the datagram rather than all 45 bytes.
UNION_PAYLOAD_PACKETS = frozenset({3})
