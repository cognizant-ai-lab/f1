"""
F1 25 UDP Telemetry — Car Status Packet (1239 bytes).

Source: F1 25 Telemetry Output Structures (c) 2025 Electronic Arts Inc.
"""

# Car status data for one car
CAR_STATUS_DATA = {
    "m_tractionControl": "B",               # uint8  - Traction control - 0 = off, 1 = medium, 2 = full
    "m_antiLockBrakes": "B",                # uint8  - 0 (off) - 1 (on)
    "m_fuelMix": "B",                       # uint8  - Fuel mix - 0 = lean, 1 = standard, 2 = rich, 3 = max
    "m_frontBrakeBias": "B",                # uint8  - Front brake bias (percentage)
    "m_pitLimiterStatus": "B",              # uint8  - Pit limiter status - 0 = off, 1 = on
    "m_fuelInTank": "f",                    # float  - Current fuel mass
    "m_fuelCapacity": "f",                  # float  - Fuel capacity
    "m_fuelRemainingLaps": "f",             # float  - Fuel remaining in terms of laps (value on MFD)
    "m_maxRPM": "H",                        # uint16 - Cars max RPM, point of rev limiter
    "m_idleRPM": "H",                       # uint16 - Cars idle RPM
    "m_maxGears": "B",                      # uint8  - Maximum number of gears
    "m_drsAllowed": "B",                    # uint8  - 0 = not allowed, 1 = allowed
    "m_drsActivationDistance": "H",         # uint16 - 0 = DRS not available, non-zero = DRS available in [X] metres
    "m_actualTyreCompound": "B",            # uint8  - F1 Modern: 16=C5, 17=C4, 18=C3, 19=C2, 20=C1, 21=C0, 22=C6, 7=inter, 8=wet
                                            #          F1 Classic: 9=dry, 10=wet
                                            #          F2: 11=super soft, 12=soft, 13=medium, 14=hard, 15=wet
    "m_visualTyreCompound": "B",            # uint8  - F1 visual (can differ from actual): 16=soft, 17=medium, 18=hard, 7=inter, 8=wet
                                            #          F1 Classic: same as above
                                            #          F2 '20: 15=wet, 19=super soft, 20=soft, 21=medium, 22=hard
    "m_tyresAgeLaps": "B",                  # uint8  - Age in laps of the current set of tyres
    "m_vehicleFIAFlags": "b",              # int8   - -1 = invalid/unknown, 0 = none, 1 = green, 2 = blue, 3 = yellow
    "m_enginePowerICE": "f",               # float  - Engine power output of ICE (W)
    "m_enginePowerMGUK": "f",              # float  - Engine power output of MGU-K (W)
    "m_ersStoreEnergy": "f",               # float  - ERS energy store in Joules
    "m_ersDeployMode": "B",                # uint8  - ERS deployment mode, 0 = none, 1 = medium, 2 = hotlap, 3 = overtake
    "m_ersHarvestedThisLapMGUK": "f",      # float  - ERS energy harvested this lap by MGU-K
    "m_ersHarvestedThisLapMGUH": "f",      # float  - ERS energy harvested this lap by MGU-H
    "m_ersDeployedThisLap": "f",           # float  - ERS energy deployed this lap
    "m_networkPaused": "B",                # uint8  - Whether the car is paused in a network game
}

# PacketCarStatusData: PACKET_HEADER + CAR_STATUS_DATA[22]

# ---------------------------------------------------------------------------
# 2026 Season Pack (packet format 2026): 59 bytes per car, 24 cars.
# Adds m_ersHarvestLimitPerLap after m_ersDeployMode.
# Source: 2026 Season Pack Telemetry Output Structures (c) 2026 Electronic Arts Inc.
# ---------------------------------------------------------------------------

CAR_STATUS_DATA_2026: dict[str, str] = {}
for _field_name, _field_format in CAR_STATUS_DATA.items():
    CAR_STATUS_DATA_2026[_field_name] = _field_format
    if _field_name == "m_ersDeployMode":
        # Inserted here to match the 2026 wire order.
        CAR_STATUS_DATA_2026["m_ersHarvestLimitPerLap"] = "f"  # ERS energy harvest limit for this lap

# PacketCarStatusData: PACKET_HEADER + CAR_STATUS_DATA_2026[24]
