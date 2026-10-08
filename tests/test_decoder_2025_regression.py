"""Real captured F1 25 (format 2025) packets still decode unchanged.

tests/fixtures/real_2025_packets.f1bin holds one genuine datagram per packet
type, taken from a recorded Catalunya race capture.
"""

from pathlib import Path

from common.f1_capture.binary_reader import BinaryReader
from common.f1_decoder.packet_decoder import PacketDecoder

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "real_2025_packets.f1bin"


def test_real_2025_capture_decodes():
    """Every packet in the recorded 2025 capture decodes as format 2025."""
    decoder = PacketDecoder()
    packet_ids = []

    for _, datagram in BinaryReader(FIXTURE):
        decoded = decoder.decode(datagram)
        assert decoded["m_packetFormat"] == 2025
        packet_ids.append(decoded["m_packetId"])

    assert sorted(packet_ids) == [0, 1, 2, 3, 4, 5, 6, 7, 10, 11, 12, 13, 15]
