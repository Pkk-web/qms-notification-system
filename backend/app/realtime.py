"""SocketIO: snapshot-on-connect, revision-guarded events, and broadcast helpers."""
from __future__ import annotations

from datetime import datetime

from flask import current_app
from flask_socketio import emit

from .audio.service import build_audio_state
from .auth import current_officer
from .display_auth import display_access_allowed
from .extensions import socketio
from .models import LectureSession
from .realtime_state import revisions
from .rooms import sort_sessions
from .serializers import iso, session_public, settings_public
from .switch_state import switch_notices


def _building() -> dict:
    return {
        "name": current_app.config.get("BUILDING_NAME", "Building A"),
        "label": current_app.config.get("BUILDING_LABEL", "LECTURE ROOMS"),
    }


def build_snapshot(app=None, at: datetime | None = None) -> dict:
    at = (at or datetime.now()).replace(microsecond=0)
    sessions = sort_sessions(LectureSession.query.filter_by(status="IN_PROGRESS").all())
    return {
        "sessions": [session_public(row, at) for row in sessions],
        "audio_state": build_audio_state(app, at),
        "settings": settings_public(),
        "revision": revisions.current(),
        "server_now": iso(at),
        "building": _building(),
        "switch_notice": switch_notices.current(at),
    }


def _connection_authorised(auth) -> bool:
    if current_officer() is not None:
        return True
    token = auth.get("token") if isinstance(auth, dict) else None
    return display_access_allowed(token)


def register_socket_handlers() -> None:
    @socketio.on("connect")
    def _connect(auth=None):
        if not _connection_authorised(auth):
            return False
        emit("snapshot", build_snapshot())
        return True

    @socketio.on("request:snapshot")
    def _request_snapshot(_data=None):
        # Connection was authorised at connect time; re-send authoritative state.
        emit("snapshot", build_snapshot())

    @socketio.on("ping:display")
    def _ping(_data=None):
        emit("pong:display", {"server_now": iso(datetime.now()), "revision": revisions.current()})


# ---------------------------------------------------------------- broadcasters
def notify_session_created(session_payload: dict, revision: int) -> None:
    socketio.emit("session:created", {"session": session_payload, "revision": revision})


def notify_session_ended(session_payload: dict, revision: int) -> None:
    socketio.emit(
        "session:ended",
        {
            "session": session_payload,
            "session_id": session_payload["id"],
            "room_name": session_payload["room_name"],
            "revision": revision,
        },
    )


def notify_session_switched(
    session_payload: dict,
    from_room: str,
    to_room: str,
    switch_notice: dict,
    revision: int,
) -> None:
    socketio.emit(
        "session:switched",
        {
            "session": session_payload,
            "session_id": session_payload["id"],
            "from_room": from_room,
            "to_room": to_room,
            "switch_notice": switch_notice,
            "revision": revision,
        },
    )


def notify_settings_changed(settings: dict, audio_state: dict, revision: int) -> None:
    socketio.emit(
        "settings:updated",
        {"settings": settings, "audio_state": audio_state, "revision": revision},
    )


def notify_rooms_changed() -> None:
    socketio.emit("rooms:updated", {"revision": revisions.current()})


def broadcast_audio_state(payload: dict | None = None) -> None:
    socketio.emit("audio:state", payload or build_audio_state())


def broadcast_announcement(text: str, rooms: list[str], at: datetime) -> None:
    socketio.emit(
        "audio:announce",
        {"text": text, "rooms": rooms, "at": iso(at), "revision": revisions.current()},
    )
