"""Unit tests for the fuel_lap alert in PuAlertProcessor."""

from telemetry_server.alerts.pu_alert_processor import PuAlertProcessor

TRACK_LENGTH = 5000.0
STEP = 50.0
BURN_PER_METRE = 2.0 / TRACK_LENGTH  # 2 kg per lap


class TestPuAlertProcessor:
    """Tests for the fuel-to-finish-lap alert."""

    @staticmethod
    def _snapshot(session_time: float, fuel: float, lap_distance: float) -> dict:
        """Build a PU snapshot with healthy values except fuel."""
        return {
            "sessionTime": session_time,
            "engineTemp": 100,
            "batteryPct": 80,
            "fuelInTank": fuel,
            "lapDistance": lap_distance,
            "trackLength": TRACK_LENGTH,
        }

    @staticmethod
    def _drive(processor: PuAlertProcessor, start_fuel: float, metres: float) -> list[dict]:
        """Drive from the start line, one sample every STEP metres. Return the fuel_lap alerts."""
        alerts: list[dict] = []
        driven = 0.0
        while driven <= metres:
            fuel = start_fuel - driven * BURN_PER_METRE
            snapshot = TestPuAlertProcessor._snapshot(1.0 + driven, fuel, driven % TRACK_LENGTH)
            alerts.extend(a for a in processor.process(snapshot) if "lap" in a.get("message", ""))
            driven += STEP
        return alerts

    def test_no_alert_without_rate(self) -> None:
        """No alert fires before the burn rate is known."""
        processor = PuAlertProcessor()
        assert not self._drive(processor, 0.3, 500.0)

    def test_no_alert_with_enough_fuel(self) -> None:
        """No alert fires when the tank holds enough fuel for two laps."""
        processor = PuAlertProcessor()
        assert not self._drive(processor, 10.0, 2500.0)
        assert "fuel_lap" not in processor.conditions

    def test_critical_fires(self) -> None:
        """A critical alert fires when the fuel cannot finish the lap."""
        processor = PuAlertProcessor()
        # 1.5 kg at the line, 2 kg per lap: the rate is known at 1000 m with 1.1 kg left, 1.6 kg needed
        alerts = self._drive(processor, 1.5, 2000.0)
        assert [a.get("level") for a in alerts] == ["critical"]
        assert "cannot finish lap" in alerts[0].get("message", "")
        assert alerts[0].get("time", "").endswith("FUEL")

    def test_warning_escalates_to_critical(self) -> None:
        """A warning fires first, then a critical alert when fuel drops further."""
        processor = PuAlertProcessor()
        # 2.5 kg at the line: warning at 1000 m (2.1 kg vs 3.6 kg), critical at the start of lap 2
        alerts = self._drive(processor, 2.5, 6000.0)
        assert [a.get("level") for a in alerts] == ["warning", "critical"]
        assert "cannot complete next lap" in alerts[0].get("message", "")

    def test_clear_after_refuel(self) -> None:
        """A clear message fires when the tank holds enough fuel again."""
        processor = PuAlertProcessor()
        self._drive(processor, 1.5, 2000.0)
        alerts = processor.process(self._snapshot(5000.0, 50.0, 2000.0))
        assert "fuel sufficient to finish lap" in [a.get("message") for a in alerts]
        assert "fuel_lap" not in processor.conditions
