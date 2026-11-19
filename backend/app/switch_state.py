"""Short-lived in-memory notice for the most recent room switch.

A switch is operational news: the display should keep showing "KLH101
switched to KLH102" for a while so anyone walking past still sees it, and a
display that reconnects during that window must still get the banner. The
notice therefore lives in memory and is included in every socket snapshot.
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta

from .serializers import iso

SWITCH_NOTICE_TTL_SEC = 90


class SwitchNoticeStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._notice: dict | None = None

    def set(
        self,
        *,
        session_id: int,
        from_room: str,
        to_room: str,
        at: datetime | None = None,
    ) -> dict:
        at = (at or datetime.now()).replace(microsecond=0)
        notice = {
            "session_id": session_id,
            "from_room": from_room,
            "to_room": to_room,
            "text": f"{from_room} switched to {to_room}",
            "speech": f"{from_room} changed to {to_room}.",
            "at": iso(at),
            "expires_at": iso(at + timedelta(seconds=SWITCH_NOTICE_TTL_SEC)),
        }
        with self._lock:
            self._notice = notice
        return notice

    def current(self, at: datetime | None = None) -> dict | None:
        """Return the notice while it is still fresh, otherwise None."""
        at = at or datetime.now()
        with self._lock:
            notice = self._notice
        if notice is None:
            return None
        if at >= datetime.fromisoformat(notice["expires_at"]):
            return None
        return notice

    def clear(self) -> None:
        with self._lock:
            self._notice = None


switch_notices = SwitchNoticeStore()
