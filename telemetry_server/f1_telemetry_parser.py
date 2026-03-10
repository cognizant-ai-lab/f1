"""Shared F1 25 UDP packet parser.

Provides constants, struct definitions, and the ``F1TelemetryParser`` class
used by both ``tyre_logger`` and ``telemetry_server``.
"""

import struct

# ---------------------------------------------------------------------------
# Packet IDs (F1 25 spec)
# ---------------------------------------------------------------------------
PACKET_ID_SESSION = 1
PACKET_ID_LAP_DATA = 2
PACKET_ID_CAR_SETUPS = 5
PACKET_ID_CAR_TELEMETRY = 6
PACKET_ID_CAR_STATUS = 7
PACKET_ID_CAR_DAMAGE = 10
PACKET_ID_MOTION_EX = 13

# ---------------------------------------------------------------------------
# Struct definitions (packed, little-endian)
# ---------------------------------------------------------------------------

# PacketHeader
HEADER_STRUCT = struct.Struct("<HBBBBBQfIIBB")
HEADER_SIZE = HEADER_STRUCT.size  # pylint: disable=invalid-name  # 29 bytes

NUM_CARS = 22

# Wheel order in all arrays: 0=RL, 1=RR, 2=FL, 3=FR
WHEEL_NAMES = ("rl", "rr", "fl", "fr")

# SessionData – first 13 bytes of the packet body (before marshal zones)
SESSION_HEADER_STRUCT = struct.Struct(
    "<"
    "B"  # m_weather
    "b"  # m_trackTemperature
    "b"  # m_airTemperature
    "B"  # m_totalLaps
    "H"  # m_trackLength
    "B"  # m_sessionType
    "b"  # m_trackId
    "B"  # m_formula
    "H"  # m_sessionTimeLeft
    "H"  # m_sessionDuration
)
SESSION_HEADER_SIZE = SESSION_HEADER_STRUCT.size  # pylint: disable=invalid-name  # 13

# LapData struct (57 bytes)
LAPDATA_STRUCT = struct.Struct(
    "<"
    "I"  # m_lastLapTimeInMS
    "I"  # m_currentLapTimeInMS
    "H"  # m_sector1TimeMSPart
    "B"  # m_sector1TimeMinutesPart
    "H"  # m_sector2TimeMSPart
    "B"  # m_sector2TimeMinutesPart
    "H"  # m_deltaToCarInFrontMSPart
    "B"  # m_deltaToCarInFrontMinutesPart
    "H"  # m_deltaToRaceLeaderMSPart
    "B"  # m_deltaToRaceLeaderMinutesPart
    "f"  # m_lapDistance
    "f"  # m_totalDistance
    "f"  # m_safetyCarDelta
    "B"  # m_carPosition
    "B"  # m_currentLapNum
    "B"  # m_pitStatus
    "B"  # m_numPitStops
    "B"  # m_sector
    "B"  # m_currentLapInvalid
    "B"  # m_penalties
    "B"  # m_totalWarnings
    "B"  # m_cornerCuttingWarnings
    "B"  # m_numUnservedDriveThroughPens
    "B"  # m_numUnservedStopGoPens
    "B"  # m_gridPosition
    "B"  # m_driverStatus
    "B"  # m_resultStatus
    "B"  # m_pitLaneTimerActive
    "H"  # m_pitLaneTimeInLaneInMS
    "H"  # m_pitStopTimerInMS
    "B"  # m_pitStopShouldServePen
    "f"  # m_speedTrapFastestSpeed
    "B"  # m_speedTrapFastestLap
)
LAPDATA_SIZE = LAPDATA_STRUCT.size  # pylint: disable=invalid-name  # 57

# CarTelemetryData struct (60 bytes)
CAR_TELEMETRY_STRUCT = struct.Struct(
    "<"
    "H"  # m_speed
    "f"  # m_throttle
    "f"  # m_steer
    "f"  # m_brake
    "B"  # m_clutch
    "b"  # m_gear
    "H"  # m_engineRPM
    "B"  # m_drs
    "B"  # m_revLightsPercent
    "H"  # m_revLightsBitValue
    "4H"  # m_brakesTemperature[4]
    "4B"  # m_tyresSurfaceTemperature[4]
    "4B"  # m_tyresInnerTemperature[4]
    "H"  # m_engineTemperature
    "4f"  # m_tyresPressure[4]
    "4B"  # m_surfaceType[4]
)
CAR_TELEMETRY_SIZE = CAR_TELEMETRY_STRUCT.size  # pylint: disable=invalid-name  # 60

# CarStatusData struct (55 bytes)
CAR_STATUS_STRUCT = struct.Struct(
    "<"
    "B"  # m_tractionControl
    "B"  # m_antiLockBrakes
    "B"  # m_fuelMix
    "B"  # m_frontBrakeBias
    "B"  # m_pitLimiterStatus
    "f"  # m_fuelInTank
    "f"  # m_fuelCapacity
    "f"  # m_fuelRemainingLaps
    "H"  # m_maxRPM
    "H"  # m_idleRPM
    "B"  # m_maxGears
    "B"  # m_drsAllowed
    "H"  # m_drsActivationDistance
    "B"  # m_actualTyreCompound
    "B"  # m_visualTyreCompound
    "B"  # m_tyresAgeLaps
    "b"  # m_vehicleFiaFlags
    "f"  # m_enginePowerICE
    "f"  # m_enginePowerMGUK
    "f"  # m_ersStoreEnergy
    "B"  # m_ersDeployMode
    "f"  # m_ersHarvestedThisLapMGUK
    "f"  # m_ersHarvestedThisLapMGUH
    "f"  # m_ersDeployedThisLap
    "B"  # m_networkPaused
)
CAR_STATUS_SIZE = CAR_STATUS_STRUCT.size  # pylint: disable=invalid-name  # 55

# CarDamageData struct (46 bytes)
CAR_DAMAGE_STRUCT = struct.Struct(
    "<"
    "4f"  # m_tyresWear[4]
    "4B"  # m_tyresDamage[4]
    "4B"  # m_brakesDamage[4]
    "4B"  # m_tyreBlisters[4]
    "B"  # m_frontLeftWingDamage
    "B"  # m_frontRightWingDamage
    "B"  # m_rearWingDamage
    "B"  # m_floorDamage
    "B"  # m_diffuserDamage
    "B"  # m_sidepodDamage
    "B"  # m_drsFault
    "B"  # m_ersFault
    "B"  # m_gearBoxDamage
    "B"  # m_engineDamage
    "B"  # m_engineMGUHWear
    "B"  # m_engineESWear
    "B"  # m_engineCEWear
    "B"  # m_engineICEWear
    "B"  # m_engineMGUKWear
    "B"  # m_engineTCWear
    "B"  # m_engineBlown
    "B"  # m_engineSeized
)
CAR_DAMAGE_SIZE = CAR_DAMAGE_STRUCT.size  # pylint: disable=invalid-name  # 46

# CarSetupData struct (50 bytes)
CAR_SETUP_STRUCT = struct.Struct(
    "<"
    "B"  # m_frontWing
    "B"  # m_rearWing
    "B"  # m_onThrottle
    "B"  # m_offThrottle
    "f"  # m_frontCamber
    "f"  # m_rearCamber
    "f"  # m_frontToe
    "f"  # m_rearToe
    "B"  # m_frontSuspension
    "B"  # m_rearSuspension
    "B"  # m_frontAntiRollBar
    "B"  # m_rearAntiRollBar
    "B"  # m_frontSuspensionHeight
    "B"  # m_rearSuspensionHeight
    "B"  # m_brakePressure
    "B"  # m_brakeBias
    "B"  # m_engineBraking
    "f"  # m_rearLeftTyrePressure
    "f"  # m_rearRightTyrePressure
    "f"  # m_frontLeftTyrePressure
    "f"  # m_frontRightTyrePressure
    "B"  # m_ballast
    "f"  # m_fuelLoad
)
CAR_SETUP_SIZE = CAR_SETUP_STRUCT.size  # pylint: disable=invalid-name  # 50

# PacketMotionExData (player only, 244 bytes after header)
MOTION_EX_STRUCT = struct.Struct(
    "<"
    "4f"  # m_suspensionPosition[4]
    "4f"  # m_suspensionVelocity[4]
    "4f"  # m_suspensionAcceleration[4]
    "4f"  # m_wheelSpeed[4]
    "4f"  # m_wheelSlipRatio[4]
    "4f"  # m_wheelSlipAngle[4]
    "4f"  # m_wheelLatForce[4]
    "4f"  # m_wheelLongForce[4]
    "f"  # m_heightOfCOGAboveGround
    "f"  # m_localVelocityX
    "f"  # m_localVelocityY
    "f"  # m_localVelocityZ
    "f"  # m_angularVelocityX
    "f"  # m_angularVelocityY
    "f"  # m_angularVelocityZ
    "f"  # m_angularAccelerationX
    "f"  # m_angularAccelerationY
    "f"  # m_angularAccelerationZ
    "f"  # m_frontWheelsAngle
    "4f"  # m_wheelVertForce[4]
    "f"  # m_frontAeroHeight
    "f"  # m_rearAeroHeight
    "f"  # m_frontRollAngle
    "f"  # m_rearRollAngle
    "f"  # m_chassisYaw
    "f"  # m_chassisPitch
    "4f"  # m_wheelCamber[4]
    "4f"  # m_wheelCamberGain[4]
)
MOTION_EX_SIZE = MOTION_EX_STRUCT.size  # pylint: disable=invalid-name  # 244

# ---------------------------------------------------------------------------
# Tyre compound lookups
# ---------------------------------------------------------------------------
ACTUAL_COMPOUND = {
    16: "C5",
    17: "C4",
    18: "C3",
    19: "C2",
    20: "C1",
    21: "C0",
    22: "C6",
    7: "inter",
    8: "wet",
    9: "dry_classic",
    10: "wet_classic",
    11: "super_soft_f2",
    12: "soft_f2",
    13: "medium_f2",
    14: "hard_f2",
    15: "wet_f2",
}

VISUAL_COMPOUND = {
    16: "soft",
    17: "medium",
    18: "hard",
    7: "inter",
    8: "wet",
    19: "super_soft_f2",
    20: "soft_f2",
    21: "medium_f2",
    22: "hard_f2",
    15: "wet_f2",
}


# ---------------------------------------------------------------------------
# Parser class
# ---------------------------------------------------------------------------
class F1TelemetryParser:  # pylint: disable=too-many-instance-attributes,too-few-public-methods
    """Parses raw F1 25 UDP packets and accumulates state into dicts."""

    def __init__(self) -> None:
        """Initialise empty state containers for each packet type."""
        self.session_state: dict = {}
        self.lap_state: dict = {}
        self.status_state: dict = {}
        self.damage_state: dict = {}
        self.telemetry_state: dict = {}
        self.setup_state: dict = {}
        self.motion_ex_state: dict = {}
        self.session_time: float = 0.0
        self.session_uid: int = 0

    def parse_packet(self, data: bytes) -> int | None:  # pylint: disable=too-many-return-statements
        """Parse a raw UDP packet and update internal state.

        Returns the ``PACKET_ID_*`` on success, or ``None`` if the packet
        was too small or contained an unrecognised type.
        """
        if len(data) < HEADER_SIZE:
            return None

        header = HEADER_STRUCT.unpack_from(data, 0)
        packet_id = header[5]
        player_car_index = header[10]
        self.session_uid = header[6]

        if packet_id == PACKET_ID_SESSION:
            return self._parse_session(data)
        if packet_id == PACKET_ID_LAP_DATA:
            return self._parse_lap_data(data, player_car_index)
        if packet_id == PACKET_ID_CAR_STATUS:
            return self._parse_car_status(data, player_car_index)
        if packet_id == PACKET_ID_CAR_DAMAGE:
            return self._parse_car_damage(data, player_car_index)
        if packet_id == PACKET_ID_CAR_TELEMETRY:
            return self._parse_car_telemetry(data, player_car_index, header)
        if packet_id == PACKET_ID_CAR_SETUPS:
            return self._parse_car_setups(data, player_car_index)
        if packet_id == PACKET_ID_MOTION_EX:
            return self._parse_motion_ex(data)

        return None

    # -- private parse helpers ------------------------------------------------

    def _parse_session(self, data: bytes) -> int | None:
        """Parse a Session packet and update ``session_state``."""
        if len(data) < HEADER_SIZE + SESSION_HEADER_SIZE:
            return None
        fields = SESSION_HEADER_STRUCT.unpack_from(data, HEADER_SIZE)
        self.session_state = {
            "session_type": fields[5],
            "track_id": fields[6],
            "total_laps": fields[3],
            "track_length_m": int(fields[4]),
            "session_time_left": fields[8],
            "session_duration": fields[9],
            "track_temperature": fields[1],
            "air_temperature": fields[2],
            "weather": fields[0],
        }
        return PACKET_ID_SESSION

    def _parse_lap_data(self, data: bytes, idx: int) -> int | None:
        """Parse a LapData packet and update ``lap_state``."""
        base = HEADER_SIZE + idx * LAPDATA_SIZE
        if len(data) < base + LAPDATA_SIZE:
            return None
        fields = LAPDATA_STRUCT.unpack_from(data, base)
        self.lap_state = {
            "current_lap_num": fields[14],
            "lap_distance_m": round(fields[10], 2),
            "total_distance_m": round(fields[11], 2),
            "car_position": fields[13],
            "last_lap_time_ms": fields[0],
            "current_lap_time_ms": fields[1],
        }
        return PACKET_ID_LAP_DATA

    def _parse_car_status(self, data: bytes, idx: int) -> int | None:
        """Parse a CarStatus packet and update ``status_state``."""
        base = HEADER_SIZE + idx * CAR_STATUS_SIZE
        if len(data) < base + CAR_STATUS_SIZE:
            return None
        fields = CAR_STATUS_STRUCT.unpack_from(data, base)
        actual = fields[13]
        visual = fields[14]
        self.status_state = {
            "tyre_compound_actual": ACTUAL_COMPOUND.get(actual, str(actual)),
            "tyre_compound_visual": VISUAL_COMPOUND.get(visual, str(visual)),
            "tyres_age_laps": fields[15],
            "fuel_in_tank": fields[5],
            "fuel_remaining_laps": fields[7],
            "fuel_mix": fields[2],
            "engine_power_ice": fields[17],
            "engine_power_mguk": fields[18],
            "ers_store_energy": fields[19],
            "ers_deploy_mode": fields[20],
            "ers_harvested_mguk": fields[21],
            "ers_harvested_mguh": fields[22],
            "ers_deployed_this_lap": fields[23],
            "front_brake_bias": fields[3],
            "drs_allowed": fields[11],
            "drs_activation_distance": fields[12],
        }
        return PACKET_ID_CAR_STATUS

    def _parse_car_damage(self, data: bytes, idx: int) -> int | None:
        """Parse a CarDamage packet and update ``damage_state``."""
        base = HEADER_SIZE + idx * CAR_DAMAGE_SIZE
        if len(data) < base + CAR_DAMAGE_SIZE:
            return None
        fields = CAR_DAMAGE_STRUCT.unpack_from(data, base)
        dmg: dict = {}
        for i, wn in enumerate(WHEEL_NAMES):
            dmg[f"tyre_wear_{wn}"] = round(fields[0 + i], 2)
            dmg[f"tyre_damage_{wn}"] = fields[4 + i]
            dmg[f"tyre_blisters_{wn}"] = fields[12 + i]
        dmg["engine_damage"] = fields[25]
        dmg["gearbox_damage"] = fields[24]
        dmg["front_left_wing_damage"] = fields[16]
        dmg["front_right_wing_damage"] = fields[17]
        dmg["rear_wing_damage"] = fields[18]
        dmg["floor_damage"] = fields[19]
        dmg["diffuser_damage"] = fields[20]
        dmg["sidepod_damage"] = fields[21]
        dmg["drs_fault"] = fields[22]
        self.damage_state = dmg
        return PACKET_ID_CAR_DAMAGE

    def _parse_car_telemetry(self, data: bytes, idx: int, header: tuple) -> int | None:
        """Parse a CarTelemetry packet and update ``telemetry_state``."""
        base = HEADER_SIZE + idx * CAR_TELEMETRY_SIZE
        if len(data) < base + CAR_TELEMETRY_SIZE:
            return None
        fields = CAR_TELEMETRY_STRUCT.unpack_from(data, base)
        telem: dict = {
            "speed_kmh": fields[0],
            "throttle": round(fields[1], 3),
            "brake": round(fields[3], 3),
            "engine_rpm": fields[6],
            "engine_temp": fields[22],
            "gear": fields[5],
            "drs": fields[7],
        }
        for i, wn in enumerate(WHEEL_NAMES):
            telem[f"brake_temp_{wn}"] = fields[10 + i]
            telem[f"tyre_surface_temp_{wn}"] = fields[14 + i]
            telem[f"tyre_inner_temp_{wn}"] = fields[18 + i]
            telem[f"tyre_pressure_{wn}"] = round(fields[23 + i], 2)
        self.telemetry_state = telem
        self.session_time = header[7]  # m_sessionTime (float)
        return PACKET_ID_CAR_TELEMETRY

    def _parse_car_setups(self, data: bytes, idx: int) -> int | None:
        """Parse a CarSetups packet and update ``setup_state``."""
        base = HEADER_SIZE + idx * CAR_SETUP_SIZE
        if len(data) < base + CAR_SETUP_SIZE:
            return None
        fields = CAR_SETUP_STRUCT.unpack_from(data, base)
        self.setup_state = {
            "front_wing": fields[0],
            "rear_wing": fields[1],
            "front_suspension_height": fields[12],
            "rear_suspension_height": fields[13],
            "brake_bias": fields[15],
        }
        return PACKET_ID_CAR_SETUPS

    def _parse_motion_ex(self, data: bytes) -> int | None:
        """Parse a MotionEx packet and update ``motion_ex_state``."""
        if len(data) < HEADER_SIZE + MOTION_EX_SIZE:
            return None
        fields = MOTION_EX_STRUCT.unpack_from(data, HEADER_SIZE)
        self.motion_ex_state = {
            "front_aero_height": round(fields[47] * 1000, 1),  # m -> mm
            "rear_aero_height": round(fields[48] * 1000, 1),
            "front_roll_angle": round(fields[49], 4),
            "rear_roll_angle": round(fields[50], 4),
        }
        return PACKET_ID_MOTION_EX
