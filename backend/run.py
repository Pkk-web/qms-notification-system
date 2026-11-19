"""WSGI entry point. Development: python run.py."""
from __future__ import annotations

from app.config import Config
from app import create_app
from app.extensions import socketio

app = create_app(Config)

if __name__ == "__main__":
    socketio.run(app, host="127.0.0.1", port=5000, debug=False, allow_unsafe_werkzeug=True)
