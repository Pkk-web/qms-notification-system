"""Convenience CLI: python manage.py <command>."""
from __future__ import annotations

import argparse
import getpass
import sys

from app.config import Config
from app import create_app
from app.extensions import db, socketio


def _app(**overrides):
    config = {**overrides}
    return create_app(Config, config)


def command_init_db(args):
    app = _app(AUDIO_ENABLED=False)
    with app.app_context():
        db.create_all()
        print("Database tables created.")
    print(f"Database: {app.config['SQLALCHEMY_DATABASE_URI']}")


def command_seed(args):
    from app.seed import seed_defaults

    app = _app(AUDIO_ENABLED=False)
    with app.app_context():
        seed_defaults(app)
        print("Seed complete (existing rows were left untouched).")


def command_reset_password(args):
    from app.auth import hash_password
    from app.models import Officer

    app = _app(AUDIO_ENABLED=False)
    with app.app_context():
        officer = Officer.query.filter_by(username=args.username.lower()).first()
        if officer is None:
            print(f"No officer with username {args.username!r}.")
            sys.exit(1)
        password = args.password or getpass.getpass("New password: ")
        if len(password) < 8:
            print("Password must be at least 8 characters.")
            sys.exit(1)
        officer.password_hash = hash_password(password)
        officer.active = True
        db.session.commit()
        print(f"Password updated for {officer.username}.")


def command_run(args):
    app = _app()
    print(f"Database: {app.config['SQLALCHEMY_DATABASE_URI']}")
    print("Serving on http://localhost:%d" % args.port)
    socketio.run(
        app,
        host=args.host,
        port=args.port,
        debug=args.debug,
        use_reloader=args.debug,
        allow_unsafe_werkzeug=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Smart Lecture Room Notification System")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init-db", help="Create database tables")
    p_init.set_defaults(func=command_init_db)

    p_seed = sub.add_parser("seed", help="Create demo officers and rooms")
    p_seed.set_defaults(func=command_seed)

    p_reset = sub.add_parser("reset-password", help="Reset an officer password")
    p_reset.add_argument("username")
    p_reset.add_argument("--password", help="Non-interactive password (use with care)")
    p_reset.set_defaults(func=command_reset_password)

    p_run = sub.add_parser("run", help="Run the development server")
    p_run.add_argument("--host", default="127.0.0.1")
    p_run.add_argument("--port", type=int, default=5000)
    p_run.add_argument("--debug", action="store_true")
    p_run.set_defaults(func=command_run)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
