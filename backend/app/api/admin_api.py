"""Administrator endpoints: officers, rooms, audit trail."""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from flask import Blueprint, g, jsonify, request

from ..audit import log_action
from ..auth import admin_required, error, hash_password
from ..extensions import db
from ..models import AuditLog, LectureSession, Officer, Room
from ..realtime import notify_rooms_changed
from ..realtime_state import revisions
from ..rooms import parse_room_number, room_sort_key
from ..serializers import iso, officer_public, room_public
from .common import clean_text, json_body, parse_bool

bp = Blueprint("admin_api", __name__, url_prefix="/api")

_USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,59}$")
_ROLES = {"OFFICER", "ADMIN"}


# ------------------------------------------------------------------- officers
@bp.get("/officers")
@admin_required
def list_officers():
    rows = Officer.query.order_by(Officer.name.asc(), Officer.username.asc()).all()
    return jsonify({"officers": [officer_public(row) for row in rows]})


@bp.post("/officers")
@admin_required
def create_officer():
    data = json_body()
    name = clean_text(data.get("name"), 120)
    username = clean_text(data.get("username"), 60).lower()
    password = str(data.get("password") or "")
    role = str(data.get("role") or "OFFICER").upper()

    if not name:
        return error("Enter the officer's full name.", 400)
    if not _USERNAME_RE.match(username):
        return error("Username must be 3-60 characters: letters, numbers, dot, dash or underscore.", 400)
    if len(password) < 8:
        return error("Password must be at least 8 characters.", 400)
    if role not in _ROLES:
        return error("Role must be OFFICER or ADMIN.", 400)
    if Officer.query.filter_by(username=username).first():
        return error("That username is already taken.", 409)

    row = Officer(
        name=name,
        username=username,
        password_hash=hash_password(password),
        role=role,
        active=True,
    )
    db.session.add(row)
    db.session.flush()
    log_action(g.officer.id, "OFFICER_CREATE", detail={"officer_id": row.id, "username": username, "role": role})
    db.session.commit()
    return jsonify({"officer": officer_public(row)}), 201


@bp.patch("/officers/<int:officer_id>")
@admin_required
def update_officer(officer_id: int):
    row = db.session.get(Officer, officer_id)
    if row is None:
        return error("Officer not found.", 404)
    data = json_body()

    new_role = str(data.get("role", row.role)).upper()
    new_active = parse_bool(data.get("active"), row.active)
    if new_role not in _ROLES:
        return error("Role must be OFFICER or ADMIN.", 400)

    if row.id == g.officer.id and (new_role != "ADMIN" or not new_active):
        return error("You cannot deactivate or demote your own account.", 400)

    removing_admin = row.role == "ADMIN" and row.active and (new_role != "ADMIN" or not new_active)
    if removing_admin:
        remaining = Officer.query.filter(Officer.role == "ADMIN", Officer.active.is_(True), Officer.id != row.id).count()
        if remaining == 0:
            return error("At least one active administrator is required.", 400)

    name = clean_text(data.get("name", row.name), 120)
    if not name:
        return error("Name cannot be blank.", 400)

    changes: dict[str, object] = {}
    if name != row.name:
        row.name = name
        changes["name"] = name
    if new_role != row.role:
        changes["role"] = new_role
        row.role = new_role
    if new_active != row.active:
        changes["active"] = new_active
        row.active = new_active
    if "password" in data and data.get("password"):
        password = str(data["password"])
        if len(password) < 8:
            return error("Password must be at least 8 characters.", 400)
        row.password_hash = hash_password(password)
        changes["password_reset"] = True

    if changes:
        log_action(g.officer.id, "OFFICER_UPDATE", detail={"officer_id": row.id, **changes})
    db.session.commit()

    if not row.active:
        # Force a deactivated officer out of active sessions on their next request.
        pass
    return jsonify({"officer": officer_public(row)})


# ---------------------------------------------------------------------- rooms
@bp.post("/rooms")
@admin_required
def create_room():
    data = json_body()
    room_name = clean_text(data.get("room_name"), 40).upper()
    building = clean_text(data.get("building"), 40).upper() or "A"
    if not room_name:
        return error("Enter a room name.", 400)
    if Room.query.filter(db.func.lower(Room.room_name) == room_name.lower()).first():
        return error("That room already exists.", 409)

    row = Room(room_name=room_name, room_number=parse_room_number(room_name), building=building, active=True)
    db.session.add(row)
    db.session.flush()
    log_action(g.officer.id, "ROOM_CREATE", room_name=room_name, detail={"building": building})
    db.session.commit()

    revisions.bump()
    notify_rooms_changed()
    return jsonify({"room": room_public(row)}), 201


@bp.patch("/rooms/<int:room_id>")
@admin_required
def update_room(room_id: int):
    row = db.session.get(Room, room_id)
    if row is None:
        return error("Room not found.", 404)
    data = json_body()
    changes: dict[str, object] = {}

    new_name = clean_text(data.get("room_name", row.room_name), 40).upper()
    if new_name != row.room_name:
        clash = Room.query.filter(
            db.func.lower(Room.room_name) == new_name.lower(), Room.id != row.id
        ).first()
        if clash:
            return error("That room already exists.", 409)
        active = LectureSession.query.filter_by(room_name=row.room_name, status="IN_PROGRESS").first()
        if active:
            return error("End the active session before renaming this room.", 409)
        changes["room_name"] = new_name
        row.room_name = new_name
        row.room_number = parse_room_number(new_name)

    new_building = clean_text(data.get("building", row.building), 40).upper() or row.building
    if new_building != row.building:
        row.building = new_building
        changes["building"] = new_building

    new_active = parse_bool(data.get("active"), row.active)
    if new_active != row.active:
        if not new_active:
            active = LectureSession.query.filter_by(room_name=row.room_name, status="IN_PROGRESS").first()
            if active:
                return error("End the active session before deactivating this room.", 409)
        row.active = new_active
        changes["active"] = new_active

    if changes:
        log_action(g.officer.id, "ROOM_UPDATE", room_name=row.room_name, detail=changes)
    db.session.commit()

    revisions.bump()
    notify_rooms_changed()
    return jsonify({"room": room_public(row)})


# ---------------------------------------------------------------------- audit
@bp.get("/audit")
@admin_required
def audit_log():
    query = AuditLog.query

    date_text = (request.args.get("date") or "").strip()
    if date_text:
        try:
            day = datetime.strptime(date_text, "%Y-%m-%d")
        except ValueError:
            return error("Date must be formatted YYYY-MM-DD.", 400)
        query = query.filter(AuditLog.created_at >= day, AuditLog.created_at < day + timedelta(days=1))

    room = (request.args.get("room") or "").strip()
    if room:
        query = query.filter(AuditLog.room_name.ilike(f"%{room}%"))

    action = (request.args.get("action") or "").strip().upper()
    if action:
        query = query.filter(AuditLog.action == action)

    officer_text = (request.args.get("officer_id") or "").strip()
    if officer_text:
        try:
            query = query.filter(AuditLog.officer_id == int(officer_text))
        except ValueError:
            return error("officer_id must be a number.", 400)

    try:
        limit = min(200, max(1, int(request.args.get("limit", 50))))
        offset = max(0, int(request.args.get("offset", 0)))
    except ValueError:
        return error("limit and offset must be numbers.", 400)

    total = query.count()
    rows = query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).offset(offset).limit(limit).all()

    entries = [
        {
            "id": row.id,
            "action": row.action,
            "room_name": row.room_name,
            "detail": row.detail,
            "created_at": iso(row.created_at),
            "officer": (
                {"id": row.officer.id, "name": row.officer.name, "username": row.officer.username}
                if row.officer
                else None
            ),
        }
        for row in rows
    ]
    return jsonify({"entries": entries, "total": total, "limit": limit, "offset": offset})
