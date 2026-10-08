"""Build synthetic UDP packets from the decoder layout, for tests.

Values are supplied as keyword arguments. Scalar fields use the field name;
array fields use "segmentName[index].fieldName".
"""

import struct

from common.f1_decoder.packet_layout import PACKET_LAYOUTS
from common.f1_decoder.packet_layout import PACKET_LAYOUTS_2026
from common.f1_decoder.struct_parser import StructParser


def layouts_for(packet_format: int) -> dict:
    """Return the layout table for a packet format."""
    if packet_format == 2026:
        return PACKET_LAYOUTS_2026
    if packet_format == 2025:
        return PACKET_LAYOUTS
    raise ValueError(f"unsupported packet format: {packet_format}")


def layout_size(layout: list) -> int:
    """Total wire size in bytes of a layout."""
    total = 0
    for segment in layout:
        total += StructParser(segment.fields).size * segment.count
    return total


def _field_offsets(fields: dict) -> tuple[dict, int]:
    """Map field name -> (byte offset, struct format) within one struct."""
    offsets = {}
    offset = 0
    for name, fmt in fields.items():
        offsets[name] = (offset, fmt)
        offset += StructParser({name: fmt}).size
    return offsets, offset


def _pack(buf: bytearray, offset: int, fmt: str, value) -> None:
    """Pack a scalar or a list into a fixed-width field."""
    if isinstance(value, (list, tuple)):
        struct.pack_into("<" + fmt, buf, offset, *value)
    else:
        struct.pack_into("<" + fmt, buf, offset, value)


def _layout_plan(layout: list) -> tuple[list, int]:
    """Return (segment, offsets, size, base) tuples plus the total packet size."""
    plan = []
    total = 0
    for segment in layout:
        offsets, size = _field_offsets(segment.fields)
        plan.append((segment, offsets, size, total))
        total += size * segment.count
    return plan, total


def _apply_values(buf: bytearray, plan: list, values: dict) -> None:
    """Write each requested value at its wire offset within the buffer."""
    for segment, offsets, size, base in plan:
        for key, value in values.items():
            if segment.count == 1:
                if key in offsets:
                    offset, fmt = offsets[key]
                    _pack(buf, base + offset, fmt, value)
            elif key.startswith(segment.name + "[") and "]." in key:
                index_text, field = key[len(segment.name) + 1:].split("].", 1)
                if field in offsets:
                    offset, fmt = offsets[field]
                    _pack(buf, base + int(index_text) * size + offset, fmt, value)


def build_packet(packet_format: int, packet_id: int, **values) -> bytes:
    """Build a zero-filled packet of the correct size with values applied."""
    plan, total = _layout_plan(layouts_for(packet_format)[packet_id])
    buf = bytearray(total)
    _apply_values(buf, plan, values)
    return bytes(buf)
