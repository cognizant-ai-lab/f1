"""WebSocket bridge that streams live F1 25 telemetry from UDP to the
race_engineer_hub web app.

Usage:
    python -m telemetry_server

Listens on UDP 20777 for F1 25 telemetry packets (decoded via
``common.f1_decoder.PacketDecoder``) and exposes a WebSocket server on
port 8765.  The web app connects to ws://localhost:8765 and receives
JSON frames with the latest telemetry state.
"""

import argparse
import asyncio
import os

from dotenv import load_dotenv

from common.f1_structs.f1_constants import MAX_NUM_CARS
from telemetry_server.alerts.aero_alert_processor import AeroAlertProcessor
from telemetry_server.alerts.pit_alert_processor import PitAlertProcessor
from telemetry_server.alerts.pu_alert_processor import PuAlertProcessor
from telemetry_server.alerts.tyre_alert_processor import TyreAlertProcessor
from telemetry_server.dispatch.agent_dispatch_manager import AgentDispatchManager
from telemetry_server.server.message_builder import MessageBuilder
from telemetry_server.server.telemetry_input import TelemetryInput
from telemetry_server.server.websocket_server import WebSocketServer
from telemetry_server.telemetry_state_adapter import TelemetryStateAdapter
from telemetry_server.timing_processor import TimingProcessor
from telemetry_server.track_location_provider import TrackLocationProvider

WS_HOST = "0.0.0.0"
WS_PORT = 8765


class TelemetryServer:
    """Composition root that wires all telemetry components together.

    Owns the shared packet state, adapter, alert processors, dispatch
    manager, message builder, WebSocket server, and telemetry input.
    """

    def __init__(self) -> None:
        """Wire all components via dependency injection."""
        self.state: dict[int, dict] = {}
        self.session_histories: dict[int, dict] = {}
        self.adapter: TelemetryStateAdapter = self._create_adapter(self.state)
        self.session_time: float = 0.0

        # Timing processor
        self.timing_processor = TimingProcessor()

        # Track location provider (for enriching alerts with corner/sector info)
        self.track_location = TrackLocationProvider()

        # Alert processors
        self.aero_processor = AeroAlertProcessor()
        self.tyre_processor = TyreAlertProcessor()
        self.pu_processor = PuAlertProcessor()
        self.pit_processor = PitAlertProcessor()

        # Agent dispatch manager
        self.dispatch_manager = AgentDispatchManager(
            session_time_fn=lambda: self.session_time,
            alert_logs={
                "aero": self.aero_processor.alerts_log,
                "tyre": self.tyre_processor.alerts_log,
                "pu": self.pu_processor.alerts_log,
            },
        )

        # Message builder
        self.message_builder = MessageBuilder(
            adapter_fn=lambda: self.adapter,
            aero_processor=self.aero_processor,
            tyre_processor=self.tyre_processor,
            pu_processor=self.pu_processor,
            pit_processor=self.pit_processor,
            dispatch_manager=self.dispatch_manager,
            session_time_fn=lambda: self.session_time,
            state_ready_fn=self._state_ready,
            track_location=self.track_location,
            timing_processor=self.timing_processor,
            state_fn=lambda: self.state,
            session_histories_fn=lambda: self.session_histories,
        )

        # WebSocket server
        self.websocket_server = WebSocketServer(
            host=WS_HOST,
            port=WS_PORT,
            message_builder=self.message_builder,
            dispatch_manager=self.dispatch_manager,
        )

        # Telemetry input (UDP / replay)
        self.telemetry_input = TelemetryInput(server=self)

    def store_packet(self, packet_id: int, decoded: dict) -> None:
        """Store a decoded packet, accumulating per-car session histories for packet 11.

        Args:
            packet_id: The F1 packet ID.
            decoded: The decoded packet dict.
        """
        if packet_id == 12:
            car_idx = decoded.get("m_carIdx", -1)
            player_idx = decoded.get("m_playerCarIndex", 0)
            if car_idx != player_idx:
                return
        self.state[packet_id] = decoded
        if packet_id == 11:
            car_idx = decoded.get("m_carIdx", -1)
            if 0 <= car_idx < MAX_NUM_CARS:
                self.session_histories[car_idx] = decoded

    @staticmethod
    def _create_adapter(state: dict[int, dict]) -> TelemetryStateAdapter:
        """Create a new TelemetryStateAdapter for the given state dict."""
        return TelemetryStateAdapter(state)

    def _state_ready(self) -> bool:
        """Return True once essential packets (6, 7, 10) have been received."""
        return 6 in self.state and 7 in self.state and 10 in self.state

    async def run(self, args: argparse.Namespace) -> None:
        """Start the WebSocket server and the telemetry input source."""
        self.agents_enabled = not args.no_agents
        os.environ.setdefault("AGENT_MANIFEST_FILE", "registries/manifest.hocon")
        if self.agents_enabled:
            self.dispatch_manager.init_agents()
        else:
            print("Agents disabled — running in telemetry-only mode")

        print(f"Starting WebSocket server on ws://{WS_HOST}:{WS_PORT}")
        async with self.websocket_server.serve():
            if args.replay:
                speed_str = args.speed.rstrip("x")
                try:
                    speed = float(speed_str)
                except ValueError as exc:
                    raise SystemExit(f"invalid --speed value: {args.speed} (expected Nx, e.g. 2x, 10x)") from exc
                max_gap = None if args.keep_pauses else 0.5
                await self.telemetry_input.f1bin_replay(args.replay, speed, max_gap=max_gap)
            else:
                await self.telemetry_input.udp_reader(args.capture)


async def main() -> None:
    """Parse CLI arguments and start the telemetry server."""
    load_dotenv()

    parser = argparse.ArgumentParser(description="F1 25 telemetry WebSocket bridge")
    parser.add_argument(
        "--capture",
        action="store_true",
        help="Save telemetry to .f1bin files in the data/ folder (one file per session)",
    )
    parser.add_argument(
        "--replay",
        metavar="FILE",
        help="Replay a captured .f1bin file instead of listening for live UDP",
    )
    parser.add_argument(
        "--speed",
        metavar="Nx",
        default="1x",
        help="Replay speed multiplier, e.g. 2x, 10x (default: 1x)",
    )
    parser.add_argument(
        "--keep-pauses",
        action="store_true",
        help="Preserve original game pauses during replay (by default pauses are skipped)",
    )
    parser.add_argument(
        "--no-agents",
        action="store_true",
        help="Disable AI agent initialization — stream telemetry only",
    )
    args = parser.parse_args()

    if args.capture and args.replay:
        parser.error("--capture and --replay cannot be used together")

    if args.speed != "1x" and not args.replay:
        parser.error("--speed can only be used with --replay")

    server = TelemetryServer()
    await server.run(args)


if __name__ == "__main__":
    asyncio.run(main())
