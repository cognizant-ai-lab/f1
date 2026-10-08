"""The UDP listener drops a delayed duplicate of the telemetry stream.

An interleaved live stream and a copy of it that arrives late must yield only
the live frames, since the stale copy makes the alert processors re-fire.
"""

import asyncio
import socket

from f1_packet_builder import build_packet

from common.f1_capture.udp_listener import UdpListener
from common.f1_decoder.packet_decoder import PacketDecoder

UID = 7
_DECODER = PacketDecoder()
_PACKET6 = {
    "m_packetFormat": 2025,
    "m_packetId": 6,
    "m_playerCarIndex": 0,
}


def _frame(overall: int, session_time: float) -> bytes:
    """Build a Car Telemetry frame with a given overall frame id and time."""
    return build_packet(2025, 6, m_sessionUID=UID, m_overallFrameIdentifier=overall,
                        m_sessionTime=session_time, **_PACKET6)


def _overall_id(datagram: bytes) -> int:
    """Read m_overallFrameIdentifier from a raw datagram header."""
    return _DECODER.decode_header(datagram)["m_overallFrameIdentifier"]


async def _send_and_collect() -> list:
    """Send a live stream interleaved with a delayed copy of it."""
    listener = UdpListener(port=0)
    await listener.start()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        for index in range(6):
            # Live frame, then the delayed copy of a much older frame.
            sock.sendto(_frame(5000 + index, 100.0 + index), ("127.0.0.1", listener.port))
            sock.sendto(_frame(4900 + index, 95.0 + index), ("127.0.0.1", listener.port))
            await asyncio.sleep(0.01)
        sock.close()
        await asyncio.sleep(0.2)

        received = []
        while not listener.queue.empty():
            received.append(listener.queue.get_nowait())
        return received
    finally:
        listener.stop()


def test_delayed_duplicate_stream_is_not_delivered():
    """Only the live frames reach the consumer."""
    received = asyncio.run(_send_and_collect())
    ids = {_overall_id(datagram) for datagram in received}

    assert {5000, 5001, 5002, 5003, 5004, 5005} & ids, "no live frame was delivered"
    assert ids.isdisjoint({4900, 4901, 4902, 4903, 4904, 4905}), f"delivered stale frames: {sorted(ids)}"
