"""Read and update scheduling settings."""
from __future__ import annotations

import re

from flask import Blueprint, current_app, g, jsonify

from ..audio.service import build_audio_state, get_engine
from ..audit import log_action
from ..auth import error, login_required
from ..extensions import db
from ..realtime import notify_settings_changed
from ..realtime_state import revisions
from ..serializers import settings_public
from ..settings_store import EDITABLE_BY_ADMIN, EDITABLE_BY_OFFICER, set_setting
from .common import json_body

bp = Blueprint("settings_api", __name__, url_prefix="/api")

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
_SCHEDULE_KEYS = {"lecture_start", "audio_window_min", "repeat_interval_sec"}


def _validate_int(key: str, value, low: int, high: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{key} must be a whole number.")
    if number < low or number > high:
        raise ValueError(f"{key} must be between {low} and {high}.")
    return number


@bp.get("/settings")
@login_required
def get_settings():
    return jsonify({"settings": settings_public(), "audio_state": build_audio_state()})


@bp.patch("/settings")
@login_required
def update_settings():
    data = json_body()
    if not data:
        return error("No settings supplied.", 400)

    allowed = EDITABLE_BY_ADMIN if g.officer.is_admin else EDITABLE_BY_OFFICER
    unknown = set(data) - set(EDITABLE_BY_ADMIN)
    if unknown:
        return error(f"Unknown setting: {', '.join(sorted(unknown))}.", 400)
    forbidden = set(data) - set(allowed)
    if forbidden:
        return error("Only an administrator can change those settings.", 403)

    updates: dict[str, str] = {}
    try:
        if "lecture_start" in data:
            value = str(data["lecture_start"]).strip()
            if not _TIME_RE.match(value):
                raise ValueError("Lecture start must be a 24-hour time, e.g. 07:00.")
            updates["lecture_start"] = value
        if "lecture_duration_min" in data:
            updates["lecture_duration_min"] = str(_validate_int("lecture_duration_min", data["lecture_duration_min"], 30, 720))
        if "audio_window_min" in data:
            updates["audio_window_min"] = str(_validate_int("audio_window_min", data["audio_window_min"], 5, 180))
        if "repeat_interval_sec" in data:
            updates["repeat_interval_sec"] = str(_validate_int("repeat_interval_sec", data["repeat_interval_sec"], 10, 3600))
    except ValueError as exc:
        return error(str(exc), 400)

    for key, value in updates.items():
        set_setting(key, value, g.officer.id)

    action = "SET_INTERVAL" if set(updates) == {"repeat_interval_sec"} else "SETTINGS"
    log_action(g.officer.id, action, detail={"changed": updates})
    db.session.commit()

    if _SCHEDULE_KEYS & set(updates):
        get_engine(current_app._get_current_object()).reset_schedule()

    revision = revisions.bump()
    state = build_audio_state()
    settings = settings_public()
    notify_settings_changed(settings, state, revision)
    return jsonify({"settings": settings, "audio_state": state, "revision": revision})
