"""Translates PacketDecoder state dicts into the flat data structures
expected by the telemetry server's WebSocket JSON messages and alert system.

Reads from ``state: dict[int, dict]`` (keyed by packet ID) produced by
``PacketDecoder`` / ``CaptureSession`` / ``ReplaySession`` and provides
methods that return the same camelCase / flat dicts that ``build_message()``
previously assembled from the old ``F1TelemetryParser`` globals.
"""

from common.f1_structs.f1_constants import ACTUAL_TYRE_COMPOUND
from common.f1_structs.f1_constants import DRIVER_ABBREVIATIONS
from common.f1_structs.f1_constants import TEAM_ABBREVIATIONS
from common.f1_structs.f1_constants import VISUAL_TYRE_COMPOUND

# Wheel array order in all f1_structs arrays: 0=RL, 1=RR, 2=FL, 3=FR
WHEEL_INDICES = {"rl": 0, "rr": 1, "fl": 2, "fr": 3}
WHEEL_NAMES = ("rl", "rr", "fl", "fr")

# Presentation-layer lookups
SESSION_TYPE_LABELS: dict[int, str] = {
    0: "UNKNOWN", 1: "FP1", 2: "FP2", 3: "FP3", 4: "SHORT FP",
    5: "Q1", 6: "Q2", 7: "Q3", 8: "SHORT QUALIFYING", 9: "OSQ",
    10: "RACE", 11: "RACE 2", 12: "RACE 3", 13: "TIME TRIAL",
    14: "SQ1", 15: "RACE SHORT", 16: "SQ3", 17: "SPRINT",
}

TRACK_NAMES_SHORT: dict[int, str] = {
    0: "AUSTRALIAN GP", 2: "CHINESE GP", 3: "BAHRAIN GP",
    4: "SPANISH GP", 5: "MONACO GP", 6: "CANADIAN GP", 7: "BRITISH GP",
    9: "HUNGARIAN GP", 10: "BELGIAN GP", 11: "ITALIAN GP",
    12: "SINGAPORE GP", 13: "JAPANESE GP", 14: "ABU DHABI GP", 15: "UNITED STATES GP",
    16: "BRAZILIAN GP", 17: "AUSTRIAN GP", 19: "MEXICAN GP",
    20: "AZERBAIJAN GP", 26: "DUTCH GP",
    27: "EMILIA ROMAGNA GP", 29: "SAUDI ARABIAN GP", 30: "MIAMI GP",
    31: "LAS VEGAS GP", 32: "QATAR GP",
}

WEATHER_LABELS: dict[int, str] = {
    0: "Clear", 1: "Light Cloud", 2: "Overcast",
    3: "Light Rain", 4: "Heavy Rain", 5: "Storm",
}

FUEL_MIX_LABELS: dict[int, str] = {0: "LEAN", 1: "STANDARD", 2: "RICH", 3: "MAX"}
ERS_MODE_LABELS: dict[int, str] = {0: "NONE", 1: "MEDIUM", 2: "HOTLAP", 3: "OVERTAKE"}

ERS_MAX_ENERGY_J = 4_000_000  # 4 MJ per F1 regulations
WATTS_PER_KILOWATT = 1000.0


class TelemetryStateAdapter:
    """Reads PacketDecoder state and produces flat dicts for the WebSocket layer."""

    def __init__(self, state: dict[int, dict]) -> None:
        """Initialize with a reference to the shared PacketDecoder state dict.

        Args:
            state: Dict keyed by packet ID, values are decoded packet dicts.
        """
        self._state = state

    # -- Header fields (available in every packet via merged header) ----------

    def _header_field(self, key: str, default=None):
        """Read a header field from whichever packet is available."""
        for pkt_id in (6, 1, 2, 7, 0, 10, 5, 13, 4):
            pkt = self._state.get(pkt_id)
            if pkt and key in pkt:
                return pkt[key]
        return default

    @property
    def player_car_index(self) -> int:
        """Player car index from the packet header."""
        return self._header_field("m_playerCarIndex", 0)

    @property
    def session_uid(self) -> int:
        """Session UID from the packet header."""
        return self._header_field("m_sessionUID", 0)

    @property
    def session_time(self) -> float:
        """Session time in seconds from the packet header."""
        return self._header_field("m_sessionTime", 0.0)

    # -- Per-car data helpers -------------------------------------------------

    def _player_car(self, packet_id: int, array_key: str) -> dict:
        """Get the player's car data from an arrayed packet."""
        pkt = self._state.get(packet_id)
        if not pkt:
            return {}
        cars = pkt.get(array_key, [])
        idx = self.player_car_index
        return cars[idx] if idx < len(cars) else {}

    # -- Tyres ----------------------------------------------------------------

    def get_tyres(self) -> dict:
        """Build the per-wheel tyre data dict for the WebSocket message."""
        t = self._player_car(6, "m_carTelemetryData")
        d = self._player_car(10, "m_carDamageData")

        surf = t.get("m_tyresSurfaceTemperature", [0] * 4)
        inner = t.get("m_tyresInnerTemperature", [0] * 4)
        press = t.get("m_tyresPressure", [0.0] * 4)
        brake = t.get("m_brakesTemperature", [0] * 4)
        wear = d.get("m_tyresWear", [0.0] * 4)
        damage = d.get("m_tyresDamage", [0] * 4)
        blisters = d.get("m_tyreBlisters", [0] * 4)

        tyres = {}
        for wn, i in WHEEL_INDICES.items():
            tyres[wn] = {
                "surfaceTemp": surf[i],
                "innerTemp": inner[i],
                "pressure": round(press[i], 2),
                "wear": round(wear[i], 2),
                "damage": damage[i],
                "blisters": blisters[i],
                "brakeTemp": brake[i],
            }
        return tyres

    def get_compound(self) -> tuple[str, str]:
        """Return (actual_compound, visual_compound) as human-readable strings."""
        s = self._player_car(7, "m_carStatusData")
        actual_id = s.get("m_actualTyreCompound", 0)
        visual_id = s.get("m_visualTyreCompound", 0)
        return (
            ACTUAL_TYRE_COMPOUND.get(actual_id, str(actual_id)),
            VISUAL_TYRE_COMPOUND.get(visual_id, str(visual_id)),
        )

    def get_tyres_age_laps(self) -> int:
        """Return the age of the current tyre set in laps."""
        s = self._player_car(7, "m_carStatusData")
        return s.get("m_tyresAgeLaps", 0)

    # -- Tyre Sets ------------------------------------------------------------

    def get_tyre_sets(self) -> dict:
        """Build the tyre sets data dict from packet 12.

        Returns available tyre sets with compound info, wear, lifespan,
        and which set is currently fitted.
        """
        pkt = self._state.get(12, {})
        if not pkt:
            return {"sets": [], "fittedIdx": 0}

        raw_sets = pkt.get("m_tyreSetData", [])
        fitted_idx = pkt.get("m_fittedIdx", 0)

        sets = []
        for idx, ts in enumerate(raw_sets):
            if not ts.get("m_actualTyreCompound", 0):
                continue
            if not ts.get("m_available", 0):
                continue
            sets.append({
                "index": idx,
                "actualCompound": ACTUAL_TYRE_COMPOUND.get(ts.get("m_actualTyreCompound", 0), "?"),
                "visualCompound": VISUAL_TYRE_COMPOUND.get(ts.get("m_visualTyreCompound", 0), "?"),
                "wear": ts.get("m_wear", 0),
                "available": bool(ts.get("m_available", 0)),
                "lifeSpan": ts.get("m_lifeSpan", 0),
                "usableLife": ts.get("m_usableLife", 0),
                "lapDeltaTime": ts.get("m_lapDeltaTime", 0),
                "fitted": bool(ts.get("m_fitted", 0)),
            })
        return {"sets": sets, "fittedIdx": fitted_idx}

    # -- Power Unit -----------------------------------------------------------

    def get_power_unit(self) -> dict:
        """Build the power unit data dict for the WebSocket message."""
        t = self._player_car(6, "m_carTelemetryData")
        s = self._player_car(7, "m_carStatusData")
        d = self._player_car(10, "m_carDamageData")

        ers_store = s.get("m_ersStoreEnergy", 0)
        battery_pct = round((ers_store / ERS_MAX_ENERGY_J) * 100, 1) if ERS_MAX_ENERGY_J else 0

        return {
            "rpm": t.get("m_engineRPM", 0),
            "engineTemp": t.get("m_engineTemperature", 0),
            "gear": t.get("m_gear", 0),
            "fuelInTank": round(s.get("m_fuelInTank", 0), 2),
            "fuelRemainingLaps": round(s.get("m_fuelRemainingLaps", 0), 1),
            "fuelMix": FUEL_MIX_LABELS.get(s.get("m_fuelMix", 1), "STANDARD"),
            # The game reports engine power in watts; the dashboard gauge wants kilowatts.
            "icePowerKW": round(s.get("m_enginePowerICE", 0) / WATTS_PER_KILOWATT, 1),
            "mgukPowerKW": round(s.get("m_enginePowerMGUK", 0) / WATTS_PER_KILOWATT, 1),
            "ersStoreEnergy": round(ers_store, 0),
            "batteryPct": battery_pct,
            "ersDeployMode": ERS_MODE_LABELS.get(s.get("m_ersDeployMode", 0), "NONE"),
            "ersDeployedThisLap": round(s.get("m_ersDeployedThisLap", 0), 0),
            "ersHarvestedMGUK": round(s.get("m_ersHarvestedThisLapMGUK", 0), 0),
            "ersHarvestedMGUH": round(s.get("m_ersHarvestedThisLapMGUH", 0), 0),
            "engineDamage": d.get("m_engineDamage", 0),
            "gearboxDamage": d.get("m_gearBoxDamage", 0),
            # New fields from common/
            "engineMGUHWear": d.get("m_engineMGUHWear", 0),
            "engineESWear": d.get("m_engineESWear", 0),
            "engineCEWear": d.get("m_engineCEWear", 0),
            "engineICEWear": d.get("m_engineICEWear", 0),
            "engineMGUKWear": d.get("m_engineMGUKWear", 0),
            "engineTCWear": d.get("m_engineTCWear", 0),
            "engineBlown": bool(d.get("m_engineBlown", 0)),
            "engineSeized": bool(d.get("m_engineSeized", 0)),
        }

    # -- Aero -----------------------------------------------------------------

    def get_aero(self) -> dict:
        """Build the aero data dict for the WebSocket message."""
        t = self._player_car(6, "m_carTelemetryData")
        s = self._player_car(7, "m_carStatusData")
        d = self._player_car(10, "m_carDamageData")
        su = self._player_car(5, "m_carSetupData")
        mx = self._state.get(13, {})

        brake_temps = t.get("m_brakesTemperature", [0] * 4)

        return {
            "speed": t.get("m_speed", 0),
            "drs": bool(t.get("m_drs", 0)),
            "drsAllowed": bool(s.get("m_drsAllowed", 0)),
            "drsActivationDistance": s.get("m_drsActivationDistance", 0),
            "frontWing": su.get("m_frontWing", 0),
            "rearWing": su.get("m_rearWing", 0),
            "frontRideHeight": round(mx.get("m_frontAeroHeight", 0) * 1000, 1),
            "rearRideHeight": round(mx.get("m_rearAeroHeight", 0) * 1000, 1),
            "brakeBias": s.get("m_frontBrakeBias", 0),
            "frontLeftWingDamage": d.get("m_frontLeftWingDamage", 0),
            "frontRightWingDamage": d.get("m_frontRightWingDamage", 0),
            "rearWingDamage": d.get("m_rearWingDamage", 0),
            "floorDamage": d.get("m_floorDamage", 0),
            "diffuserDamage": d.get("m_diffuserDamage", 0),
            "sidepodDamage": d.get("m_sidepodDamage", 0),
            "drsFault": bool(d.get("m_drsFault", 0)),
            "ersFault": bool(d.get("m_ersFault", 0)),
            "brakeTempFL": brake_temps[2],
            "brakeTempFR": brake_temps[3],
            "brakeTempRL": brake_temps[0],
            "brakeTempRR": brake_temps[1],
        }

    # -- Session --------------------------------------------------------------

    def get_session(self) -> dict:
        """Build the session data dict for the WebSocket message."""
        sess = self._state.get(1, {})
        lap = self._player_car(2, "m_lapData")

        session_type = sess.get("m_sessionType", 0)
        track_id = sess.get("m_trackId", -1)

        return {
            "sessionType": SESSION_TYPE_LABELS.get(session_type, f"SESSION {session_type}"),
            "trackId": track_id,
            "trackName": TRACK_NAMES_SHORT.get(track_id, f"TRACK {track_id}"),
            "totalLaps": sess.get("m_totalLaps", 0),
            "sessionTimeLeft": sess.get("m_sessionTimeLeft", 0),
            "sessionDuration": sess.get("m_sessionDuration", 0),
            "trackLength": sess.get("m_trackLength", 0),
            "trackTemp": sess.get("m_trackTemperature", 0),
            "airTemp": sess.get("m_airTemperature", 0),
            "weather": sess.get("m_weather", 0),
            "carPosition": lap.get("m_carPosition", 0),
            "currentLapTimeMs": lap.get("m_currentLapTimeInMS", 0),
            "lastLapTimeMs": lap.get("m_lastLapTimeInMS", 0),
        }

    # -- Weather forecast ------------------------------------------------------

    def get_weather_forecast(self) -> list[dict]:
        """Return filtered weather forecast samples for the current session type.

        Filters to the current session type and excludes offset=0 entries,
        matching the logic in terminal_viewer.py.
        """
        sess = self._state.get(1, {})
        n_samples = sess.get("m_numWeatherForecastSamples", 0)
        samples = sess.get("m_weatherForecastSamples", [])
        cur_session_type = sess.get("m_sessionType", 0)

        result = []
        for fc in samples[:n_samples]:
            if fc.get("m_sessionType", 0) != cur_session_type:
                continue
            offset = fc.get("m_timeOffset", 0)
            if offset == 0:
                continue
            result.append({
                "timeOffset": offset,
                "weather": fc.get("m_weather", 0),
                "trackTemperature": fc.get("m_trackTemperature", 0),
                "trackTemperatureChange": fc.get("m_trackTemperatureChange", 0),
                "airTemperature": fc.get("m_airTemperature", 0),
                "airTemperatureChange": fc.get("m_airTemperatureChange", 0),
                "rainPercentage": fc.get("m_rainPercentage", 0),
            })
        return result

    # -- Lap ------------------------------------------------------------------

    def get_lap(self) -> dict:
        """Build the lap data dict for the WebSocket message."""
        lap = self._player_car(2, "m_lapData")
        return {
            "currentLap": lap.get("m_currentLapNum", 0),
            "lapDistance": round(lap.get("m_lapDistance", 0), 2),
            "carPosition": lap.get("m_carPosition", 0),
            "lastLapTimeMs": lap.get("m_lastLapTimeInMS", 0),
            "currentLapTimeMs": lap.get("m_currentLapTimeInMS", 0),
        }

    # -- Pit status -----------------------------------------------------------

    def get_pit_status(self) -> dict:
        """Build the pit status dict for the WebSocket message."""
        lap = self._player_car(2, "m_lapData")
        return {
            "dataAvailable": bool(lap),
            "pitStatus": lap.get("m_pitStatus", 0),
            "numPitStops": lap.get("m_numPitStops", 0),
            "pitLaneTimerActive": bool(lap.get("m_pitLaneTimerActive", 0)),
            "pitLaneTimeMs": lap.get("m_pitLaneTimeInLaneInMS", 0),
            "pitStopTimeMs": lap.get("m_pitStopTimerInMS", 0),
            "driverStatus": lap.get("m_driverStatus", 0),
            "sessionType": self._state.get(1, {}).get("m_sessionType", 0),
        }

    # -- Track map ------------------------------------------------------------

    def get_track_map(self) -> dict | None:
        """Build the track map data dict for the WebSocket message."""
        motion = self._state.get(0)
        if not motion:
            return None

        motion_cars = motion.get("m_carMotionData", [])
        if not motion_cars:
            return None

        lap_pkt = self._state.get(2, {})
        lap_cars = lap_pkt.get("m_lapData", [])
        parts_pkt = self._state.get(4, {})
        parts_cars = parts_pkt.get("m_participants", [])

        track_map_cars = []
        for i in range(len(motion_cars)):
            m = motion_cars[i]
            lap = lap_cars[i] if i < len(lap_cars) else {}
            part = parts_cars[i] if i < len(parts_cars) else {}

            wx = m.get("m_worldPositionX", 0)
            wz = m.get("m_worldPositionZ", 0)

            # Compute abbreviation
            driver_id = part.get("m_driverId", 255)
            abbrev = DRIVER_ABBREVIATIONS.get(driver_id, "")
            if not abbrev:
                raw_name = part.get("m_name", "")
                name = raw_name.split("\x00")[0] if isinstance(raw_name, str) else ""
                abbrev = name[:3].upper() if name else ""

            team_id = part.get("m_teamId", 255)
            team_abbrev = TEAM_ABBREVIATIONS.get(team_id, "")

            track_map_cars.append({
                "x": wx,
                "z": wz,
                "position": lap.get("m_carPosition", 0),
                "lapDistance": lap.get("m_lapDistance", 0),
                "active": (wx != 0 or wz != 0) and lap.get("m_driverStatus", 0) >= 1,
                "abbreviation": abbrev,
                "teamAbbreviation": team_abbrev,
            })

        return {
            "playerIndex": self.player_car_index,
            "cars": track_map_cars,
        }

    # -- Marshal zones & sector boundaries ------------------------------------

    def get_marshal_zones(self) -> list[dict]:
        """Extract active marshal zones as [{zoneStart, zoneFlag}]."""
        sess = self._state.get(1, {})
        num_zones = sess.get("m_numMarshalZones", 0)
        zones = sess.get("m_marshalZones", [])
        return [
            {"zoneStart": z.get("m_zoneStart", 0), "zoneFlag": z.get("m_zoneFlag", 0)}
            for z in zones[:num_zones]
        ]

    def get_sector_boundaries(self) -> dict:
        """Extract sector 2/3 start distances in metres."""
        sess = self._state.get(1, {})
        return {
            "sector2Start": sess.get("m_sector2LapDistanceStart", 0),
            "sector3Start": sess.get("m_sector3LapDistanceStart", 0),
        }

    def get_track_id(self) -> int:
        """Return the raw trackId from the session packet."""
        sess = self._state.get(1, {})
        return sess.get("m_trackId", -1)

    # -- Session context (for agent initialization) ---------------------------

    def get_session_context(self) -> str:
        """Build a human-readable session context string for agent initialization."""
        sess = self._state.get(1, {})
        session_type = SESSION_TYPE_LABELS.get(sess.get("m_sessionType", 0), "Unknown")
        track = TRACK_NAMES_SHORT.get(sess.get("m_trackId", -1), "Unknown Track")
        total_laps = sess.get("m_totalLaps", 0)
        weather = WEATHER_LABELS.get(sess.get("m_weather", 0), "Unknown")
        air_temp = sess.get("m_airTemperature", 0)
        track_temp = sess.get("m_trackTemperature", 0)

        lines = [
            "## Current Session Context",
            f"- Session: {session_type}",
            f"- Track: {track}",
            f"- Weather: {weather}",
            f"- Air temperature: {air_temp}\u00b0C",
            f"- Track temperature: {track_temp}\u00b0C",
        ]
        if total_laps > 0:
            lines.append(f"- Total laps: {total_laps}")
        return "\n".join(lines)
