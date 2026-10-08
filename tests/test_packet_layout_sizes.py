"""Every packet layout must match the size declared by the official spec.

Sizes come from tests/f1_spec_sizes.py, transcribed from the Codemasters/EA
documents, so these tests fail if a layout drifts from the wire format.
"""

import struct

import pytest
from f1_packet_builder import build_packet
from f1_packet_builder import layout_size
from f1_packet_builder import layouts_for
from f1_spec_sizes import SPEC_PACKET_SIZES
from f1_spec_sizes import UNION_PAYLOAD_PACKETS

from common.f1_decoder.packet_decoder import PacketDecoder

CASES = [
    (packet_format, packet_id, size)
    for packet_format, sizes in SPEC_PACKET_SIZES.items()
    for packet_id, size in sizes.items()
    if packet_id not in UNION_PAYLOAD_PACKETS
]


@pytest.mark.parametrize("packet_format,packet_id,expected_size", CASES)
def test_layout_size_matches_spec(packet_format, packet_id, expected_size):
    """The layout consumes exactly the number of bytes the spec declares."""
    layout = layouts_for(packet_format)[packet_id]
    assert layout_size(layout) == expected_size


@pytest.mark.parametrize("packet_format,packet_id,expected_size", CASES)
def test_decodes_a_buffer_of_declared_size(packet_format, packet_id, expected_size):
    """A datagram of the declared size decodes, and routing fields survive."""
    packet = build_packet(
        packet_format,
        packet_id,
        m_packetFormat=packet_format,
        m_packetId=packet_id,
    )
    assert len(packet) == expected_size

    decoded = PacketDecoder().decode(packet)
    assert decoded["m_packetFormat"] == packet_format
    assert decoded["m_packetId"] == packet_id


@pytest.mark.parametrize("packet_format,packet_id,expected_size", CASES)
def test_one_byte_short_raises(packet_format, packet_id, expected_size):
    """Proves the layout needs the declared size, not fewer bytes."""
    packet = build_packet(
        packet_format,
        packet_id,
        m_packetFormat=packet_format,
        m_packetId=packet_id,
    )
    with pytest.raises(struct.error):
        PacketDecoder().decode(packet[: expected_size - 1])


@pytest.mark.parametrize("packet_format,expected_size", [(2025, 45), (2026, 45)])
def test_event_packet_decodes_from_its_declared_size(packet_format, expected_size):
    """Event reads only its event code, from a datagram of the declared size."""
    datagram = bytearray(expected_size)
    built = build_packet(packet_format, 3, m_packetFormat=packet_format, m_packetId=3)
    datagram[: len(built)] = built

    decoded = PacketDecoder().decode(bytes(datagram))

    assert decoded["m_packetId"] == 3
    assert decoded["m_packetFormat"] == packet_format
