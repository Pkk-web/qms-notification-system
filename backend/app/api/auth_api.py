"""Login, logout and current-officer endpoints."""
from __future__ import annotations

import threading
import time

from flask import Blueprint, g, jsonify, request, session

from ..audit import log_action
from ..auth import (
    error,
    hash_password,
    login_required,
    needs_rehash,
    verify_password,
)
from ..extensions import db
from ..models import Officer
from ..serializers import officer_public
from .common import clean_text, json_body

bp = Blueprint("auth_api", __name__, url_prefix="/api/auth")

# Simple in-process throttle: 10 failures per username+IP per 5 minutes.
_WINDOW_SEC = 300
_MAX_FAILURES = 10
_failures: dict[str, list[float]] = {}
_lock = threading.Lock()
_DUMMY_HASH = hash_password("timing-equaliser-not-a-real-password")


def _throttled(key: str) -> bool:
    now = time.time()
    with _lock:
        recent = [stamp for stamp in _failures.get(key, []) if now - stamp < _WINDOW_SEC]
        _failures[key] = recent
        return len(recent) >= _MAX_FAILURES


def _record_failure(key: str) -> None:
    with _lock:
        _failures.setdefault(key, []).append(time.time())


def _clear_failures(key: str) -> None:
    with _lock:
        _failures.pop(key, None)


@bp.post("/login")
def login():
    data = json_body()
    username = clean_text(data.get("username"), 60).lower()
    password = str(data.get("password") or "")
    if not username or not password:
        return error("Enter your username and password.", 400)

    key = f"{request.remote_addr or 'local'}:{username}"
    if _throttled(key):
        return error("Too many failed attempts. Try again in a few minutes.", 429)

    officer = Officer.query.filter_by(username=username).first()
    valid = False
    if officer is not None and officer.active:
        valid = verify_password(officer.password_hash, password)
    else:
        # Keep timing similar whether or not the username exists.
        verify_password(_DUMMY_HASH, password)

    if not valid:
        _record_failure(key)
        return error("Incorrect username or password.", 401)

    _clear_failures(key)
    if needs_rehash(officer.password_hash):
        officer.password_hash = hash_password(password)

    session.clear()
    session.permanent = True
    session["officer_id"] = officer.id
    log_action(officer.id, "LOGIN", detail={"ip": request.remote_addr})
    db.session.commit()
    return jsonify({"officer": officer_public(officer)})


@bp.post("/logout")
@login_required
def logout():
    officer = g.officer
    log_action(officer.id, "LOGOUT")
    db.session.commit()
    session.clear()
    return jsonify({"ok": True})


@bp.get("/me")
@login_required
def me():
    return jsonify({"officer": officer_public(g.officer)})
