"""Typed access to the key/value settings table."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .extensions import db
from .models import Setting

DEFAULTS: dict[str, str] = {
    "lecture_start": "07:00",
    "lecture_duration_min": "180",
    "audio_window_min": "30",
    "repeat_interval_sec": "300",
    "audio_extended_until": "",
    "audio_paused": "0",
}

EDITABLE_BY_ADMIN = {"lecture_start", "lecture_duration_min", "audio_window_min", "repeat_interval_sec"}
EDITABLE_BY_OFFICER = {"repeat_interval_sec"}


@dataclass(frozen=True)
class AudioConfig:
    now: datetime
    start: datetime
    base_end: datetime
    end: datetime
    lecture_end: datetime
    interval_sec: int
    window_min: int
    paused: bool
    extended: bool

    @property
    def is_open(self) -> bool:
        return self.start <= self.now < self.end


def ensure_defaults() -> None:
    changed = False
    existing = {row.key for row in Setting.query.all()}
    for key, value in DEFAULTS.items():
        if key not in existing:
            db.session.add(Setting(key=key, value=value))
            changed = True
    if changed:
        db.session.commit()


def get_all_settings() -> dict[str, str]:
    values = dict(DEFAULTS)
    for row in Setting.query.all():
        values[row.key] = row.value
    return values


def get_int(key: str, fallback: int) -> int:
    try:
        return int(get_all_settings().get(key, fallback))
    except (TypeError, ValueError):
        return fallback


def set_setting(key: str, value: str, officer_id: int | None = None) -> None:
    row = db.session.get(Setting, key)
    if row is None:
        row = Setting(key=key, value=str(value), updated_by=officer_id)
        db.session.add(row)
    else:
        row.value = str(value)
        row.updated_by = officer_id
        row.updated_at = datetime.now().replace(microsecond=0)


def _parse_time_of_day(value: str) -> tuple[int, int]:
    try:
        hours, minutes = value.split(":")[:2]
        h, m = int(hours), int(minutes)
        if 0 <= h <= 23 and 0 <= m <= 59:
            return h, m
    except (AttributeError, ValueError):
        pass
    return 7, 0


def _parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.replace(microsecond=0)
    except ValueError:
        return None


def build_audio_config(at: datetime | None = None) -> AudioConfig:
    values = get_all_settings()
    at = (at or datetime.now()).replace(microsecond=0)

    hours, minutes = _parse_time_of_day(values.get("lecture_start", "07:00"))
    start = at.replace(hour=hours, minute=minutes, second=0, microsecond=0)

    window_min = max(1, _coerce_int(values.get("audio_window_min"), 30))
    duration_min = max(1, _coerce_int(values.get("lecture_duration_min"), 180))
    interval_sec = max(30, _coerce_int(values.get("repeat_interval_sec"), 300))

    base_end = start + timedelta(minutes=window_min)
    extended_until = _parse_iso(values.get("audio_extended_until", ""))
    end = base_end
    if extended_until and extended_until > base_end:
        end = extended_until

    return AudioConfig(
        now=at,
        start=start,
        base_end=base_end,
        end=end,
        lecture_end=start + timedelta(minutes=duration_min),
        interval_sec=interval_sec,
        window_min=window_min,
        paused=values.get("audio_paused", "0") in {"1", "true", "yes", "on"},
        extended=end > base_end,
    )


def _coerce_int(value: str | None, fallback: int) -> int:
    try:
        return int(value) if value is not None else fallback
    except (TypeError, ValueError):
        return fallback


def extend_window(minutes: int = 15, at: datetime | None = None) -> datetime:
    """Extend from the later of now and the current window end."""
    at = (at or datetime.now()).replace(microsecond=0)
    cfg = build_audio_config(at)
    new_end = max(cfg.end, at) + timedelta(minutes=minutes)
    set_setting("audio_extended_until", new_end.isoformat(timespec="seconds"))
    return new_end
