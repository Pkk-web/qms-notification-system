"""Idempotent demo seed data."""
from __future__ import annotations

from flask import Flask

from .auth import hash_password
from .extensions import db
from .models import Officer, Room
from .rooms import parse_room_number

DEFAULT_ROOMS = [
    "KLH9",
    "KLH10",
    "KLH101",
    "KLH101A",
    "KLH102",
    "KLH103",
    "KLH105",
    "KLH110",
    "KLH201",
    "KLH202",
    "KLH205",
    "KLH210",
]


def seed_defaults(app: Flask) -> None:
    created: list[str] = []

    if Officer.query.count() == 0:
        admin = Officer(
            name="System Administrator",
            username=app.config["DEFAULT_ADMIN_USERNAME"],
            password_hash=hash_password(app.config["DEFAULT_ADMIN_PASSWORD"]),
            role="ADMIN",
            active=True,
        )
        officer = Officer(
            name="J. Otieno",
            username=app.config["DEFAULT_OFFICER_USERNAME"],
            password_hash=hash_password(app.config["DEFAULT_OFFICER_PASSWORD"]),
            role="OFFICER",
            active=True,
        )
        db.session.add_all([admin, officer])
        created.append(f"officers ({admin.username}, {officer.username})")

    if Room.query.count() == 0:
        for name in DEFAULT_ROOMS:
            db.session.add(
                Room(room_name=name, room_number=parse_room_number(name), building="A", active=True)
            )
        created.append(f"{len(DEFAULT_ROOMS)} rooms")

    if created:
        db.session.commit()
        app.logger.warning(
            "Seeded %s. Change the default passwords before deployment.", ", ".join(created)
        )
