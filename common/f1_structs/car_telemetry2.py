"""
2026 Season Pack UDP Telemetry — Car Telemetry 2 Packet (269 bytes, packet 16).

New in the 2026 Season Pack: per-car active-aero and overtake state.

Source: 2026 Season Pack Telemetry Output Structures (c) 2026 Electronic Arts Inc.
"""

# Telemetry 2 data for one car (10 bytes)
CAR_TELEMETRY2_DATA = {
    "m_activeAeroMode": "B",                 # uint8  - 0 = Corner mode, 1 = Straight mode
    "m_activeAeroAvailable": "B",            # uint8  - 0 = not available, 1 = available
    "m_activeAeroActivationDistance": "H",   # uint16 - 0 = Active aero not available, else distance in metres
    "m_overtakeAvailable": "B",              # uint8  - 0 = not available, 1 = available
    "m_overtakeActive": "B",                 # uint8  - 0 = not active, 1 = active
    "m_overtakeActivationDistance": "H",     # uint16 - 0 = Overtake Mode not available, else distance in metres
    "m_2026Regulations": "B",                # uint8  - 0 = pre-2026 vehicle, 1 = 2026 regulations apply
    "m_drivingWrongWay": "B",                # uint8  - Whether the car is driving the wrong way
}

# PacketCarTelemetry2Data: PACKET_HEADER + CAR_TELEMETRY2_DATA[24]
