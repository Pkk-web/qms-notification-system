"""Monotonic revision counter used by the real-time protocol."""
from __future__ import annotations

import threading


class RevisionStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._value = 0

    def bump(self) -> int:
        with self._lock:
            self._value += 1
            return self._value

    def current(self) -> int:
        with self._lock:
            return self._value

    def reset(self) -> None:
        with self._lock:
            self._value = 0


revisions = RevisionStore()
