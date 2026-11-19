"""Session lifecycle: tick a room in progress and end it."""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, current_app, g, jsonify
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..audit import log_action
from ..audio.service import get_engine
from ..auth import error, login_required
from ..extensions import db
from ..models import LectureSession, Room
from ..realtime import (
    broadcast_announcement,
    notify_session_created,
    notify_session_ended,
    notify_session_switched,
)
from ..realtime_state import revisions
from ..rooms import parse_room_number, sort_sessions
from ..serializers import iso, session_public
from ..switch_state import switch_notices
from .common import clean_text, json_body

bp = Blueprint("sessions_api", __name__, url_prefix="/api")


def _active_for_room(room_name: str) -> LectureSession | None:
    stmt = (
        select(LectureSession)
        .where(LectureSession.room_name == room_name, LectureSession.status == "IN_PROGRESS")
        .with_for_update()
    )
    return db.session.execute(stmt).scalars().first()


@bp.get("/sessions")
@login_required
def list_sessions():
    at = datetime.now().replace(microsecond=0)
    rows = sort_sessions(LectureSession.query.filter_by(status="IN_PROGRESS").all())
    return jsonify(
        {
            "sessions": [session_public(row, at) for row in rows],
            "revision": revisions.current(),
            "server_now": iso(at),
        }
    )


@bp.post("/sessions")
@login_required
def tick_room():
    data = json_body()
    room_name = clean_text(data.get("room_name"), 40)
    lecturer_name = clean_text(data.get("lecturer_name"), 120) or None

    if not room_name:
        return error("Choose a room first.", 400)

    room = Room.query.filter_by(room_name=room_name).first()
    if room is None or not room.active:
        return error("That room is not available. Refresh the room list.", 404)

    existing = _active_for_room(room.room_name)
    if existing is not None:
        return error(
            f"{room.room_name} is already in progress.",
            409,
            session=session_public(existing),
        )

    started = datetime.now().replace(microsecond=0)
    session_row = LectureSession(
        room_name=room.room_name,
        room_number=room.room_number or parse_room_number(room.room_name),
        lecturer_name=lecturer_name,
        status="IN_PROGRESS",
        started_at=started,
        ticked_by=g.officer.id,
    )
    db.session.add(session_row)
    log_action(
        g.officer.id,
        "TICK",
        room_name=room.room_name,
        detail={"lecturer_name": lecturer_name, "started_at": started.isoformat(timespec="seconds")},
    )
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing = _active_for_room(room.room_name)
        return error(
            f"{room.room_name} is already in progress.",
            409,
            session=session_public(existing) if existing else None,
        )

    payload = session_public(session_row, started)
    revision = revisions.bump()
    notify_session_created(payload, revision)
    return jsonify({"session": payload, "revision": revision}), 201


@bp.post("/sessions/<int:session_id>/end")
@login_required
def end_session(session_id: int):
    data = json_body()
    row = db.session.get(LectureSession, session_id)
    if row is None:
        return error("That session no longer exists.", 404)
    if row.status != "IN_PROGRESS":
        return error("That session has already ended.", 409)

    ended = datetime.now().replace(microsecond=0)
    row.status = "ENDED"
    row.ended_at = ended
    row.ended_by = g.officer.id
    log_action(
        g.officer.id,
        "END",
        room_name=row.room_name,
        detail={"session_id": row.id, "undo": bool(data.get("undo"))},
    )
    db.session.commit()

    payload = session_public(row, ended)
    revision = revisions.bump()
    notify_session_ended(payload, revision)
    return jsonify({"session": payload, "revision": revision})


@bp.post("/sessions/<int:session_id>/switch")
@login_required
def switch_session(session_id: int):
    """Move an in-progress lecture to another room without restarting it."""
    data = json_body()
    to_room = clean_text(data.get("room_name"), 40)

    row = db.session.get(LectureSession, session_id)
    if row is None:
        return error("That session no longer exists.", 404)
    if row.status != "IN_PROGRESS":
        return error("Only a session in progress can be switched.", 409)
    if not to_room:
        return error("Choose the room the lecture moved to.", 400)

    room = Room.query.filter_by(room_name=to_room).first()
    if room is None or not room.active:
        return error("That room is not available. Refresh the room list.", 404)

    from_room = row.room_name
    if room.room_name == from_room:
        return error(f"The lecture is already in {from_room}.", 400)

    occupied = _active_for_room(room.room_name)
    if occupied is not None:
        return error(
            f"{room.room_name} is already in progress.",
            409,
            session=session_public(occupied),
        )

    at = datetime.now().replace(microsecond=0)
    row.room_name = room.room_name
    row.room_number = room.room_number or parse_room_number(room.room_name)
    log_action(
        g.officer.id,
        "SWITCH_ROOM",
        room_name=room.room_name,
        detail={"session_id": row.id, "from_room": from_room, "to_room": room.room_name},
    )
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        occupied = _active_for_room(room.room_name)
        return error(
            f"{room.room_name} is already in progress.",
            409,
            session=session_public(occupied) if occupied else None,
        )

    payload = session_public(row, at)
    notice = switch_notices.set(
        session_id=row.id,
        from_room=from_room,
        to_room=row.room_name,
        at=at,
    )
    revision = revisions.bump()
    notify_session_switched(payload, from_room, row.room_name, notice, revision)

    # Speak the change immediately. If audio is busy, the switch still stands
    # and the display banner carries the news.
    announcement = get_engine(current_app._get_current_object()).play_text_now(
        notice["speech"], [row.room_name], at
    )
    announcement_payload = None
    if announcement is not None:
        broadcast_announcement(announcement.text, list(announcement.rooms), announcement.at)
        announcement_payload = {
            "text": announcement.text,
            "rooms": list(announcement.rooms),
            "at": iso(announcement.at),
        }

    return jsonify(
        {
            "session": payload,
            "from_room": from_room,
            "to_room": row.room_name,
            "switch_notice": notice,
            "announcement": announcement_payload,
            "revision": revision,
        }
    )
