"""Small request-validation helpers shared by the API blueprints."""
from __future__ import annotations

from flask import request


def json_body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def clean_text(value, max_length: int) -> str:
    return str(value or "").strip()[:max_length]


def parse_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}
