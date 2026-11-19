"""Password hashing and request authentication helpers."""
from __future__ import annotations

from functools import wraps

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from flask import g, jsonify, session

from .extensions import db
from .models import Officer

_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, VerifyMismatchError, InvalidHashError):
        return False
    except Exception:  # pragma: no cover - defensive: never 500 on a bad hash
        return False


def needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except Exception:
        return False


def current_officer() -> Officer | None:
    officer_id = session.get("officer_id")
    if not officer_id:
        return None
    officer = db.session.get(Officer, officer_id)
    if officer is None or not officer.active:
        return None
    return officer


def error(message: str, status: int = 400, **extra):
    payload = {"error": message}
    payload.update(extra)
    return jsonify(payload), status


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        officer = current_officer()
        if officer is None:
            return error("Please sign in to continue.", 401)
        g.officer = officer
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        officer = current_officer()
        if officer is None:
            return error("Please sign in to continue.", 401)
        if not officer.is_admin:
            return error("Administrator access is required.", 403)
        g.officer = officer
        return view(*args, **kwargs)

    return wrapped
