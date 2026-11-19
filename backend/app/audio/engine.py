"""Pure, clock-injectable audio scheduling state machine.

The engine never sleeps and never reads the database. Given an AudioConfig
and a list of in-progress room names it decides whether this poll is an
announcement cycle. This makes every edge case in the specification testable
with a fake clock.

Scheduling model
----------------
Cycles are fixed slots measured from the lecture start:
    slot = floor((now - lecture_start) / repeat_interval)
A slot is announced at most once. A slot is consumed even when the player is
busy (skip-if-busy) or there are no rooms (silent cycle), so a room that
appears mid-slot is announced on the next cycle rather than immediately.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import RLock
from typing import Protocol, Sequence

from ..rooms import sort_room_names
from ..settings_store import AudioConfig


class Player(Protocol):
    def play(self, text: str, rooms: Sequence[str]) -> None: ...
    def is_busy(self) -> bool: ...
    def stop(self) -> None: ...


@dataclass(frozen=True)
class Announcement:
    text: str
    rooms: tuple[str, ...]
    at: datetime
    slot: int
    duration_estimate: float


def compose_announcement(room_names: Sequence[str]) -> str:
    ordered = sort_room_names(room_names)
    return " ".join(f"{room} in progress." for room in ordered)


def _slot_for(cfg: AudioConfig) -> int:
    elapsed = (cfg.now - cfg.start).total_seconds()
    if elapsed < 0:
        return -1
    return int(elapsed // cfg.interval_sec)


class AudioEngine:
    def __init__(
        self,
        player: Player,
        seconds_per_room: float = 2.4,
        seconds_overhead: float = 1.0,
    ) -> None:
        self.player = player
        self.seconds_per_room = seconds_per_room
        self.seconds_overhead = seconds_overhead
        self._lock = RLock()
        self._last_slot: int | None = None
        self._busy_until: datetime | None = None
        self.last_announcement: Announcement | None = None
        self.skipped_cycles = 0

    # ------------------------------------------------------------- scheduling
    @property
    def last_slot(self) -> int | None:
        return self._last_slot

    def reset_schedule(self) -> None:
        with self._lock:
            self._last_slot = None

    def is_busy(self, at: datetime) -> bool:
        if self._busy_until is not None and at < self._busy_until:
            return True
        return bool(self.player.is_busy())

    def duration_estimate(self, room_count: int) -> float:
        return self.seconds_overhead + self.seconds_per_room * max(1, room_count)

    def tick(self, cfg: AudioConfig, room_names: Sequence[str]) -> Announcement | None:
        """Poll once. Returns the announcement if audio should play now."""
        with self._lock:
            slot = _slot_for(cfg)
            if slot < 0 or not cfg.is_open:
                return None
            if self._last_slot is not None and slot <= self._last_slot:
                return None

            # This cycle has arrived; consume it regardless of outcome.
            self._last_slot = slot

            if cfg.paused or not room_names:
                return None

            if self.is_busy(cfg.now):
                self.skipped_cycles += 1
                return None

            ordered = tuple(sort_room_names(room_names))
            text = compose_announcement(ordered)
            estimate = self.duration_estimate(len(ordered))
            self.player.play(text, ordered)
            self._busy_until = cfg.now + timedelta(seconds=estimate)
            announcement = Announcement(
                text=text,
                rooms=ordered,
                at=cfg.now,
                slot=slot,
                duration_estimate=estimate,
            )
            self.last_announcement = announcement
            return announcement

    def play_now(self, room_names: Sequence[str], at: datetime | None = None) -> Announcement | None:
        """Manual test announcement, bypassing the schedule but not overlap."""
        at = at or datetime.now()
        with self._lock:
            if not room_names or self.is_busy(at):
                return None
            ordered = tuple(sort_room_names(room_names))
            text = compose_announcement(ordered)
            estimate = self.duration_estimate(len(ordered))
            self.player.play(text, ordered)
            self._busy_until = at + timedelta(seconds=estimate)
            announcement = Announcement(text=text, rooms=ordered, at=at, slot=-1, duration_estimate=estimate)
            self.last_announcement = announcement
            return announcement

    def play_text_now(
        self,
        text: str,
        rooms: Sequence[str] = (),
        at: datetime | None = None,
    ) -> Announcement | None:
        """Speak custom operational text now (for example a room switch).

        This bypasses the schedule and the announcement window but still
        respects overlap: it returns None while audio is busy so the caller can
        complete the action without speaking.
        """
        at = at or datetime.now()
        text = (text or "").strip()
        if not text:
            return None
        with self._lock:
            if self.is_busy(at):
                return None
            ordered = tuple(sort_room_names(rooms))
            estimate = max(
                self.duration_estimate(len(ordered)),
                self.seconds_overhead + 0.4 * len(text.split()),
            )
            self.player.play(text, ordered)
            self._busy_until = at + timedelta(seconds=estimate)
            announcement = Announcement(
                text=text,
                rooms=ordered,
                at=at,
                slot=-1,
                duration_estimate=estimate,
            )
            self.last_announcement = announcement
            return announcement

    # ---------------------------------------------------------------- reading
    def describe(self, cfg: AudioConfig) -> dict:
        with self._lock:
            slot = _slot_for(cfg)
            if cfg.paused:
                state, reason = "PAUSED", "PAUSED"
            elif cfg.now < cfg.start:
                state, reason = "SILENT", "BEFORE_WINDOW"
            elif cfg.now >= cfg.end:
                state, reason = "SILENT", "WINDOW_CLOSED"
            else:
                state, reason = "ACTIVE", "ACTIVE"

            next_cycle_at: datetime | None = None
            if state == "ACTIVE":
                next_slot = max(slot + 1, 0)
                next_cycle_at = cfg.start + timedelta(seconds=next_slot * cfg.interval_sec)
                if next_cycle_at > cfg.end:
                    next_cycle_at = cfg.end

            last = self.last_announcement
            return {
                "state": state,
                "reason": reason,
                "current_slot": slot,
                "next_cycle_at": next_cycle_at,
                "is_playing": self.is_busy(cfg.now),
                "skipped_cycles": self.skipped_cycles,
                "last_announcement_at": last.at if last else None,
                "last_announcement_text": last.text if last else None,
            }
