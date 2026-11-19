"""Background audio scheduler and read-only audio state payloads."""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime

from flask import current_app, has_app_context

from ..extensions import db, socketio
from ..models import LectureSession
from ..realtime_state import revisions
from ..rooms import sort_room_names
from ..serializers import iso
from ..settings_store import AudioConfig, build_audio_config
from .engine import AudioEngine
from .players import LogPlayer, make_player

log = logging.getLogger(__name__)


def _empty_engine() -> AudioEngine:
    return AudioEngine(LogPlayer())


def get_engine(app=None) -> AudioEngine:
    if app is None and has_app_context():
        app = current_app._get_current_object()
    if app is not None:
        engine = app.extensions.get("audio_engine")
        if engine is not None:
            return engine
    return _empty_engine()


def build_audio_state(app=None, at: datetime | None = None) -> dict:
    """Full audio state for API/socket payloads (never raises)."""
    at = (at or datetime.now()).replace(microsecond=0)
    cfg = build_audio_config(at)
    engine = get_engine(app)
    described = engine.describe(cfg)
    return {
        **described,
        "next_cycle_at": iso(described["next_cycle_at"]),
        "last_announcement_at": iso(described["last_announcement_at"]),
        "window_start": iso(cfg.start),
        "window_end": iso(cfg.end),
        "base_window_end": iso(cfg.base_end),
        "lecture_start": iso(cfg.start),
        "lecture_end": iso(cfg.lecture_end),
        "interval_sec": cfg.interval_sec,
        "window_min": cfg.window_min,
        "paused": cfg.paused,
        "extended": cfg.extended,
        "revision": revisions.current(),
        "server_now": iso(at),
    }


def _state_signature(cfg: AudioConfig, described: dict) -> tuple:
    return (
        described["state"],
        described["reason"],
        described["is_playing"],
        described["next_cycle_at"],
        cfg.interval_sec,
        cfg.end,
        cfg.paused,
        described["skipped_cycles"],
        described["last_announcement_at"],
    )


class AudioService:
    """One daemon thread that polls the engine once per second."""

    def __init__(self, app) -> None:
        self.app = app
        self.engine = AudioEngine(
            make_player(app.config.get("TTS_ADAPTER", "browser"), app.config.get("TTS_COMMAND", "")),
            seconds_per_room=app.config.get("AUDIO_SECONDS_PER_ROOM", 2.4),
            seconds_overhead=app.config.get("AUDIO_SECONDS_OVERHEAD", 1.0),
        )
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_signature = None
        self._last_broadcast = 0.0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="audio-engine", daemon=True)
        self._thread.start()
        log.info("Audio engine started (adapter=%s)", self.app.config.get("TTS_ADAPTER", "browser"))

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3)

    # ------------------------------------------------------------------ loop
    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_once(datetime.now().replace(microsecond=0))
            except Exception:  # keep the scheduler alive no matter what
                log.exception("Audio engine poll failed")
            self._stop_event.wait(1.0)

    def run_once(self, at: datetime) -> dict | None:
        with self.app.app_context():
            cfg = build_audio_config(at)
            rooms = sort_room_names(
                row.room_name
                for row in LectureSession.query.filter_by(status="IN_PROGRESS").all()
            )
            announcement = self.engine.tick(cfg, rooms)
            if announcement is not None:
                log.info("Announcing: %s", announcement.text)
                socketio.emit(
                    "audio:announce",
                    {
                        "text": announcement.text,
                        "rooms": list(announcement.rooms),
                        "at": iso(announcement.at),
                        "revision": revisions.current(),
                    },
                    namespace="/",
                )

            described = self.engine.describe(cfg)
            signature = _state_signature(cfg, described)
            now_monotonic = time.monotonic()
            if signature != self._last_signature or (now_monotonic - self._last_broadcast) > 10:
                self._last_signature = signature
                self._last_broadcast = now_monotonic
                socketio.emit("audio:state", build_audio_state(self.app, at), namespace="/")

            db.session.remove()
            return described
