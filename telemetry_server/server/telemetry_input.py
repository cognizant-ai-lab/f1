"""Telemetry input sources — live UDP and .f1bin replay."""

from __future__ import annotations

import asyncio
import struct
from pathlib import Path
from typing import TYPE_CHECKING

from common.f1_capture.capture_session import CaptureSession
from common.f1_capture.replay_session import ReplaySession
from common.f1_capture.udp_listener import UdpListener
from common.f1_decoder.packet_decoder import PacketDecoder
from common.f1_decoder.packet_decoder import UnsupportedPacketFormatError
from common.f1_structs.f1_constants import MAX_NUM_CARS

if TYPE_CHECKING:
    from telemetry_server.telemetry_server import TelemetryServer


class TelemetryInput:
    """Reads telemetry data from either live UDP or a .f1bin replay file.

    On each telemetry frame (packet 6), builds the JSON message, broadcasts
    to WebSocket clients, and dispatches new alerts to specialist agents.
    """

    UDP_PORT = 20777

    def __init__(self, server: TelemetryServer) -> None:
        """Initialise the telemetry input.

        Args:
            server: The parent TelemetryServer that owns shared state.
        """
        self._server = server
        self._prev_session_uid: int = 0

    async def udp_reader(self, capture: bool) -> None:
        """Read F1 25 UDP packets and update shared state, broadcasting on each telemetry frame (packet 6)."""
        server = self._server
        listener = UdpListener(port=self.UDP_PORT)
        decoder = PacketDecoder()

        capture_session = None
        if capture:
            Path("data").mkdir(exist_ok=True)
            capture_session = CaptureSession(
                hz=10, port=self.UDP_PORT, output_dir=Path("data"), state=server.state,
            )

        await listener.start()
        try:
            while True:
                datagram = await listener.queue.get()
                try:
                    packet_id = decoder.decode_header(datagram)["m_packetId"]
                    decoded = decoder.decode(datagram)
                except (struct.error, KeyError, UnsupportedPacketFormatError) as exc:
                    # UDP input is untrusted: one malformed or unknown packet
                    # must not tear down the whole telemetry stream.
                    print(f"[UdpListener] dropping undecodable {len(datagram)}-byte packet: {exc}")
                    continue
                server.store_packet(packet_id, decoded)

                if capture_session:
                    capture_session.process(datagram, decode=False)

                server.session_time = server.adapter.session_time

                # Detect new session
                uid = server.adapter.session_uid
                if packet_id == 1 and uid != self._prev_session_uid:
                    self._prev_session_uid = uid
                    server.session_histories = {}
                    server.track_location.set_track(server.adapter.get_track_id())
                    context = server.adapter.get_session_context()
                    if server.agents_enabled:
                        print(f"New session detected \u2014 re-initializing agents\n{context}")
                        await asyncio.to_thread(server.dispatch_manager.reinit_agents, context)
                    else:
                        print(f"New session detected\n{context}")

                # Trigger on Car Telemetry (packet 6)
                if packet_id == 6:
                    msg, new_aero, new_tyre, new_pu = server.message_builder.build()
                    await server.websocket_server.broadcast(msg)
                    server.dispatch_manager.dispatch_alerts(new_aero, new_tyre, new_pu)
        finally:
            listener.stop()
            if capture_session:
                capture_session.close()

    async def f1bin_replay(self, filepath: str, speed: float, max_gap: float | None = 0.5) -> None:
        """Replay a captured .f1bin file as if it were live telemetry."""
        server = self._server

        path = Path(filepath)
        if not path.exists():
            print(f"ERROR: file not found: {filepath}")
            return

        print(f"Replaying {filepath} ({speed}x) ...")

        session = ReplaySession(path, speed=speed, max_gap=max_gap)
        # Share the replay's state dict with the adapter
        server.state = session.state
        server.adapter = server._create_adapter(server.state)

        replay_task = asyncio.create_task(session.run())

        prev_count = 0
        try:
            while not replay_task.done():
                await asyncio.sleep(1 / 60)
                if session.packets_received == prev_count:
                    continue
                prev_count = session.packets_received
                server.session_time = server.adapter.session_time

                # Accumulate per-car session histories from replay state
                pkt11 = server.state.get(11)
                if pkt11:
                    car_idx = pkt11.get("m_carIdx", -1)
                    if 0 <= car_idx < MAX_NUM_CARS:
                        server.session_histories[car_idx] = pkt11

                # Detect new session
                uid = server.adapter.session_uid
                if uid and uid != self._prev_session_uid:
                    self._prev_session_uid = uid
                    server.session_histories = {}
                    server.track_location.set_track(server.adapter.get_track_id())
                    context = server.adapter.get_session_context()
                    if server.agents_enabled:
                        print(f"New session detected in replay \u2014 re-initializing agents\n{context}")
                        await asyncio.to_thread(server.dispatch_manager.reinit_agents, context)
                    else:
                        print(f"New session detected in replay\n{context}")

                msg, new_aero, new_tyre, new_pu = server.message_builder.build()
                await server.websocket_server.broadcast(msg)
                server.dispatch_manager.dispatch_alerts(new_aero, new_tyre, new_pu)
        finally:
            session.stop()
            await replay_task

        print(f"Replay complete \u2014 {session.packets_received} packets sent.")
