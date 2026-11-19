"""Signed read-only tokens for public display screens."""
from __future__ import annotations

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

SALT = "smart-room-display"


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=SALT)


def issue_display_token() -> str:
    return _serializer().dumps({"scope": "display", "building": current_app.config.get("BUILDING_NAME", "Building A")})


def display_token_valid(token: str | None) -> bool:
    if not token:
        return False
    try:
        payload = _serializer().loads(token, max_age=current_app.config["DISPLAY_TOKEN_MAX_AGE_SEC"])
        return isinstance(payload, dict) and payload.get("scope") == "display"
    except (BadSignature, SignatureExpired, Exception):
        return False


def display_access_allowed(token: str | None) -> bool:
    """Token is optional while DISPLAY_REQUIRE_TOKEN is false (pilot demo)."""
    if not current_app.config["DISPLAY_REQUIRE_TOKEN"]:
        return True
    return display_token_valid(token)
