from __future__ import annotations

import threading


def tick(client, room="KLH101", lecturer=None):
    payload = {"room_name": room}
    if lecturer:
        payload["lecturer_name"] = lecturer
    return client.post("/api/sessions", json=payload)


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


# ----------------------------------------------------------------------- auth
def test_login_rejects_bad_password(client):
    assert client.post("/api/auth/login", json={"username": "otieno", "password": "nope"}).status_code == 401


def test_login_and_me(client):
    response = client.post("/api/auth/login", json={"username": "otieno", "password": "Officer@123"})
    assert response.status_code == 200
    assert response.get_json()["officer"]["role"] == "OFFICER"
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.get_json()["officer"]["username"] == "otieno"


def test_anonymous_access_is_denied(client):
    assert client.get("/api/sessions").status_code == 401
    assert tick(client).status_code == 401


def test_logout_ends_session(auth_client):
    assert auth_client.post("/api/auth/logout").status_code == 200
    assert auth_client.get("/api/auth/me").status_code == 401


# --------------------------------------------------------------------- rooms
def test_rooms_are_numerically_sorted(auth_client):
    response = auth_client.get("/api/rooms")
    assert response.status_code == 200
    names = [room["room_name"] for room in response.get_json()["rooms"]]
    assert names[:3] == ["KLH9", "KLH10", "KLH101"]


# ------------------------------------------------------------------ sessions
def test_tick_and_end_lifecycle(auth_client):
    created = tick(auth_client, "KLH101", "Mr Paul")
    assert created.status_code == 201
    session = created.get_json()["session"]
    assert session["room_name"] == "KLH101"
    assert session["lecturer_name"] == "Mr Paul"
    assert session["status"] == "IN_PROGRESS"

    listed = auth_client.get("/api/sessions").get_json()["sessions"]
    assert [row["room_name"] for row in listed] == ["KLH101"]

    ended = auth_client.post(f"/api/sessions/{session['id']}/end")
    assert ended.status_code == 200
    assert ended.get_json()["session"]["status"] == "ENDED"
    assert auth_client.get("/api/sessions").get_json()["sessions"] == []


def test_second_active_session_is_rejected(auth_client):
    assert tick(auth_client, "KLH101").status_code == 201
    duplicate = tick(auth_client, "KLH101")
    assert duplicate.status_code == 409
    assert "already in progress" in duplicate.get_json()["error"]


def test_room_can_be_reticked_after_end(auth_client):
    first = tick(auth_client, "KLH101").get_json()["session"]
    auth_client.post(f"/api/sessions/{first['id']}/end")
    assert tick(auth_client, "KLH101").status_code == 201


def test_unknown_room_is_rejected(auth_client):
    assert tick(auth_client, "NOPE999").status_code == 404


def test_lecturer_name_is_optional(auth_client):
    response = tick(auth_client, "KLH102")
    assert response.status_code == 201
    assert response.get_json()["session"]["lecturer_name"] is None


def test_end_unknown_session_returns_404(auth_client):
    assert auth_client.post("/api/sessions/99999/end").status_code == 404


def test_public_session_payload_has_no_staff_identifiers(auth_client):
    payload = tick(auth_client, "KLH101").get_json()["session"]
    for forbidden in ("ticked_by", "ended_by", "staff_number", "unit_code"):
        assert forbidden not in payload


# --------------------------------------------------------------- switch room
def test_switch_room_keeps_the_same_session(auth_client):
    created = tick(auth_client, "KLH101", "Mr Paul").get_json()["session"]

    response = auth_client.post(
        f"/api/sessions/{created['id']}/switch",
        json={"room_name": "KLH102"},
    )
    assert response.status_code == 200
    data = response.get_json()

    assert data["session"]["id"] == created["id"]
    assert data["session"]["room_name"] == "KLH102"
    assert data["session"]["lecturer_name"] == "Mr Paul"
    assert data["session"]["started_at"] == created["started_at"]
    assert data["from_room"] == "KLH101"
    assert data["to_room"] == "KLH102"
    assert data["switch_notice"]["text"] == "KLH101 switched to KLH102"
    assert data["announcement"]["text"] == "KLH101 changed to KLH102."

    listed = auth_client.get("/api/sessions").get_json()["sessions"]
    assert [row["room_name"] for row in listed] == ["KLH102"]


def test_switch_to_busy_room_is_rejected(auth_client):
    first = tick(auth_client, "KLH101").get_json()["session"]
    tick(auth_client, "KLH102")

    response = auth_client.post(
        f"/api/sessions/{first['id']}/switch",
        json={"room_name": "KLH102"},
    )
    assert response.status_code == 409
    assert "already in progress" in response.get_json()["error"]

    listed = auth_client.get("/api/sessions").get_json()["sessions"]
    assert {row["room_name"] for row in listed} == {"KLH101", "KLH102"}


def test_switch_to_unknown_or_inactive_room_is_rejected(admin_client):
    session = admin_client.post("/api/sessions", json={"room_name": "KLH101"}).get_json()["session"]

    unknown = admin_client.post(
        f"/api/sessions/{session['id']}/switch",
        json={"room_name": "NOPE999"},
    )
    assert unknown.status_code == 404

    room = next(
        row for row in admin_client.get("/api/rooms").get_json()["rooms"] if row["room_name"] == "KLH102"
    )
    admin_client.patch(f"/api/rooms/{room['id']}", json={"active": False})
    inactive = admin_client.post(
        f"/api/sessions/{session['id']}/switch",
        json={"room_name": "KLH102"},
    )
    assert inactive.status_code == 404


def test_switch_to_same_room_is_rejected(auth_client):
    session = tick(auth_client, "KLH101").get_json()["session"]
    response = auth_client.post(
        f"/api/sessions/{session['id']}/switch",
        json={"room_name": "KLH101"},
    )
    assert response.status_code == 400


def test_switch_ended_session_is_rejected(auth_client):
    session = tick(auth_client, "KLH101").get_json()["session"]
    auth_client.post(f"/api/sessions/{session['id']}/end")
    response = auth_client.post(
        f"/api/sessions/{session['id']}/switch",
        json={"room_name": "KLH102"},
    )
    assert response.status_code == 409


def test_anonymous_cannot_switch_rooms(client):
    response = client.post("/api/sessions/1/switch", json={"room_name": "KLH102"})
    assert response.status_code == 401


def test_switch_room_is_audited(auth_client, admin_client):
    session = tick(auth_client, "KLH101", "Mr Paul").get_json()["session"]
    auth_client.post(
        f"/api/sessions/{session['id']}/switch",
        json={"room_name": "KLH102"},
    )

    entries = admin_client.get("/api/audit?action=SWITCH_ROOM").get_json()["entries"]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["room_name"] == "KLH102"
    assert entry["detail"]["session_id"] == session["id"]
    assert entry["detail"]["from_room"] == "KLH101"
    assert entry["detail"]["to_room"] == "KLH102"


def test_display_snapshot_carries_recent_switch_notice(auth_client):
    session = tick(auth_client, "KLH101").get_json()["session"]
    auth_client.post(
        f"/api/sessions/{session['id']}/switch",
        json={"room_name": "KLH102"},
    )

    token = auth_client.get("/api/display/token").get_json()["token"]
    snapshot = auth_client.get(f"/api/display/snapshot?token={token}").get_json()
    assert snapshot["switch_notice"]["from_room"] == "KLH101"
    assert snapshot["switch_notice"]["to_room"] == "KLH102"


# ------------------------------------------------------------------ settings
def test_officer_can_change_interval(auth_client):
    response = auth_client.patch("/api/settings", json={"repeat_interval_sec": 120})
    assert response.status_code == 200
    assert response.get_json()["settings"]["repeat_interval_sec"] == 120


def test_officer_cannot_change_lecture_start(auth_client):
    assert auth_client.patch("/api/settings", json={"lecture_start": "08:00"}).status_code == 403


def test_admin_can_change_settings(admin_client):
    response = admin_client.patch(
        "/api/settings",
        json={"lecture_start": "08:00", "lecture_duration_min": 120, "audio_window_min": 45},
    )
    assert response.status_code == 200
    settings = response.get_json()["settings"]
    assert settings["lecture_start"] == "08:00"
    assert settings["lecture_duration_min"] == 120


def test_invalid_time_is_rejected(admin_client):
    assert admin_client.patch("/api/settings", json={"lecture_start": "25:00"}).status_code == 400


# --------------------------------------------------------------------- audio
def test_pause_resume_and_extend(auth_client):
    paused = auth_client.post("/api/audio/pause")
    assert paused.status_code == 200
    assert paused.get_json()["audio_state"]["paused"] is True
    assert paused.get_json()["audio_state"]["state"] == "PAUSED"

    resumed = auth_client.post("/api/audio/resume")
    assert resumed.get_json()["audio_state"]["paused"] is False

    extended = auth_client.post("/api/audio/extend")
    assert extended.status_code == 200
    assert extended.get_json()["audio_state"]["extended"] is True


def test_test_announcement_requires_rooms(auth_client):
    assert auth_client.post("/api/audio/test").status_code == 409
    tick(auth_client, "KLH101")
    response = auth_client.post("/api/audio/test")
    assert response.status_code == 200
    assert response.get_json()["text"] == "KLH101 in progress."


# --------------------------------------------------------------------- audit
def test_audit_records_actions(auth_client, admin_client):
    tick(auth_client, "KLH101", "Mr Paul")
    response = admin_client.get("/api/audit")
    assert response.status_code == 200
    actions = [entry["action"] for entry in response.get_json()["entries"]]
    assert "TICK" in actions
    assert "LOGIN" in actions


def test_audit_is_admin_only(auth_client):
    assert auth_client.get("/api/audit").status_code == 403


def test_audit_filters(admin_client):
    admin_client.post("/api/sessions", json={"room_name": "KLH101"})
    admin_client.post("/api/sessions", json={"room_name": "KLH102"})
    response = admin_client.get("/api/audit?room=KLH102&action=TICK")
    entries = response.get_json()["entries"]
    assert len(entries) == 1
    assert entries[0]["room_name"] == "KLH102"


# ------------------------------------------------------------------- officers
def test_admin_creates_officer_and_officer_cannot(admin_client, auth_client):
    created = admin_client.post(
        "/api/officers",
        json={"name": "Mary Wambui", "username": "mwambui", "password": "StrongPass1", "role": "OFFICER"},
    )
    assert created.status_code == 201
    assert created.get_json()["officer"]["username"] == "mwambui"

    forbidden = auth_client.post(
        "/api/officers",
        json={"name": "Nope", "username": "nope", "password": "StrongPass1"},
    )
    assert forbidden.status_code == 403


def test_duplicate_username_rejected(admin_client):
    response = admin_client.post(
        "/api/officers",
        json={"name": "Another", "username": "otieno", "password": "StrongPass1"},
    )
    assert response.status_code == 409


def test_admin_cannot_deactivate_self(admin_client):
    me = admin_client.get("/api/auth/me").get_json()["officer"]
    response = admin_client.patch(f"/api/officers/{me['id']}", json={"active": False})
    assert response.status_code == 400


def test_deactivated_officer_loses_access(admin_client, auth_client):
    officers = admin_client.get("/api/officers").get_json()["officers"]
    otieno = next(row for row in officers if row["username"] == "otieno")
    assert admin_client.patch(f"/api/officers/{otieno['id']}", json={"active": False}).status_code == 200
    assert auth_client.get("/api/sessions").status_code == 401


# ---------------------------------------------------------------------- rooms
def test_admin_manages_rooms(admin_client, auth_client):
    created = admin_client.post("/api/rooms", json={"room_name": "KLH301"})
    assert created.status_code == 201
    room = created.get_json()["room"]
    assert room["room_number"] == 301

    assert admin_client.patch(f"/api/rooms/{room['id']}", json={"active": False}).status_code == 200
    names = [row["room_name"] for row in auth_client.get("/api/rooms").get_json()["rooms"]]
    assert "KLH301" not in names

    assert auth_client.post("/api/rooms", json={"room_name": "KLH999"}).status_code == 403


# -------------------------------------------------------------------- display
def test_display_token_and_snapshot(auth_client):
    token_response = auth_client.get("/api/display/token")
    assert token_response.status_code == 200
    token = token_response.get_json()["token"]
    snapshot = auth_client.get(f"/api/display/snapshot?token={token}")
    assert snapshot.status_code == 200
    body = snapshot.get_json()
    assert "sessions" in body and "audio_state" in body


# ---------------------------------------------------------------- concurrency
def test_ten_parallel_ticks_only_one_succeeds(app):
    results: list[int] = []
    errors: list[Exception] = []
    barrier = threading.Barrier(10)

    def worker():
        try:
            client = app.test_client()
            assert client.post(
                "/api/auth/login", json={"username": "otieno", "password": "Officer@123"}
            ).status_code == 200
            barrier.wait(timeout=10)
            response = client.post("/api/sessions", json={"room_name": "KLH101"})
            results.append(response.status_code)
        except Exception as exc:  # pragma: no cover - only on infrastructure failure
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert not errors, errors
    assert len(results) == 10
    assert results.count(201) == 1
    assert all(status in {201, 409} for status in results)
