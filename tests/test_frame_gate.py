"""FrameGate drops telemetry frames that arrive older than the newest seen.

When the same stream reaches the server twice (a delayed duplicate), the older
copy rewinds the session clock, which the alert processors treat as a new
session and re-fire every condition. m_overallFrameIdentifier is monotonic per
session and shared by every packet of a frame, so an older id marks a stale frame.
"""

from common.f1_decoder.frame_gate import FrameGate


def header(uid=1, overall=100, packet_id=6):
    """Build a decoded-packet header for a frame."""
    return {
        "m_sessionUID": uid,
        "m_overallFrameIdentifier": overall,
        "m_packetId": packet_id,
    }


def test_first_frame_is_accepted():
    """The gate must let the stream start."""
    gate = FrameGate()

    assert gate.accept(header()) is True


def test_other_packets_of_the_same_frame_are_accepted():
    """Every packet type in a frame shares one overall id."""
    gate = FrameGate()
    gate.accept(header(overall=100, packet_id=6))

    assert gate.accept(header(overall=100, packet_id=2)) is True
    assert gate.accept(header(overall=100, packet_id=7)) is True


def test_newer_frame_is_accepted():
    """Normal progress through the stream is always accepted."""
    gate = FrameGate()
    gate.accept(header(overall=100))

    assert gate.accept(header(overall=101)) is True
    assert gate.accept(header(overall=102)) is True


def test_delayed_duplicate_is_rejected():
    """A frame older than the newest seen is a stale duplicate."""
    gate = FrameGate()
    gate.accept(header(overall=500))

    assert gate.accept(header(overall=450)) is False
    assert gate.accept(header(overall=499)) is False


def test_gate_keeps_accepting_the_live_stream_after_a_duplicate():
    """Rejecting a duplicate must not disturb the live stream."""
    gate = FrameGate()
    gate.accept(header(overall=500))
    gate.accept(header(overall=450))

    assert gate.accept(header(overall=501)) is True
    assert gate.accept(header(overall=502)) is True


def test_new_session_rebaselines_the_gate():
    """A new session may restart the frame counter from a lower value."""
    gate = FrameGate()
    gate.accept(header(uid=1, overall=9000))

    assert gate.accept(header(uid=2, overall=10)) is True
    assert gate.accept(header(uid=2, overall=11)) is True


def test_missing_overall_id_is_accepted():
    """Without a frame id the gate cannot judge staleness, so it passes through."""
    gate = FrameGate()
    gate.accept(header(overall=100))

    assert gate.accept({"m_sessionUID": 1, "m_packetId": 6}) is True


def test_recovers_when_only_stale_frames_keep_arriving():
    """If the live stream stops, the gate re-baselines instead of stalling forever."""
    gate = FrameGate(max_consecutive_rejections=3)
    gate.accept(header(overall=5000))

    results = [gate.accept(header(overall=10)) for _ in range(3)]
    assert results == [False, False, False]

    assert gate.accept(header(overall=11)) is True
    assert gate.accept(header(overall=12)) is True


def test_counts_rejected_frames():
    """Rejections are counted so the server can report that it filtered a duplicate."""
    gate = FrameGate()
    gate.accept(header(overall=500))
    gate.accept(header(overall=400))
    gate.accept(header(overall=401))

    assert gate.stale_dropped == 2
