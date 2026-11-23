"""Unit tests for FuelLapEstimator."""

import pytest

from telemetry_server.alerts.fuel_lap_estimator import FuelLapEstimator

TRACK_LENGTH = 5000.0
STEP = 50.0


class TestFuelLapEstimator:
    """Tests for the fuel burn rate estimate."""

    @staticmethod
    def _drive(
        estimator: FuelLapEstimator, start_fuel: float, start_distance: float, metres: float, burn_per_metre: float
    ) -> tuple[float, float]:
        """Feed samples every STEP metres and return the final (fuel, lap distance)."""
        fuel = start_fuel
        distance = start_distance
        estimator.update(fuel, distance, TRACK_LENGTH)
        driven = 0.0
        while driven < metres:
            driven += STEP
            fuel -= STEP * burn_per_metre
            distance = (distance + STEP) % TRACK_LENGTH
            estimator.update(fuel, distance, TRACK_LENGTH)
        return fuel, distance

    def test_no_rate_before_any_sample(self) -> None:
        """The estimator returns None when it has no data."""
        estimator = FuelLapEstimator()
        assert estimator.fuel_to_finish_lap(0.0, TRACK_LENGTH) is None
        assert estimator.fuel_per_lap(TRACK_LENGTH) is None

    def test_rate_after_full_lap_across_line(self) -> None:
        """A full lap that crosses the start line gives the burn rate."""
        estimator = FuelLapEstimator()
        self._drive(estimator, 10.0, 3000.0, TRACK_LENGTH, 2.0 / TRACK_LENGTH)
        assert estimator.fuel_per_lap(TRACK_LENGTH) == pytest.approx(2.0)

    def test_rate_before_full_lap(self) -> None:
        """After 20 % of a lap, the estimator uses the distance driven so far."""
        estimator = FuelLapEstimator()
        self._drive(estimator, 10.0, 0.0, 2500.0, 2.0 / TRACK_LENGTH)
        assert estimator.fuel_per_lap(TRACK_LENGTH) == pytest.approx(2.0)
        assert estimator.fuel_to_finish_lap(2500.0, TRACK_LENGTH) == pytest.approx(1.0)

    def test_no_rate_below_min_fraction(self) -> None:
        """Less than 20 % of a lap gives no rate."""
        estimator = FuelLapEstimator()
        self._drive(estimator, 10.0, 0.0, 500.0, 2.0 / TRACK_LENGTH)
        assert estimator.fuel_per_lap(TRACK_LENGTH) is None

    def test_refuel_starts_new_window(self) -> None:
        """A fuel increase starts a new window and keeps the known rate."""
        estimator = FuelLapEstimator()
        self._drive(estimator, 10.0, 0.0, TRACK_LENGTH, 2.0 / TRACK_LENGTH)
        estimator.update(50.0, 0.0, TRACK_LENGTH)
        assert estimator.fuel_per_lap(TRACK_LENGTH) == pytest.approx(2.0)
        self._drive(estimator, 50.0, 0.0, TRACK_LENGTH, 3.0 / TRACK_LENGTH)
        assert estimator.fuel_per_lap(TRACK_LENGTH) == pytest.approx(3.0)

    def test_distance_jump_starts_new_window(self) -> None:
        """A teleport (garage to pit exit) does not count as distance driven."""
        estimator = FuelLapEstimator()
        estimator.update(5.0, 165.0, TRACK_LENGTH)
        # The car appears at the pit exit with fuel already used
        self._drive(estimator, 4.0, 2700.0, 2000.0, 2.0 / TRACK_LENGTH)
        assert estimator.fuel_per_lap(TRACK_LENGTH) == pytest.approx(2.0)

    def test_fuel_drop_starts_new_window(self) -> None:
        """A sudden fuel drop after a teleport does not count as fuel burned."""
        estimator = FuelLapEstimator()
        estimator.update(5.0, 165.0, TRACK_LENGTH)
        estimator.update(5.0, 2600.0, TRACK_LENGTH)
        # One sample later, the game takes off 0.88 kg for the skipped pit lane
        self._drive(estimator, 4.12, 2620.0, TRACK_LENGTH, 2.0 / TRACK_LENGTH)
        assert estimator.fuel_per_lap(TRACK_LENGTH) == pytest.approx(2.0)

    def test_negative_lap_distance_ignored(self) -> None:
        """Samples before the first line crossing do not start the window."""
        estimator = FuelLapEstimator()
        estimator.update(20.0, -300.0, TRACK_LENGTH)
        self._drive(estimator, 10.0, 0.0, 2500.0, 2.0 / TRACK_LENGTH)
        assert estimator.fuel_per_lap(TRACK_LENGTH) == pytest.approx(2.0)

    def test_reset_keeps_rate(self) -> None:
        """Reset keeps the full-lap rate, and a partial lap after reset does not overwrite it."""
        estimator = FuelLapEstimator()
        self._drive(estimator, 10.0, 0.0, TRACK_LENGTH, 2.0 / TRACK_LENGTH)
        estimator.reset()
        self._drive(estimator, 8.0, 0.0, 2000.0, 4.0 / TRACK_LENGTH)
        assert estimator.fuel_per_lap(TRACK_LENGTH) == pytest.approx(2.0)

    def test_track_change_clears_rate(self) -> None:
        """A new track length deletes the known rate."""
        estimator = FuelLapEstimator()
        self._drive(estimator, 10.0, 0.0, 2500.0, 2.0 / TRACK_LENGTH)
        estimator.update(9.0, 0.0, 4000.0)
        assert estimator.fuel_per_lap(4000.0) is None
