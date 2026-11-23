"""Power unit alert processor — engine temp, damage, fuel, battery, ERS/fuel-mix changes."""

from telemetry_server.alerts.alert_constants import PU_ALERT_DEFS
from telemetry_server.alerts.alert_constants import PU_DAMAGE_KEYS
from telemetry_server.alerts.alert_constants import PU_DAMAGE_REFIRE_STEP
from telemetry_server.alerts.alert_utils import format_session_time
from telemetry_server.alerts.fuel_lap_estimator import FuelLapEstimator


class PuAlertProcessor:
    """Evaluates power unit telemetry snapshots and accumulates alerts.

    Tracks engine temperature, engine/gearbox damage, fuel remaining laps,
    fuel needed to finish the lap (see ``FuelLapEstimator``), battery state-of-charge,
    ERS deploy mode changes, and fuel mix changes.
    """

    def __init__(self) -> None:
        """Initialise with empty state."""
        self.conditions: dict = {}
        self.alerts_log: list[dict] = []
        self.prev_session_time: float = 0.0
        self.prev_ers_mode: str = ""
        self.prev_fuel_mix: str = ""
        self.fuel_estimator: FuelLapEstimator = FuelLapEstimator()

    def reset(self) -> None:
        """Clear all accumulated state (e.g. on session change). The fuel estimator keeps its burn rate."""
        self.conditions.clear()
        self.alerts_log.clear()
        self.prev_session_time = 0.0
        self.prev_ers_mode = ""
        self.prev_fuel_mix = ""
        self.fuel_estimator.reset()

    def process(self, snapshot: dict) -> list[dict]:
        """Process a power unit snapshot and return any new alerts."""
        st = snapshot.get("sessionTime", 0.0)

        # Detect new session (session time resets)
        if st < self.prev_session_time:
            self.reset()
        self.prev_session_time = st

        new_alerts: list[dict] = []
        current_conditions: dict = {}
        ts = format_session_time(st)

        engine_temp = snapshot.get("engineTemp", 0)
        engine_damage = snapshot.get("engineDamage", 0)
        gearbox_damage = snapshot.get("gearboxDamage", 0)
        fuel_delta_laps = snapshot.get("fuelRemainingLaps", 0)
        battery_pct = snapshot.get("batteryPct", 0)
        fuel_in_tank = snapshot.get("fuelInTank", 0.0)
        lap_distance = snapshot.get("lapDistance", 0.0)
        track_length = snapshot.get("trackLength", 0)
        self.fuel_estimator.update(fuel_in_tank, lap_distance, track_length)
        fuel_needed = 0.0

        # Engine temperature
        if engine_temp > 130:
            current_conditions["eng_temp"] = {"level": "crit", "value": engine_temp}
        elif engine_temp > 120:
            current_conditions["eng_temp"] = {"level": "warn", "value": engine_temp}

        # Engine damage (0-100)
        if engine_damage > 20:
            current_conditions["eng_dmg"] = {"level": "crit", "value": engine_damage}
        elif engine_damage > 5:
            current_conditions["eng_dmg"] = {"level": "warn", "value": engine_damage}

        # Gearbox damage (0-100)
        if gearbox_damage > 20:
            current_conditions["gbx_dmg"] = {"level": "crit", "value": gearbox_damage}
        elif gearbox_damage > 5:
            current_conditions["gbx_dmg"] = {"level": "warn", "value": gearbox_damage}

        # Fuel delta vs plan (negative = running short)
        if fuel_delta_laps < -2.0:
            current_conditions["fuel"] = {"level": "crit", "value": fuel_delta_laps}
        elif fuel_delta_laps < -1.0:
            current_conditions["fuel"] = {"level": "warn", "value": fuel_delta_laps}

        # Fuel in tank vs fuel needed to finish this lap (crit) or this lap plus one more lap (warn)
        fuel_to_finish = self.fuel_estimator.fuel_to_finish_lap(lap_distance, track_length)
        fuel_per_lap = self.fuel_estimator.fuel_per_lap(track_length)
        if fuel_to_finish is not None and fuel_per_lap is not None and lap_distance >= 0:
            if fuel_in_tank < fuel_to_finish:
                current_conditions["fuel_lap"] = {"level": "crit", "value": fuel_in_tank}
                fuel_needed = fuel_to_finish
            elif fuel_in_tank < fuel_to_finish + fuel_per_lap:
                current_conditions["fuel_lap"] = {"level": "warn", "value": fuel_in_tank}
                fuel_needed = fuel_to_finish + fuel_per_lap

        # Battery SOC
        if battery_pct < 15:
            current_conditions["battery"] = {"level": "crit", "value": battery_pct}
        elif battery_pct < 30:
            current_conditions["battery"] = {"level": "warn", "value": battery_pct}

        # Fire alerts for new, escalated, or worsened conditions
        for key, cur in current_conditions.items():
            prev = self.conditions.get(key)
            defn = PU_ALERT_DEFS.get(key)
            if not defn:
                continue

            is_new = prev is None
            is_escalation = prev is not None and prev["level"] == "warn" and cur["level"] == "crit"
            is_worsened = (
                key in PU_DAMAGE_KEYS
                and prev is not None
                and prev["level"] == cur["level"]
                and cur["value"] >= prev["value"] + PU_DAMAGE_REFIRE_STEP
            )

            if is_new or is_escalation or is_worsened:
                alert_level = "critical" if cur["level"] == "crit" else "warning"

                if key == "eng_temp":
                    msg = (
                        f"Engine temp {engine_temp}\u00b0C \u2014 overheating"
                        if cur["level"] == "crit"
                        else f"Engine temp {engine_temp}\u00b0C \u2014 running hot"
                    )
                elif key == "eng_dmg":
                    msg = (
                        f"Engine damage critical ({engine_damage}%)"
                        if cur["level"] == "crit"
                        else f"Engine damage detected ({engine_damage}%)"
                    )
                elif key == "gbx_dmg":
                    msg = (
                        f"Gearbox damage critical ({gearbox_damage}%)"
                        if cur["level"] == "crit"
                        else f"Gearbox damage detected ({gearbox_damage}%)"
                    )
                elif key == "fuel":
                    msg = (
                        f"Fuel critical \u2014 {fuel_delta_laps:+.1f} laps vs plan"
                        if cur["level"] == "crit"
                        else f"Fuel short \u2014 {fuel_delta_laps:+.1f} laps vs plan"
                    )
                elif key == "fuel_lap":
                    msg = (
                        f"Fuel critical \u2014 cannot finish lap"
                        f" ({fuel_in_tank:.2f} kg in tank, {fuel_needed:.2f} kg needed)"
                        if cur["level"] == "crit"
                        else f"Fuel low \u2014 cannot complete next lap"
                        f" ({fuel_in_tank:.2f} kg in tank, {fuel_needed:.2f} kg needed)"
                    )
                elif key == "battery":
                    msg = (
                        f"Battery SOC critically low at {battery_pct}%"
                        if cur["level"] == "crit"
                        else f"Battery SOC low at {battery_pct}%"
                    )
                else:
                    continue

                new_alerts.append({"level": alert_level, "message": msg, "time": f"{ts} {defn['tag']}"})
            elif prev is not None:
                # Keep the previous alerted value as baseline
                cur["value"] = prev["value"]

        # Detect fully cleared conditions
        for key in self.conditions:
            if key not in current_conditions:
                defn = PU_ALERT_DEFS.get(key)
                if defn:
                    new_alerts.append({"level": "info", "message": defn["clearMsg"], "time": f"{ts} {defn['tag']}"})

        # ERS deploy mode change
        ers_mode = snapshot.get("ersDeployMode", "")
        if ers_mode and ers_mode != self.prev_ers_mode:
            if self.prev_ers_mode:
                new_alerts.append({
                    "level": "info",
                    "message": f"ERS mode \u2192 {ers_mode.upper()}",
                    "time": f"{ts} ERS",
                })
            self.prev_ers_mode = ers_mode

        # Fuel mix change
        fuel_mix = snapshot.get("fuelMix", "")
        if fuel_mix and fuel_mix != self.prev_fuel_mix:
            if self.prev_fuel_mix:
                new_alerts.append({
                    "level": "info",
                    "message": f"Fuel mix \u2192 {fuel_mix.upper()}",
                    "time": f"{ts} FUEL",
                })
            self.prev_fuel_mix = fuel_mix

        self.conditions = current_conditions
        self.alerts_log.extend(new_alerts)
        return new_alerts
