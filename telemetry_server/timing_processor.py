"""Computes lap timing summaries and standings from telemetry state."""

from common.f1_structs.f1_constants import DRIVER_ABBREVIATIONS
from common.f1_structs.f1_constants import MAX_NUM_CARS
from common.f1_structs.f1_constants import TEAM_ABBREVIATIONS
from common.f1_structs.f1_constants import VISUAL_TYRE_COMPOUND

RACE_SESSION_TYPES = {10, 11, 12, 15, 17}  # RACE, RACE 2, RACE 3, RACE SHORT, SPRINT


def _combine_sector_time(minutes_part: int, ms_part: int) -> int:
    """Combine the minutes and milliseconds parts of a sector time.

    Args:
        minutes_part: Whole minute part (0-255).
        ms_part: Milliseconds part (0-59999).

    Returns:
        Total time in milliseconds, or 0 if both parts are zero.
    """
    return minutes_part * 60_000 + ms_part


class TimingProcessor:
    """Computes player lap timing and race standings from packet state."""

    def get_player_lap_timing(
        self, player_idx: int, state: dict[int, dict], session_histories: dict[int, dict],
    ) -> dict:
        """Build the player's lap timing summary.

        Args:
            player_idx: Index of the player's car.
            state: Shared packet state dict keyed by packet ID.
            session_histories: Per-car session history data keyed by car index.

        Returns:
            Dict with current lap info, sector times, personal/overall bests, and lap history.
        """
        lap_data = self._get_player_lap_data(player_idx, state)
        player_history = session_histories.get(player_idx, {})

        current_lap = lap_data.get("m_currentLapNum", 0)
        current_sector = lap_data.get("m_sector", 0)
        current_lap_time_ms = lap_data.get("m_currentLapTimeInMS", 0)
        current_lap_invalid = bool(lap_data.get("m_currentLapInvalid", 0))
        last_lap_time_ms = lap_data.get("m_lastLapTimeInMS", 0)

        # Sector times from packet 2 (real-time, set when sector completes)
        s1_ms = _combine_sector_time(
            lap_data.get("m_sector1TimeMinutesPart", 0),
            lap_data.get("m_sector1TimeMSPart", 0),
        )
        s2_ms = _combine_sector_time(
            lap_data.get("m_sector2TimeMinutesPart", 0),
            lap_data.get("m_sector2TimeMSPart", 0),
        )

        personal_best = self._get_personal_best(player_history)
        overall_best = self._get_overall_best(session_histories)
        lap_history = self._get_lap_history(player_history, current_lap)

        return {
            "currentLap": current_lap,
            "currentSector": current_sector,
            "currentLapTimeMs": current_lap_time_ms,
            "currentLapInvalid": current_lap_invalid,
            "sector1Ms": s1_ms,
            "sector2Ms": s2_ms,
            "lastLapTimeMs": last_lap_time_ms,
            "personalBest": personal_best,
            "overallBest": overall_best,
            "lapHistory": lap_history,
        }

    def get_standings(
        self, player_idx: int, state: dict[int, dict],
        session_type: int = 0, session_histories: dict[int, dict] | None = None,
    ) -> list[dict]:
        """Build standings from telemetry. Race sessions use live positions; practice/quali use best lap times.

        Args:
            player_idx: Index of the player's car.
            state: Shared packet state dict keyed by packet ID.
            session_type: Raw session type value from packet 1.
            session_histories: Per-car session history data keyed by car index.

        Returns:
            List of standing entries sorted by position.
        """
        if session_type not in RACE_SESSION_TYPES and session_histories:
            return self._get_practice_quali_standings(player_idx, state, session_histories)
        return self._get_race_standings(player_idx, state)

    def _get_race_standings(self, player_idx: int, state: dict[int, dict]) -> list[dict]:
        """Build race standings from packet 2 (lap data) and packet 4 (participants)."""
        lap_pkt = state.get(2, {})
        lap_cars = lap_pkt.get("m_lapData", [])
        parts_pkt = state.get(4, {})
        parts_cars = parts_pkt.get("m_participants", [])
        status_pkt = state.get(7, {})
        status_cars = status_pkt.get("m_carStatusData", [])

        standings = []
        for i in range(min(len(lap_cars), MAX_NUM_CARS)):
            car = lap_cars[i]
            part = parts_cars[i] if i < len(parts_cars) else {}
            status_car = status_cars[i] if i < len(status_cars) else {}

            position = car.get("m_carPosition", 0)
            result_status = car.get("m_resultStatus", 0)
            if position == 0 or result_status == 0:
                continue

            driver_id = part.get("m_driverId", 255)
            abbrev = DRIVER_ABBREVIATIONS.get(driver_id, "")
            if not abbrev:
                raw_name = part.get("m_name", "")
                name = raw_name.split("\x00")[0] if isinstance(raw_name, str) else ""
                abbrev = name[:3].upper() if name else "???"

            team_id = part.get("m_teamId", 255)

            gap_leader_ms = _combine_sector_time(
                car.get("m_deltaToRaceLeaderMinutesPart", 0),
                car.get("m_deltaToRaceLeaderMSPart", 0),
            )
            gap_front_ms = _combine_sector_time(
                car.get("m_deltaToCarInFrontMinutesPart", 0),
                car.get("m_deltaToCarInFrontMSPart", 0),
            )

            standings.append({
                "position": position,
                "abbreviation": abbrev,
                "teamId": team_id,
                "teamAbbreviation": TEAM_ABBREVIATIONS.get(team_id, ""),
                "gapToLeaderMs": gap_leader_ms,
                "gapToFrontMs": gap_front_ms,
                "currentLap": car.get("m_currentLapNum", 0),
                "isPlayer": i == player_idx,
                "driverStatus": car.get("m_driverStatus", 0),
                "resultStatus": result_status,
                "lastLapTimeMs": car.get("m_lastLapTimeInMS", 0),
                "visualCompound": VISUAL_TYRE_COMPOUND.get(status_car.get("m_visualTyreCompound", 0), ""),
            })

        standings.sort(key=lambda s: s["position"])
        return standings

    def _get_practice_quali_standings(
        self, player_idx: int, state: dict[int, dict], session_histories: dict[int, dict],
    ) -> list[dict]:
        """Build standings ordered by best lap time for practice/qualifying sessions."""
        lap_pkt = state.get(2, {})
        lap_cars = lap_pkt.get("m_lapData", [])
        parts_pkt = state.get(4, {})
        parts_cars = parts_pkt.get("m_participants", [])
        status_pkt = state.get(7, {})
        status_cars = status_pkt.get("m_carStatusData", [])

        entries = []
        for i in range(min(len(lap_cars), MAX_NUM_CARS)):
            car = lap_cars[i]
            part = parts_cars[i] if i < len(parts_cars) else {}
            status_car = status_cars[i] if i < len(status_cars) else {}

            result_status = car.get("m_resultStatus", 0)
            if result_status == 0:
                continue

            history = session_histories.get(i, {})
            personal_best = self._get_personal_best(history)
            best_lap_ms = personal_best["lapMs"]
            if best_lap_ms <= 0:
                continue

            driver_id = part.get("m_driverId", 255)
            abbrev = DRIVER_ABBREVIATIONS.get(driver_id, "")
            if not abbrev:
                raw_name = part.get("m_name", "")
                name = raw_name.split("\x00")[0] if isinstance(raw_name, str) else ""
                abbrev = name[:3].upper() if name else "???"

            team_id = part.get("m_teamId", 255)

            entries.append({
                "carIndex": i,
                "bestLapMs": best_lap_ms,
                "abbreviation": abbrev,
                "teamId": team_id,
                "teamAbbreviation": TEAM_ABBREVIATIONS.get(team_id, ""),
                "currentLap": car.get("m_currentLapNum", 0),
                "isPlayer": i == player_idx,
                "driverStatus": car.get("m_driverStatus", 0),
                "resultStatus": result_status,
                "visualCompound": VISUAL_TYRE_COMPOUND.get(status_car.get("m_visualTyreCompound", 0), ""),
            })

        entries.sort(key=lambda e: e["bestLapMs"])

        standings = []
        leader_ms = entries[0]["bestLapMs"] if entries else 0
        prev_ms = leader_ms
        for pos, entry in enumerate(entries, start=1):
            gap_to_leader = entry["bestLapMs"] - leader_ms if pos > 1 else 0

            standings.append({
                "position": pos,
                "abbreviation": entry["abbreviation"],
                "teamId": entry["teamId"],
                "teamAbbreviation": entry["teamAbbreviation"],
                "gapToLeaderMs": gap_to_leader,
                "gapToFrontMs": gap_to_leader,
                "currentLap": entry["currentLap"],
                "isPlayer": entry["isPlayer"],
                "driverStatus": entry["driverStatus"],
                "resultStatus": entry["resultStatus"],
                "lastLapTimeMs": entry["bestLapMs"],
                "visualCompound": entry["visualCompound"],
            })

        return standings

    @staticmethod
    def _get_player_lap_data(player_idx: int, state: dict[int, dict]) -> dict:
        """Get the player's lap data from packet 2."""
        pkt = state.get(2, {})
        cars = pkt.get("m_lapData", [])
        return cars[player_idx] if player_idx < len(cars) else {}

    @staticmethod
    def _get_personal_best(history: dict) -> dict:
        """Extract personal best times from a car's session history."""
        laps = history.get("m_lapHistoryData", [])
        num_laps = history.get("m_numLaps", 0)

        best = {"lapMs": 0, "s1Ms": 0, "s2Ms": 0, "s3Ms": 0}

        best_lap_num = history.get("m_bestLapTimeLapNum", 0)
        if best_lap_num > 0 and best_lap_num <= num_laps and best_lap_num <= len(laps):
            lap = laps[best_lap_num - 1]
            best["lapMs"] = lap.get("m_lapTimeInMS", 0)

        best_s1_num = history.get("m_bestSector1LapNum", 0)
        if best_s1_num > 0 and best_s1_num <= num_laps and best_s1_num <= len(laps):
            lap = laps[best_s1_num - 1]
            best["s1Ms"] = _combine_sector_time(
                lap.get("m_sector1TimeMinutesPart", 0), lap.get("m_sector1TimeMSPart", 0),
            )

        best_s2_num = history.get("m_bestSector2LapNum", 0)
        if best_s2_num > 0 and best_s2_num <= num_laps and best_s2_num <= len(laps):
            lap = laps[best_s2_num - 1]
            best["s2Ms"] = _combine_sector_time(
                lap.get("m_sector2TimeMinutesPart", 0), lap.get("m_sector2TimeMSPart", 0),
            )

        best_s3_num = history.get("m_bestSector3LapNum", 0)
        if best_s3_num > 0 and best_s3_num <= num_laps and best_s3_num <= len(laps):
            lap = laps[best_s3_num - 1]
            best["s3Ms"] = _combine_sector_time(
                lap.get("m_sector3TimeMinutesPart", 0), lap.get("m_sector3TimeMSPart", 0),
            )

        return best

    @staticmethod
    def _get_overall_best(session_histories: dict[int, dict]) -> dict:
        """Find the overall best lap and sector times across all cars."""
        best = {"lapMs": 0, "s1Ms": 0, "s2Ms": 0, "s3Ms": 0}

        for history in session_histories.values():
            laps = history.get("m_lapHistoryData", [])
            num_laps = history.get("m_numLaps", 0)

            best_lap_num = history.get("m_bestLapTimeLapNum", 0)
            if best_lap_num > 0 and best_lap_num <= num_laps and best_lap_num <= len(laps):
                lap_ms = laps[best_lap_num - 1].get("m_lapTimeInMS", 0)
                if lap_ms > 0 and (best["lapMs"] == 0 or lap_ms < best["lapMs"]):
                    best["lapMs"] = lap_ms

            for sector_num, (min_key, ms_key) in enumerate([
                ("m_sector1TimeMinutesPart", "m_sector1TimeMSPart"),
                ("m_sector2TimeMinutesPart", "m_sector2TimeMSPart"),
                ("m_sector3TimeMinutesPart", "m_sector3TimeMSPart"),
            ], start=1):
                best_s_num = history.get(f"m_bestSector{sector_num}LapNum", 0)
                if best_s_num > 0 and best_s_num <= num_laps and best_s_num <= len(laps):
                    s_ms = _combine_sector_time(
                        laps[best_s_num - 1].get(min_key, 0), laps[best_s_num - 1].get(ms_key, 0),
                    )
                    key = f"s{sector_num}Ms"
                    if s_ms > 0 and (best[key] == 0 or s_ms < best[key]):
                        best[key] = s_ms

        return best

    @staticmethod
    def _get_lap_history(history: dict, current_lap: int) -> list[dict]:
        """Build the lap history list (most recent first, excluding current lap)."""
        laps = history.get("m_lapHistoryData", [])
        num_laps = history.get("m_numLaps", 0)

        # num_laps includes the current partial lap, so completed laps = num_laps - 1
        completed = min(num_laps - 1, len(laps)) if num_laps > 0 else 0

        result = []
        for i in range(completed - 1, -1, -1):
            lap = laps[i]
            valid_flags = lap.get("m_lapValidBitFlags", 0)
            result.append({
                "lapNum": i + 1,
                "lapTimeMs": lap.get("m_lapTimeInMS", 0),
                "s1Ms": _combine_sector_time(
                    lap.get("m_sector1TimeMinutesPart", 0), lap.get("m_sector1TimeMSPart", 0),
                ),
                "s2Ms": _combine_sector_time(
                    lap.get("m_sector2TimeMinutesPart", 0), lap.get("m_sector2TimeMSPart", 0),
                ),
                "s3Ms": _combine_sector_time(
                    lap.get("m_sector3TimeMinutesPart", 0), lap.get("m_sector3TimeMSPart", 0),
                ),
                "valid": bool(valid_flags & 0x01),
            })

        return result
