"""Room name parsing and ordering.

The integer part of a room name is the sort key: KLH9 < KLH10 < KLH101.
Names without digits sort first (key 0), then tie-break alphabetically so
ordering is deterministic.
"""
from __future__ import annotations

import re
from typing import Iterable, Protocol, TypeVar

_DIGITS = re.compile(r"\d+")

T = TypeVar("T")


class HasRoom(Protocol):
    room_name: str
    room_number: int


def parse_room_number(room_name: str) -> int:
    """Return the first run of digits in a room name, or 0."""
    match = _DIGITS.search(room_name or "")
    return int(match.group()) if match else 0


def room_sort_key(room_name: str) -> tuple[int, str]:
    """Numeric ascending, with a stable case-insensitive tie-break."""
    return (parse_room_number(room_name), (room_name or "").casefold())


def sort_room_names(room_names: Iterable[str]) -> list[str]:
    return sorted(room_names, key=room_sort_key)


def room_number_for(room_name: str, stored: int | None = None) -> int:
    """Use the stored value when present, otherwise parse the name."""
    return stored if stored is not None else parse_room_number(room_name)


def sort_sessions(sessions: Iterable[T]) -> list[T]:
    """Sort ORM session/room objects by numeric room order."""
    return sorted(
        sessions,
        key=lambda s: (
            room_number_for(getattr(s, "room_name", ""), getattr(s, "room_number", None)),
            (getattr(s, "room_name", "") or "").casefold(),
        ),
    )
