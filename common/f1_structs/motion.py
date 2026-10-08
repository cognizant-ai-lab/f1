"""
F1 25 UDP Telemetry — Motion Packet (1349 bytes).

Source: F1 25 Telemetry Output Structures (c) 2025 Electronic Arts Inc.
"""

# Motion data for one car
CAR_MOTION_DATA = {
    "m_worldPositionX": "f",             # float  - World space X position - metres
    "m_worldPositionY": "f",             # float  - World space Y position
    "m_worldPositionZ": "f",             # float  - World space Z position
    "m_worldVelocityX": "f",             # float  - Velocity in world space X - metres/s
    "m_worldVelocityY": "f",             # float  - Velocity in world space Y
    "m_worldVelocityZ": "f",             # float  - Velocity in world space Z
    "m_worldForwardDirX": "h",           # int16  - World space forward X direction (normalised)
    "m_worldForwardDirY": "h",           # int16  - World space forward Y direction (normalised)
    "m_worldForwardDirZ": "h",           # int16  - World space forward Z direction (normalised)
    "m_worldRightDirX": "h",             # int16  - World space right X direction (normalised)
    "m_worldRightDirY": "h",             # int16  - World space right Y direction (normalised)
    "m_worldRightDirZ": "h",             # int16  - World space right Z direction (normalised)
    "m_gForceLateral": "f",              # float  - Lateral G-Force component
    "m_gForceLongitudinal": "f",         # float  - Longitudinal G-Force component
    "m_gForceVertical": "f",             # float  - Vertical G-Force component
    "m_yaw": "f",                        # float  - Yaw angle in radians
    "m_pitch": "f",                      # float  - Pitch angle in radians
    "m_roll": "f",                       # float  - Roll angle in radians
}

# PacketMotionData: PACKET_HEADER + CAR_MOTION_DATA[22]

# ---------------------------------------------------------------------------
# 2026 Season Pack (packet format 2026): 54 bytes per car, 24 cars.
# The g-force components are quantised int16, read as value / 1000.0.
# Source: 2026 Season Pack Telemetry Output Structures (c) 2026 Electronic Arts Inc.
# ---------------------------------------------------------------------------

CAR_MOTION_DATA_2026 = {
    "m_worldPositionX": "f",             # float  - World space X position - metres
    "m_worldPositionY": "f",             # float  - World space Y position
    "m_worldPositionZ": "f",             # float  - World space Z position
    "m_worldVelocityX": "f",             # float  - Velocity in world space X - metres/s
    "m_worldVelocityY": "f",             # float  - Velocity in world space Y
    "m_worldVelocityZ": "f",             # float  - Velocity in world space Z
    "m_worldForwardDirX": "h",           # int16  - World space forward X direction (normalised)
    "m_worldForwardDirY": "h",           # int16  - World space forward Y direction (normalised)
    "m_worldForwardDirZ": "h",           # int16  - World space forward Z direction (normalised)
    "m_worldRightDirX": "h",             # int16  - World space right X direction (normalised)
    "m_worldRightDirY": "h",             # int16  - World space right Y direction (normalised)
    "m_worldRightDirZ": "h",             # int16  - World space right Z direction (normalised)
    "m_gForceLateral": "h",              # int16  - Lateral G-Force component (divide by 1000.0)
    "m_gForceLongitudinal": "h",         # int16  - Longitudinal G-Force component (divide by 1000.0)
    "m_gForceVertical": "h",             # int16  - Vertical G-Force component (divide by 1000.0)
    "m_yaw": "f",                        # float  - Yaw angle in radians
    "m_pitch": "f",                      # float  - Pitch angle in radians
    "m_roll": "f",                       # float  - Roll angle in radians
}

# PacketMotionData: PACKET_HEADER + CAR_MOTION_DATA_2026[24]
