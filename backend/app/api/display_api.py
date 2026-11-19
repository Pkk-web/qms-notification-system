"""Public display token and read-only REST snapshot."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from ..auth import login_required
from ..display_auth import display_access_allowed, issue_display_token
from ..realtime import build_snapshot

bp = Blueprint("display_api", __name__, url_prefix="/api/display")


@bp.get("/token")
@login_required
def token():
    value = issue_display_token()
    return jsonify(
        {
            "token": value,
            "path": f"/#/display?token={value}",
            "expires_in": current_app.config["DISPLAY_TOKEN_MAX_AGE_SEC"],
        }
    )


@bp.get("/snapshot")
def snapshot():
    supplied = request.args.get("token") or request.headers.get("X-Display-Token")
    if not display_access_allowed(supplied):
        return jsonify({"error": "A valid display link is required."}), 401
    return jsonify(build_snapshot())
