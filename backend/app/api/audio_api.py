"""Officer audio controls: pause, resume, extend and test announcements."""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, current_app, g, jsonify

from ..audio.service import build_audio_state, get_engine
from ..audit import log_action
from ..auth import error, login_required
from ..extensions import db
from ..models import LectureSession
from ..realtime import broadcast_announcement, broadcast_audio_state
from ..realtime_state import revisions
from ..rooms import sort_room_names
from ..serializers import iso
from ..settings_store import extend_window, set_setting
from .common import json_body

bp = Blueprint("audio_api", __name__, url_prefix="/api/audio")


def _commit_and_broadcast(extra: dict | None = None):
    db.session.commit()
    revision = revisions.bump()
    state = build_audio_state()
    broadcast_audio_state(state)
    payload = {"audio_state": state, "revision": revision}
    if extra:
        payload.update(extra)
    return jsonify(payload)


@bp.get("/state")
@login_required
def state():
    return jsonify({"audio_state": build_audio_state(), "revision": revisions.current()})


@bp.post("/pause")
@login_required
def pause():
    set_setting("audio_paused", "1", g.officer.id)
    log_action(g.officer.id, "PAUSE")
    return _commit_and_broadcast()


@bp.post("/resume")
@login_required
def resume():
    set_setting("audio_paused", "0", g.officer.id)
    log_action(g.officer.id, "RESUME")
    return _commit_and_broadcast()


@bp.post("/extend")
@login_required
def extend():
    data = json_body()
    try:
        minutes = int(data.get("minutes", 15))
    except (TypeError, ValueError):
        return error("Extension must be a whole number of minutes.", 400)
    if minutes < 5 or minutes > 60:
        return error("Extension must be between 5 and 60 minutes.", 400)

    until = extend_window(minutes)
    log_action(g.officer.id, "EXTEND", detail={"minutes": minutes, "until": iso(until)})
    return _commit_and_broadcast({"extended_until": iso(until)})


@bp.post("/test")
@login_required
def test_announcement():
    rooms = sort_room_names(
        row.room_name for row in LectureSession.query.filter_by(status="IN_PROGRESS").all()
    )
    if not rooms:
        return error("There are no in-progress rooms to announce.", 409)

    at = datetime.now().replace(microsecond=0)
    engine = get_engine(current_app._get_current_object())
    announcement = engine.play_now(rooms, at)
    if announcement is None:
        return error("Audio is still playing. Try again in a moment.", 409)

    log_action(g.officer.id, "TEST_ANNOUNCE", detail={"text": announcement.text})
    db.session.commit()
    broadcast_announcement(announcement.text, list(announcement.rooms), announcement.at)
    return jsonify(
        {
            "text": announcement.text,
            "rooms": list(announcement.rooms),
            "audio_state": build_audio_state(),
            "revision": revisions.current(),
        }
    )
