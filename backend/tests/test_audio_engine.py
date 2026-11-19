"""Fake-clock tests for the audio scheduler. No sleeps, no real audio."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.audio.engine import AudioEngine, compose_announcement
from app.settings_store import AudioConfig


class FakePlayer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str]]] = []
        self.busy = False

    def play(self, text, rooms):
        self.calls.append((text, list(rooms)))

    def is_busy(self):
        return self.busy

    def stop(self):
        pass


def make_config(
    at: datetime,
    *,
    start: datetime | None = None,
    window_min: int = 30,
    extended_min: int = 0,
    interval_sec: int = 300,
    paused: bool = False,
) -> AudioConfig:
    base_day = (start or at).replace(hour=7, minute=0, second=0, microsecond=0)
    start = start or base_day
    base_end = start + timedelta(minutes=window_min)
    end = base_end + timedelta(minutes=extended_min)
    return AudioConfig(
        now=at,
        start=start,
        base_end=base_end,
        end=end,
        lecture_end=start + timedelta(hours=3),
        interval_sec=interval_sec,
        window_min=window_min,
        paused=paused,
        extended=extended_min > 0,
    )


DAY = datetime(2026, 11, 9)
START = DAY.replace(hour=7, minute=0)


def at(hour, minute, second=0):
    return DAY.replace(hour=hour, minute=minute, second=second)


@pytest.fixture()
def player():
    return FakePlayer()


@pytest.fixture()
def engine(player):
    return AudioEngine(player, seconds_per_room=2.4, seconds_overhead=1.0)


def test_silent_before_window(engine, player):
    assert engine.tick(make_config(at(6, 59)), ["KLH101"]) is None
    assert player.calls == []
    assert engine.describe(make_config(at(6, 59)))["reason"] == "BEFORE_WINDOW"


def test_announces_inside_window_in_numeric_order(engine, player):
    announcement = engine.tick(make_config(at(7, 0)), ["KLH101", "KLH9", "KLH10"])
    assert announcement is not None
    assert announcement.text == "KLH9 in progress. KLH10 in progress. KLH101 in progress."
    assert announcement.rooms == ("KLH9", "KLH10", "KLH101")
    assert player.calls[0][0] == announcement.text


def test_does_not_repeat_within_same_cycle(engine, player):
    cfg0 = make_config(at(7, 0))
    assert engine.tick(cfg0, ["KLH101"]) is not None
    assert engine.tick(make_config(at(7, 2)), ["KLH101"]) is None
    assert engine.tick(make_config(at(7, 4, 59)), ["KLH101"]) is None
    assert len(player.calls) == 1


def test_repeats_on_next_cycle(engine, player):
    engine.tick(make_config(at(7, 0)), ["KLH101"])
    assert engine.tick(make_config(at(7, 5)), ["KLH101"]) is not None
    assert len(player.calls) == 2


def test_silent_after_window(engine, player):
    assert engine.tick(make_config(at(7, 30)), ["KLH101"]) is None
    assert player.calls == []
    assert engine.describe(make_config(at(7, 30)))["reason"] == "WINDOW_CLOSED"


def test_room_that_ticks_mid_cycle_waits_for_next_cycle(engine, player):
    assert engine.tick(make_config(at(7, 0)), []) is None
    assert engine.tick(make_config(at(7, 2)), ["KLH101"]) is None
    assert engine.tick(make_config(at(7, 5)), ["KLH101"]) is not None


def test_room_ended_before_cycle_is_not_announced(engine, player):
    engine.tick(make_config(at(7, 0)), ["KLH101", "KLH102"])
    # KLH102 ends at 07:04:30; at 07:05 only KLH101 remains.
    announcement = engine.tick(make_config(at(7, 5)), ["KLH101"])
    assert announcement is not None
    assert "KLH102" not in announcement.text


def test_skip_if_busy_never_overlaps(engine, player):
    player.busy = True
    assert engine.tick(make_config(at(7, 0)), ["KLH101"]) is None
    assert engine.skipped_cycles == 1
    assert engine.tick(make_config(at(7, 1)), ["KLH101"]) is None  # same slot consumed
    player.busy = False
    assert engine.tick(make_config(at(7, 5)), ["KLH101"]) is not None


def test_engine_estimated_busy_skips_next_cycle(engine, player):
    # Six rooms with a 60s interval should still be speaking at the next cycle.
    rooms = [f"KLH{i}" for i in range(1, 7)]
    first = engine.tick(make_config(at(7, 0), interval_sec=10), rooms)
    assert first is not None
    assert first.duration_estimate > 10
    assert engine.tick(make_config(at(7, 0, 10), interval_sec=10), rooms) is None
    assert engine.skipped_cycles == 1


def test_extension_keeps_audio_alive_past_normal_window(engine, player):
    assert engine.tick(make_config(at(7, 31)), ["KLH101"]) is None
    assert engine.tick(make_config(at(7, 31), extended_min=15), ["KLH101"]) is not None


def test_paused_is_silent_and_reports_paused(engine, player):
    cfg = make_config(at(7, 5), paused=True)
    assert engine.tick(cfg, ["KLH101"]) is None
    assert player.calls == []
    assert engine.describe(cfg)["state"] == "PAUSED"


def test_next_cycle_is_reported(engine):
    cfg = make_config(at(7, 6))
    described = engine.describe(cfg)
    assert described["state"] == "ACTIVE"
    assert described["next_cycle_at"] == at(7, 10)


def test_manual_test_announcement_bypasses_window(engine, player):
    announcement = engine.play_now(["KLH101"], at(12, 0))
    assert announcement is not None
    assert announcement.text == "KLH101 in progress."
    assert player.calls


def test_switch_announcement_plays_custom_text(engine, player):
    announcement = engine.play_text_now("KLH101 changed to KLH102.", ["KLH102"], at(12, 0))
    assert announcement is not None
    assert announcement.text == "KLH101 changed to KLH102."
    assert announcement.rooms == ("KLH102",)
    assert player.calls == [("KLH101 changed to KLH102.", ["KLH102"])]


def test_switch_announcement_skips_when_audio_is_busy(engine, player):
    assert engine.play_now(["KLH101"], at(12, 0)) is not None
    assert engine.play_text_now("KLH101 changed to KLH102.", ["KLH102"], at(12, 0)) is None
    assert len(player.calls) == 1


def test_compose_announcement_omits_empty_name_but_keeps_rooms():
    assert compose_announcement(["KLH102", "KLH101"]) == "KLH101 in progress. KLH102 in progress."
