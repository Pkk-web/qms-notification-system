"""Room list for the console grid."""
from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from ..auth import error, login_required
from ..models import Room
from ..realtime_state import revisions
from ..rooms import room_sort_key
from ..serializers import room_public

bp = Blueprint("rooms_api", __name__, url_prefix="/api")


@bp.get("/rooms")
@login_required
def list_rooms():
    include_inactive = request.args.get("include_inactive", "").lower() in {"1", "true", "yes"}
    if include_inactive and not g.officer.is_admin:
        return error("Administrator access is required.", 403)

    query = Room.query
    if not include_inactive:
        query = query.filter_by(active=True)
    rooms = sorted(query.all(), key=lambda room: room_sort_key(room.room_name))
    return jsonify({"rooms": [room_public(room) for room in rooms], "revision": revisions.current()})
