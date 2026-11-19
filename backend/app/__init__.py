"""Application factory."""
from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, request, send_file
from werkzeug.exceptions import HTTPException

from .config import INSTANCE_DIR, Config
from .extensions import db, socketio
from .realtime import register_socket_handlers
from .realtime_state import revisions

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


def create_app(config_object=Config, overrides: dict | None = None) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config.from_object(config_object)
    if overrides:
        app.config.update(overrides)

    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    socketio.init_app(
        app,
        async_mode="threading",
        cors_allowed_origins=None,
        manage_session=True,
    )

    _register_blueprints(app)
    register_socket_handlers()
    _register_error_handlers(app)
    _register_spa(app)

    with app.app_context():
        if app.config.get("TESTING"):
            revisions.reset()
            from .switch_state import switch_notices

            switch_notices.clear()
        if app.config.get("AUTO_INIT_DB") or app.config.get("TESTING"):
            db.create_all()
        from .settings_store import ensure_defaults

        ensure_defaults()
        if app.config.get("AUTO_SEED"):
            from .seed import seed_defaults

            seed_defaults(app)

    if app.config.get("AUDIO_ENABLED") and not app.config.get("TESTING"):
        from .audio.service import AudioService

        service = AudioService(app)
        app.extensions["audio_engine"] = service.engine
        app.extensions["audio_service"] = service
        service.start()

    @app.get("/api/health")
    def health():
        return jsonify(
            {
                "status": "ok",
                "building": app.config.get("BUILDING_NAME", "Building A"),
                "revision": revisions.current(),
            }
        )

    return app


def _register_blueprints(app: Flask) -> None:
    from .api.admin_api import bp as admin_bp
    from .api.audio_api import bp as audio_bp
    from .api.auth_api import bp as auth_bp
    from .api.display_api import bp as display_bp
    from .api.rooms_api import bp as rooms_bp
    from .api.sessions_api import bp as sessions_bp
    from .api.settings_api import bp as settings_bp

    for blueprint in (auth_bp, sessions_bp, rooms_bp, settings_bp, audio_bp, admin_bp, display_bp):
        app.register_blueprint(blueprint)


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(HTTPException)
    def handle_http_error(exc: HTTPException):
        if request.path.startswith("/api/") or request.path.startswith("/socket.io"):
            return jsonify({"error": exc.description or exc.name}), exc.code or 500
        if exc.code == 404:
            return _spa_response("")
        return exc

    @app.errorhandler(Exception)
    def handle_unexpected(exc: Exception):
        app.logger.exception("Unhandled error on %s", request.path)
        if request.path.startswith("/api/"):
            return jsonify({"error": "Something went wrong. Please try again."}), 500
        return "Internal server error", 500


def _register_spa(app: Flask) -> None:
    @app.get("/")
    def index():
        return _spa_response("")

    @app.get("/<path:path>")
    def spa(path: str):
        return _spa_response(path)


def _spa_response(path: str):
    if path.startswith(("api/", "socket.io")):
        return jsonify({"error": "Not found."}), 404

    index_file = STATIC_DIR / "index.html"
    if path:
        candidate = (STATIC_DIR / path).resolve()
        try:
            candidate.relative_to(STATIC_DIR.resolve())
        except ValueError:
            candidate = None
        if candidate is not None and candidate.is_file():
            return send_file(candidate)

    if index_file.is_file():
        return send_file(index_file)

    return (
        """<!doctype html><html><head><meta charset="utf-8"><title>Smart Lecture Rooms</title>
        <style>body{font-family:system-ui,sans-serif;background:#F6F8FB;color:#101828;display:grid;
        place-items:center;min-height:100vh;margin:0}.box{max-width:520px;background:#fff;padding:40px;
        border-radius:12px;border:1px solid #E4E7EC;box-shadow:0 10px 30px rgba(16,24,40,.08)}
        code{background:#EEF2F6;padding:2px 6px;border-radius:4px}</style></head><body><div class="box">
        <h1>Frontend not built yet</h1><p>The API is running. Build the React app once:</p>
        <pre><code>cd frontend
npm install
npm run build</code></pre><p>Then refresh this page, or run <code>npm run dev</code> for development.</p>
        <p><a href="/api/health">API health</a></p></div></body></html>""",
        200,
    )
