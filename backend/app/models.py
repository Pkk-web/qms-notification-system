"""Database models.

Times are stored as naive local time. The pilot is a single building with a
single server, so local time (Africa/Nairobi) is authoritative and avoids
timezone drift between console, display and the audio scheduler.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Computed, Index
from sqlalchemy.orm import validates

from .extensions import db


def now() -> datetime:
    return datetime.now().replace(microsecond=0)


class Officer(db.Model):
    __tablename__ = "officers"

    id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    username = db.Column(db.String(60), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum("OFFICER", "ADMIN", name="officer_role"), nullable=False, default="OFFICER")
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now)

    sessions_ticked = db.relationship(
        "LectureSession", foreign_keys="LectureSession.ticked_by", back_populates="ticked_by_officer", lazy="dynamic"
    )

    @validates("username")
    def _normalise_username(self, _key, value: str) -> str:
        return (value or "").strip().lower()

    @property
    def is_admin(self) -> bool:
        return self.role == "ADMIN"

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Officer {self.username} ({self.role})>"


class Room(db.Model):
    """The physical rooms offered in the console grid."""

    __tablename__ = "rooms"

    id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), primary_key=True)
    room_name = db.Column(db.String(40), unique=True, nullable=False)
    room_number = db.Column(db.Integer, nullable=False, default=0, index=True)
    building = db.Column(db.String(40), nullable=False, default="A")
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now)


class LectureSession(db.Model):
    __tablename__ = "sessions"

    id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), primary_key=True)
    room_name = db.Column(db.String(40), nullable=False, index=True)
    room_number = db.Column(db.Integer, nullable=False, default=0, index=True)
    lecturer_name = db.Column(db.String(120), nullable=True)
    status = db.Column(
        db.Enum("IN_PROGRESS", "ENDED", name="session_status"), nullable=False, default="IN_PROGRESS", index=True
    )
    started_at = db.Column(db.DateTime, nullable=False, default=now)
    ended_at = db.Column(db.DateTime, nullable=True)
    ticked_by = db.Column(
        db.BigInteger().with_variant(db.Integer, "sqlite"), db.ForeignKey("officers.id"), nullable=False
    )
    ended_by = db.Column(
        db.BigInteger().with_variant(db.Integer, "sqlite"), db.ForeignKey("officers.id"), nullable=True
    )

    # Critical constraint: at most one IN_PROGRESS session per room.
    #
    # A filtered partial index (WHERE status = 'IN_PROGRESS') is not available
    # in MySQL, so the constraint is expressed as a stored generated column
    # that is NULL for ended sessions and the room name for active sessions.
    # A UNIQUE index on that column enforces "one active session per room" at
    # the database level in both SQLite and MySQL, because NULL values are not
    # considered duplicates.
    active_room_name = db.Column(
        db.String(40),
        Computed("(CASE WHEN status = 'IN_PROGRESS' THEN room_name ELSE NULL END)", persisted=True),
        unique=True,
        nullable=True,
    )

    ticked_by_officer = db.relationship("Officer", foreign_keys=[ticked_by], back_populates="sessions_ticked")
    ended_by_officer = db.relationship("Officer", foreign_keys=[ended_by], lazy="joined")

    __table_args__ = (
        Index("ix_sessions_status_room", "status", "room_name"),
        Index("ix_sessions_started_at", "started_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<LectureSession {self.room_name} {self.status}>"


class Setting(db.Model):
    __tablename__ = "settings"

    key = db.Column(db.String(60), primary_key=True)
    value = db.Column(db.String(255), nullable=False)
    updated_by = db.Column(
        db.BigInteger().with_variant(db.Integer, "sqlite"), db.ForeignKey("officers.id"), nullable=True
    )
    updated_at = db.Column(db.DateTime, nullable=False, default=now, onupdate=now)


class AuditLog(db.Model):
    __tablename__ = "audit_log"

    id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), primary_key=True)
    officer_id = db.Column(
        db.BigInteger().with_variant(db.Integer, "sqlite"), db.ForeignKey("officers.id"), nullable=False, index=True
    )
    action = db.Column(db.String(60), nullable=False, index=True)
    room_name = db.Column(db.String(40), nullable=True)
    detail = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now, index=True)

    officer = db.relationship("Officer", lazy="joined")

    __table_args__ = (Index("ix_audit_created_action", "created_at", "action"),)
