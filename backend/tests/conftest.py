from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import LectureSession, Officer  # noqa: E402


@pytest.fixture()
def app(tmp_path):
    database = tmp_path / "test.db"
    application = create_app(
        overrides={
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database.as_posix()}",
            "SQLALCHEMY_ENGINE_OPTIONS": {"pool_pre_ping": True, "connect_args": {"timeout": 30}},
            "AUDIO_ENABLED": False,
            "AUTO_SEED": True,
            "DISPLAY_REQUIRE_TOKEN": False,
        }
    )
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_client(app):
    client = app.test_client()
    response = client.post("/api/auth/login", json={"username": "otieno", "password": "Officer@123"})
    assert response.status_code == 200, response.get_json()
    return client


@pytest.fixture()
def admin_client(app):
    client = app.test_client()
    response = client.post("/api/auth/login", json={"username": "admin", "password": "Admin@123"})
    assert response.status_code == 200, response.get_json()
    return client


@pytest.fixture()
def officer(app):
    with app.app_context():
        return Officer.query.filter_by(username="otieno").first()


@pytest.fixture(autouse=True)
def clean_sessions(app):
    with app.app_context():
        LectureSession.query.delete()
        db.session.commit()
    yield
