from __future__ import annotations

from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
# Threading mode keeps deployment simple on a single VM and works with
# Gunicorn's gthread worker. Eventlet/gevent are deliberately not required.
socketio = SocketIO(async_mode="threading", cors_allowed_origins=None, manage_session=True)
