"""Engine power is reported in kilowatts, matching the dashboard gauge.

The UDP spec defines m_enginePowerICE and m_enginePowerMGUK in watts. The
WebSocket payload exposes icePowerKW / mgukPowerKW, and the dashboard converts
those to brake horsepower for a gauge scaled to 1000 bhp, so the adapter must
convert watts to kilowatts.
"""

import pytest
from f1_packet_builder import build_packet

from common.f1_decoder.packet_decoder import PacketDecoder
from telemetry_server.telemetry_state_adapter import TelemetryStateAdapter

# Realistic values in watts, as the game sends them.
ICE_WATTS = 602620.0
MGUK_WATTS = 166572.0

# The dashboard renders icePowerKW * 1.341 on a gauge scaled to 1000 bhp.
BHP_PER_KW = 1.341
GAUGE_MAX_BHP = 1000


def _adapter() -> TelemetryStateAdapter:
    """Build an adapter whose player car reports the given engine power."""
    decoder = PacketDecoder()
    header = {"m_packetFormat": 2025, "m_playerCarIndex": 0}
    state = {
        7: decoder.decode(build_packet(
            2025, 7, m_packetId=7, **header,
            **{
                "m_carStatusData[0].m_enginePowerICE": ICE_WATTS,
                "m_carStatusData[0].m_enginePowerMGUK": MGUK_WATTS,
            },
        )),
        6: decoder.decode(build_packet(2025, 6, m_packetId=6, **header)),
        10: decoder.decode(build_packet(2025, 10, m_packetId=10, **header)),
    }
    return TelemetryStateAdapter(state)


def test_ice_power_is_kilowatts_not_watts():
    """A watt reading must be exposed as kilowatts."""
    power_unit = _adapter().get_power_unit()

    assert power_unit["icePowerKW"] == pytest.approx(ICE_WATTS / 1000.0, abs=0.1)


def test_mguk_power_is_kilowatts_not_watts():
    """A watt reading must be exposed as kilowatts."""
    power_unit = _adapter().get_power_unit()

    assert power_unit["mgukPowerKW"] == pytest.approx(MGUK_WATTS / 1000.0, abs=0.1)


def test_ice_power_fits_the_dashboard_gauge():
    """The value the dashboard converts must stay within the gauge range."""
    ice_bhp = _adapter().get_power_unit()["icePowerKW"] * BHP_PER_KW

    assert 0 < ice_bhp < GAUGE_MAX_BHP
