"""Audit-trail helper. Callers own the transaction commit."""
from __future__ import annotations

from .extensions import db
from .models import AuditLog


def log_action(officer_id: int, action: str, room_name: str | None = None, detail: dict | None = None) -> AuditLog:
    entry = AuditLog(officer_id=officer_id, action=action, room_name=room_name, detail=detail)
    db.session.add(entry)
    return entry
