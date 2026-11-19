"""Text-to-speech adapters.

`browser` is the default: the public display speaks the broadcast text with
the Web Speech API, so no server-side TTS package is needed. `command` runs
any local TTS command (espeak, PowerShell SAPI, a cloud CLI). `pyttsx3` is
optional.
"""
from __future__ import annotations

import logging
import shlex
import subprocess
import threading
from typing import Sequence

log = logging.getLogger(__name__)


class BasePlayer:
    def play(self, text: str, rooms: Sequence[str]) -> None:  # pragma: no cover
        raise NotImplementedError

    def is_busy(self) -> bool:
        return False

    def stop(self) -> None:
        pass


class LogPlayer(BasePlayer):
    """Silent player for tests and headless servers."""

    def play(self, text: str, rooms: Sequence[str]) -> None:
        log.info("AUDIO: %s", text)


class BrowserPlayer(BasePlayer):
    """No server audio; display clients speak. Busy time is tracked by engine."""

    def play(self, text: str, rooms: Sequence[str]) -> None:
        log.info("AUDIO (browser): %s", text)


class CommandPlayer(BasePlayer):
    def __init__(self, command: str) -> None:
        if not command:
            raise ValueError("TTS_COMMAND is required when TTS_ADAPTER=command")
        self.command = command
        self._process: subprocess.Popen | None = None
        self._lock = threading.Lock()

    def play(self, text: str, rooms: Sequence[str]) -> None:
        with self._lock:
            try:
                if "{text}" in self.command:
                    parts = [part.replace("{text}", text) for part in shlex.split(self.command)]
                else:
                    parts = shlex.split(self.command) + [text]
                self._process = subprocess.Popen(parts, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                log.exception("TTS command failed")

    def is_busy(self) -> bool:
        with self._lock:
            return self._process is not None and self._process.poll() is None

    def stop(self) -> None:
        with self._lock:
            if self._process and self._process.poll() is None:
                self._process.terminate()


class Pyttsx3Player(BasePlayer):
    def __init__(self) -> None:
        import pyttsx3  # noqa: F401  (imported lazily by design)

        self._engine = pyttsx3.init()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def play(self, text: str, rooms: Sequence[str]) -> None:
        if self.is_busy():
            return
        with self._lock:
            self._thread = threading.Thread(target=self._speak, args=(text,), daemon=True)
            self._thread.start()

    def _speak(self, text: str) -> None:
        try:
            self._engine.say(text)
            self._engine.runAndWait()
        except Exception:
            log.exception("pyttsx3 failed")

    def is_busy(self) -> bool:
        return self._thread is not None and self._thread.is_alive()


def make_player(adapter: str, command: str = "") -> BasePlayer:
    adapter = (adapter or "browser").strip().lower()
    if adapter == "log":
        return LogPlayer()
    if adapter == "command":
        return CommandPlayer(command)
    if adapter == "pyttsx3":
        try:
            return Pyttsx3Player()
        except Exception:
            log.exception("pyttsx3 unavailable; falling back to browser TTS")
            return BrowserPlayer()
    if adapter != "browser":
        log.warning("Unknown TTS_ADAPTER %r, using browser", adapter)
    return BrowserPlayer()
