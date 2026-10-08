"""
Async UDP listener for F1 25 telemetry packets on port 20777.

Receives raw datagrams and pushes them to an asyncio.Queue for consumption
by CaptureSession or any other consumer.

Usage:
    listener = UdpListener(port=20777)
    await listener.start()
    while True:
        datagram = await listener.queue.get()
        ...
    listener.stop()
"""

import asyncio
import struct

from common.f1_decoder.frame_gate import FrameGate
from common.f1_decoder.packet_decoder import PacketDecoder


class _UdpProtocol(asyncio.DatagramProtocol):
    """Internal protocol that pushes received datagrams to a queue."""

    def __init__(self, queue: asyncio.Queue, gate: FrameGate, decoder: PacketDecoder):
        self._queue = queue
        self._gate = gate
        self._decoder = decoder

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        """Called by asyncio when a UDP datagram arrives."""
        if not self._is_live(data):
            return
        try:
            self._queue.put_nowait(data)
        except asyncio.QueueFull:
            pass  # Drop packet when consumer can't keep up

    def _is_live(self, data: bytes) -> bool:
        """Return False for a stale or duplicated frame.

        A datagram too short to hold a header cannot be judged, so it is passed
        on for the consumer to handle.
        """
        try:
            header = self._decoder.decode_header(data)
        except struct.error:
            return True

        if self._gate.accept(header):
            return True

        if self._gate.stale_dropped == 1:
            print("[UdpListener] dropping stale/duplicate telemetry frames")
        return False

    def error_received(self, exc: Exception) -> None:
        """Called by asyncio on transport error."""
        print(f"[UdpListener] error: {exc}")


class UdpListener:
    """Listens for F1 25 UDP telemetry on the given port."""

    def __init__(self, port: int = 20777, queue_size: int = 16384):
        """Initialize the listener.

        Args:
            port: UDP port to bind to (F1 25 default is 20777).
            queue_size: Max queued datagrams before dropping.
        """
        self._port = port
        self.queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=queue_size)
        self._transport = None
        self._gate = FrameGate()
        self._decoder = PacketDecoder()

    @property
    def port(self) -> int:
        """The bound UDP port, or the configured port before start()."""
        if self._transport is None:
            return self._port
        return self._transport.get_extra_info("sockname")[1]

    async def start(self) -> None:
        """Bind the UDP socket and start receiving."""
        loop = asyncio.get_running_loop()
        self._transport, _ = await loop.create_datagram_endpoint(
            lambda: _UdpProtocol(self.queue, self._gate, self._decoder),
            local_addr=("0.0.0.0", self._port),
        )
        print(f"[UdpListener] listening on UDP port {self._port}")

    def stop(self) -> None:
        """Close the UDP socket."""
        if self._transport is not None:
            self._transport.close()
            self._transport = None
            print("[UdpListener] stopped")
