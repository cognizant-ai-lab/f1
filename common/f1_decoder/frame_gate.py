"""Drops telemetry frames that arrive stale or duplicated.

UDP makes no ordering or exactly-once guarantees. When the same game stream
reaches the server twice, for example a delayed copy arriving over a second
network path, the older copy rewinds m_sessionTime. The alert processors read a
backwards session clock as a new session: they clear their state and re-fire
every active condition, so one braking event turned into a storm of repeated
alerts.

m_overallFrameIdentifier is monotonic for a session and is shared by every
packet of a frame. Unlike m_sessionTime it does not go backwards on a flashback,
so a frame whose overall id is older than the newest accepted frame is a
duplicate and can be dropped without disturbing the live stream.
"""


# A frame gate has exactly one operation: decide whether to accept a frame.
# pylint: disable=too-few-public-methods
class FrameGate:
    """Accepts the newest telemetry frame and rejects stale duplicates."""

    def __init__(self, max_consecutive_rejections: int = 60) -> None:
        """Initialise the gate.

        Args:
            max_consecutive_rejections: Re-baseline after this many consecutive
                rejections. If the live source stops and only a delayed copy
                keeps arriving, the gate adopts that stream instead of blocking
                telemetry forever, so a wrong assumption cannot stall the server.
        """
        self.max_consecutive_rejections: int = max_consecutive_rejections
        self.stale_dropped: int = 0

        self._session_uid = None
        self._newest_overall_frame = None
        self._consecutive_rejections: int = 0

    def accept(self, header: dict) -> bool:
        """Return True when the frame belongs to the live stream.

        Args:
            header: A decoded packet header.

        Returns:
            True to process the frame, False if it is a stale duplicate.
        """
        overall = header.get("m_overallFrameIdentifier")
        if overall is None:
            # Without a frame id, staleness cannot be judged: pass it through.
            return True

        session_uid = header.get("m_sessionUID")
        if session_uid != self._session_uid:
            # A new session may restart the frame counter from any value.
            self._session_uid = session_uid
            self._newest_overall_frame = overall
            self._consecutive_rejections = 0
            return True

        if self._newest_overall_frame is None or overall >= self._newest_overall_frame:
            # Same frame as other packets of this frame, or the next frame.
            self._newest_overall_frame = overall
            self._consecutive_rejections = 0
            return True

        self._consecutive_rejections += 1
        if self._consecutive_rejections > self.max_consecutive_rejections:
            self._newest_overall_frame = overall
            self._consecutive_rejections = 0
            return True

        self.stale_dropped += 1
        return False
