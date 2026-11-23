"""Fuel burn estimator — predicts the fuel needed to reach the end of the current lap."""

from telemetry_server.alerts.alert_constants import FUEL_MAX_DISTANCE_STEP
from telemetry_server.alerts.alert_constants import FUEL_MAX_DROP_STEP
from telemetry_server.alerts.alert_constants import FUEL_RATE_MIN_LAP_FRACTION


class FuelLapEstimator:
    """Learns the fuel burn rate per metre from the fuel in the tank and the distance driven.

    Design: the estimator adds up the distance driven from sample to sample, and handles the wrap of
    ``lapDistance`` at the start line. It does not use the lap number, because the game does not always
    increment it (e.g. on a qualifying out-lap from the garage).

    The measurement window covers one full track length. When the window is full, the estimator stores
    the rate and starts a new window. Before the first full window, it stores a rate after
    ``FUEL_RATE_MIN_LAP_FRACTION`` of the track.

    These events start a new window and keep the last known rate:
     - a fuel increase (refuel, flashback, restart),
     - a distance jump larger than ``FUEL_MAX_DISTANCE_STEP`` (garage to pit exit, teleport),
     - a fuel drop larger than ``FUEL_MAX_DROP_STEP``. The game takes off the fuel for a skipped out-lap
       section one sample after it moves the car to the pit exit.

    ``reset()`` keeps the rate, because the burn rate depends on the car and the track, not on the session
    clock. A partial-lap estimate after a flashback or restart is less accurate than the last full-lap rate.
    A new track length deletes the rate.

    Used by ``PuAlertProcessor`` for the ``fuel_lap`` alert.
    """

    def __init__(self) -> None:
        """Initialise with no window and no known rate."""
        self._prev_distance: float | None = None
        self._prev_fuel: float = 0.0
        self._window_fuel: float = 0.0
        self._window_distance: float = 0.0
        self._track_length: float = 0.0
        self._burn_per_metre: float | None = None
        self._has_lap_rate: bool = False

    def reset(self) -> None:
        """Clear the measurement window (e.g. on session time reset). Keep the known rate for this track."""
        self._prev_distance = None
        self._window_fuel = 0.0
        self._window_distance = 0.0

    def update(self, fuel_kg: float, lap_distance: float, track_length: float) -> None:
        """Feed one telemetry sample.

        Args:
            fuel_kg: Fuel in the tank, in kg.
            lap_distance: Distance driven in the current lap, in metres. Negative before the first line crossing.
            track_length: Track length, in metres.
        """
        if track_length <= 0 or lap_distance < 0:
            self._prev_distance = None
            return

        if track_length != self._track_length:
            self._track_length = track_length
            self._burn_per_metre = None
            self._has_lap_rate = False
            self._prev_distance = None

        fuel_step = self._prev_fuel - fuel_kg
        if self._prev_distance is None or fuel_step < 0 or fuel_step > FUEL_MAX_DROP_STEP:
            self._start_window(fuel_kg, lap_distance)
            return

        step = lap_distance - self._prev_distance
        if step < -track_length / 2:
            # The car crossed the start line
            step += track_length
        if abs(step) > FUEL_MAX_DISTANCE_STEP:
            self._start_window(fuel_kg, lap_distance)
            return

        self._prev_distance = lap_distance
        self._prev_fuel = fuel_kg
        self._window_distance += step
        burned = self._window_fuel - fuel_kg

        if self._window_distance >= track_length:
            if burned > 0:
                self._burn_per_metre = burned / self._window_distance
                self._has_lap_rate = True
            self._start_window(fuel_kg, lap_distance)
        elif (
            not self._has_lap_rate
            and burned > 0
            and self._window_distance >= FUEL_RATE_MIN_LAP_FRACTION * track_length
        ):
            self._burn_per_metre = burned / self._window_distance

    def fuel_to_finish_lap(self, lap_distance: float, track_length: float) -> float | None:
        """Return the fuel in kg needed to reach the end of the current lap, or None if the rate is unknown."""
        if self._burn_per_metre is None or track_length <= 0:
            return None
        return self._burn_per_metre * max(0.0, track_length - lap_distance)

    def fuel_per_lap(self, track_length: float) -> float | None:
        """Return the fuel in kg needed for one full lap, or None if the rate is unknown."""
        if self._burn_per_metre is None or track_length <= 0:
            return None
        return self._burn_per_metre * track_length

    def _start_window(self, fuel_kg: float, lap_distance: float) -> None:
        """Start a new measurement window from this sample."""
        self._prev_distance = lap_distance
        self._prev_fuel = fuel_kg
        self._window_fuel = fuel_kg
        self._window_distance = 0.0
