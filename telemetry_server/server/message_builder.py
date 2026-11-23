"""Assembles the JSON message broadcast to WebSocket clients each frame."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from typing import Callable

if TYPE_CHECKING:
    from telemetry_server.alerts.aero_alert_processor import AeroAlertProcessor
    from telemetry_server.alerts.pit_alert_processor import PitAlertProcessor
    from telemetry_server.alerts.pu_alert_processor import PuAlertProcessor
    from telemetry_server.alerts.tyre_alert_processor import TyreAlertProcessor
    from telemetry_server.dispatch.agent_dispatch_manager import AgentDispatchManager
    from telemetry_server.telemetry_state_adapter import TelemetryStateAdapter
    from telemetry_server.timing_processor import TimingProcessor
    from telemetry_server.track_location_provider import TrackLocationProvider


class MessageBuilder:
    """Builds the JSON message from adapter data, alert logs, and agent responses.

    Called once per telemetry frame (packet 6). Runs the three alert
    processors and collects their new alerts for dispatch.
    """

    def __init__(
        self,
        adapter_fn: Callable[[], TelemetryStateAdapter],
        aero_processor: AeroAlertProcessor,
        tyre_processor: TyreAlertProcessor,
        pu_processor: PuAlertProcessor,
        pit_processor: PitAlertProcessor,
        dispatch_manager: AgentDispatchManager,
        session_time_fn: Callable[[], float],
        state_ready_fn: Callable[[], bool],
        track_location: TrackLocationProvider | None = None,
        timing_processor: TimingProcessor | None = None,
        state_fn: Callable[[], dict] | None = None,
        session_histories_fn: Callable[[], dict] | None = None,
    ) -> None:
        """Initialise the message builder.

        Args:
            adapter_fn: Callable returning the current TelemetryStateAdapter.
            aero_processor: The aero alert processor.
            tyre_processor: The tyre alert processor.
            pu_processor: The PU alert processor.
            pit_processor: The pit status alert processor.
            dispatch_manager: The agent dispatch manager (for reading responses).
            session_time_fn: Callable returning the current session time.
            state_ready_fn: Callable returning True when essential packets are available.
            track_location: Provider for enriching alerts with track position context.
            timing_processor: Processor for lap timing and standings data.
            state_fn: Callable returning the current packet state dict.
            session_histories_fn: Callable returning per-car session histories.
        """
        self._adapter_fn = adapter_fn
        self._aero = aero_processor
        self._tyre = tyre_processor
        self._pu = pu_processor
        self._pit = pit_processor
        self._dispatch = dispatch_manager
        self._session_time_fn = session_time_fn
        self._state_ready_fn = state_ready_fn
        self._track_location = track_location
        self._timing = timing_processor
        self._state_fn = state_fn
        self._session_histories_fn = session_histories_fn

    def build(self) -> tuple[str, list[dict], list[dict], list[dict]]:
        """Build a JSON message from the latest merged state via the adapter.

        Returns:
            A tuple of (json_string, new_aero_alerts, new_tyre_alerts, new_pu_alerts).
        """
        adapter = self._adapter_fn()
        session_time = self._session_time_fn()

        aero = adapter.get_aero()
        tyres = adapter.get_tyres()
        compound, compound_visual = adapter.get_compound()
        power_unit = adapter.get_power_unit()
        session = adapter.get_session()
        weather_forecast = adapter.get_weather_forecast()
        lap = adapter.get_lap()

        tyre_sets = adapter.get_tyre_sets()
        track_map = adapter.get_track_map()
        pit_status = adapter.get_pit_status()
        marshal_zones = adapter.get_marshal_zones()
        sector_boundaries = adapter.get_sector_boundaries()

        new_pit_alerts = self._pit.process(pit_status, session_time)
        if new_pit_alerts:
            # Add to specialist alert logs for display in all panels
            self._aero.alerts_log.extend(new_pit_alerts)
            self._tyre.alerts_log.extend(new_pit_alerts)
            self._pu.alerts_log.extend(new_pit_alerts)

            # Queue to all dispatchers for agent processing + race engineer display
            formatted = [f"PIT ALERT {a['message']} {a['time']}" for a in new_pit_alerts]
            self._dispatch.damage.queue(formatted)
            self._dispatch.tyres.queue(formatted)
            self._dispatch.pu.queue(formatted)
            self._dispatch.race_engineer.queue(formatted)

        if self._state_ready_fn():
            aero_snapshot = {**aero, "sessionTime": session_time}
            new_aero_alerts = self._aero.process(aero_snapshot)

            new_tyre_alerts = self._tyre.process({
                "sessionTime": session_time,
                "tyres": tyres,
                "compound": compound,
                "compoundVisual": compound_visual,
            })

            new_pu_alerts = self._pu.process({
                **power_unit,
                "sessionTime": session_time,
                "lapDistance": lap.get("lapDistance", 0),
                "trackLength": session.get("trackLength", 0),
            })
        else:
            new_aero_alerts = []
            new_tyre_alerts = []
            new_pu_alerts = []

        # Compute track location context for alert enrichment
        location = ""
        if self._track_location:
            location = self._track_location.describe(
                lap.get("lapDistance", 0),
                session.get("trackLength", 0),
                sector_boundaries.get("sector2Start", 0),
                sector_boundaries.get("sector3Start", 0),
                current_lap=lap.get("currentLap", 0),
                pit_status=pit_status.get("pitStatus", 0),
            )

        # Enrich alert messages with location (mutates shared dicts in alerts_log)
        if location:
            loc_tag = f" [{location}]"
            for a in new_aero_alerts + new_tyre_alerts + new_pu_alerts:
                a["message"] += loc_tag

        # Compute timing and standings
        timing_data = None
        standings_data = None
        if self._timing and self._state_fn and self._session_histories_fn:
            player_idx = adapter.player_car_index
            cur_state = self._state_fn()
            timing_data = self._timing.get_player_lap_timing(
                player_idx, cur_state, self._session_histories_fn(),
            )
            session_type = cur_state.get(1, {}).get("m_sessionType", 0)
            standings_data = self._timing.get_standings(
                player_idx, cur_state, session_type, self._session_histories_fn(),
            )

        msg = json.dumps({
            "tyres": tyres,
            "compound": compound,
            "compoundVisual": compound_visual,
            "tyresAgeLaps": adapter.get_tyres_age_laps(),
            "currentLap": lap.get("currentLap", 0),
            "lapDistance": lap.get("lapDistance", 0),
            "speed": aero.get("speed", 0),
            "sessionTime": session_time,
            "powerUnit": power_unit,
            "aero": aero,
            "session": session,
            "weatherForecast": weather_forecast,
            "tyreSets": tyre_sets,
            "trackMap": track_map,
            "pitStatus": pit_status,
            "tyreAlerts": {
                "alerts": self._tyre.alerts_log,
                "activeCount": len(self._tyre.conditions),
            },
            "puAlerts": {
                "alerts": self._pu.alerts_log,
                "activeCount": len(self._pu.conditions),
            },
            "aeroAlerts": {
                "alerts": self._aero.alerts_log,
                "activeCount": len(self._aero.conditions),
            },
            "damageReport": {
                "response": self._dispatch.damage.response,
                "time": self._dispatch.damage.response_time,
            },
            "tyresReport": {
                "response": self._dispatch.tyres.response,
                "time": self._dispatch.tyres.response_time,
            },
            "puReport": {
                "response": self._dispatch.pu.response,
                "time": self._dispatch.pu.response_time,
            },
            "raceEngineerReport": {
                "responses": self._dispatch.race_engineer.responses_log,
                "alerts": self._dispatch.race_engineer.alerts_log,
            },
            "marshalZones": marshal_zones,
            "sectorBoundaries": sector_boundaries,
            "playerDrs": {
                "drsActive": aero.get("drs", False),
                "drsAllowed": aero.get("drsAllowed", False),
                "drsActivationDistance": aero.get("drsActivationDistance", 0),
            },
            "timing": timing_data,
            "standings": standings_data,
        })
        return msg, new_aero_alerts, new_tyre_alerts, new_pu_alerts
