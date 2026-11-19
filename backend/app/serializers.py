"""JSON shapes shared by REST and SocketIO responses."""
from __future__ import annotations

from datetime import datetime

from .models import LectureSession, Officer, Room
from .rooms import parse_room_number


def iso(value: datetime | None) -> str | None:
    return value.isoformat(timespec="seconds") if value else None


def officer_public(officer: Officer) -> dict:
    return {
        "id": officer.id,
        "name": officer.name,
        "username": officer.username,
        "role": officer.role,
        "active": officer.active,
        "created_at": iso(officer.created_at),
    }


def session_public(session: LectureSession, at: datetime | None = None) -> dict:
    """Public payload. Deliberately contains no officer or staff identifiers."""
    at = at or datetime.now()
    elapsed = max(0, int((at - session.started_at).total_seconds())) if session.started_at else 0
    return {
        "id": session.id,
        "room_name": session.room_name,
        "room_number": session.room_number,
        "lecturer_name": session.lecturer_name or None,
        "status": session.status,
        "started_at": iso(session.started_at),
        "ended_at": iso(session.ended_at),
        "elapsed_seconds": elapsed,
    }


def room_public(room: Room) -> dict:
    return {
        "id": room.id,
        "room_name": room.room_name,
        "room_number": room.room_number,
        "building": room.building,
        "active": room.active,
    }


def settings_public() -> dict:
    """Typed settings for the console and admin forms."""
    from .settings_store import get_all_settings

    raw = get_all_settings()

    def _int(key: str, fallback: int) -> int:
        try:
            return int(raw.get(key, fallback))
        except (TypeError, ValueError):
            return fallback

    return {
        "lecture_start": raw.get("lecture_start", "07:00"),
        "lecture_duration_min": _int("lecture_duration_min", 180),
        "audio_window_min": _int("audio_window_min", 30),
        "repeat_interval_sec": _int("repeat_interval_sec", 300),
        "audio_paused": raw.get("audio_paused", "0") in {"1", "true", "yes", "on"},
        "audio_extended_until": raw.get("audio_extended_until") or "",
    }


def parsed_room_number(room_name: str) -> int:
    return parse_room_number(room_name)
