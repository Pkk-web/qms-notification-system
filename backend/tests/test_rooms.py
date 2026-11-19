from __future__ import annotations

import pytest

from app.rooms import parse_room_number, room_sort_key, sort_room_names


@pytest.mark.parametrize(
    "name,expected",
    [
        ("KLH9", 9),
        ("KLH10", 10),
        ("KLH101", 101),
        ("KLH101A", 101),
        ("klh101", 101),
        ("A9", 9),
        ("ROOM", 0),
        ("", 0),
        ("LH-205-B", 205),
    ],
)
def test_parse_room_number(name, expected):
    assert parse_room_number(name) == expected


def test_numeric_ascending_sort():
    rooms = ["KLH101", "KLH9", "KLH10", "KLH205", "KLH102"]
    assert sort_room_names(rooms) == ["KLH9", "KLH10", "KLH101", "KLH102", "KLH205"]


def test_non_numeric_rooms_sort_first():
    assert sort_room_names(["KLH101", "ROOM", "A9"]) == ["ROOM", "A9", "KLH101"]


def test_ties_are_deterministic_and_case_insensitive():
    assert sort_room_names(["KLH101b", "KLH101a"]) == ["KLH101a", "KLH101b"]
    assert room_sort_key("klh101") == room_sort_key("KLH101")


def test_klh9_before_klh10_before_klh101():
    assert sort_room_names(["KLH101", "KLH10", "KLH9"]) == ["KLH9", "KLH10", "KLH101"]
