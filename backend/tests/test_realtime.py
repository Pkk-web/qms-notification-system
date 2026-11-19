"""Real-time protocol tests: snapshot on connect, revision ordering, reconnect."""
from __future__ import annotations

from app.extensions import socketio


def _snapshot(events):
    return next(event["args"][0] for event in events if event["name"] == "snapshot")


def _login(client):
    assert client.post("/api/auth/login", json={"username": "otieno", "password": "Officer@123"}).status_code == 200


def test_socket_snapshot_on_connect(app, client):
    _login(client)
    ws = socketio.test_client(app, flask_test_client=client)
    assert ws.is_connected()
    snapshot = _snapshot(ws.get_received())
    assert snapshot["sessions"] == []
    assert snapshot["revision"] == 0
    assert snapshot["audio_state"]["state"] in {"ACTIVE", "PAUSED", "SILENT"}
    ws.disconnect()


def test_session_created_event_carries_increasing_revision(app, client):
    _login(client)
    ws = socketio.test_client(app, flask_test_client=client)
    initial = _snapshot(ws.get_received())

    created = client.post("/api/sessions", json={"room_name": "KLH101", "lecturer_name": "Mr Paul"})
    assert created.status_code == 201

    events = ws.get_received()
    event = next(item for item in events if item["name"] == "session:created")
    payload = event["args"][0]
    assert payload["session"]["room_name"] == "KLH101"
    assert payload["revision"] > initial["revision"]
    assert "ticked_by" not in payload["session"]
    ws.disconnect()


def test_session_ended_event(app, client):
    _login(client)
    ws = socketio.test_client(app, flask_test_client=client)
    _snapshot(ws.get_received())

    session = client.post("/api/sessions", json={"room_name": "KLH101"}).get_json()["session"]
    client.post(f"/api/sessions/{session['id']}/end")

    events = ws.get_received()
    ended = next(item for item in events if item["name"] == "session:ended")["args"][0]
    assert ended["session_id"] == session["id"]
    assert ended["room_name"] == "KLH101"
    ws.disconnect()


def test_session_switched_event(app, client):
    _login(client)
    ws = socketio.test_client(app, flask_test_client=client)
    initial = _snapshot(ws.get_received())

    session = client.post("/api/sessions", json={"room_name": "KLH101"}).get_json()["session"]
    client.post(f"/api/sessions/{session['id']}/switch", json={"room_name": "KLH102"})

    events = ws.get_received()
    switched = next(item for item in events if item["name"] == "session:switched")["args"][0]
    assert switched["session"]["id"] == session["id"]
    assert switched["session"]["room_name"] == "KLH102"
    assert switched["from_room"] == "KLH101"
    assert switched["to_room"] == "KLH102"
    assert switched["switch_notice"]["text"] == "KLH101 switched to KLH102"
    assert switched["revision"] > initial["revision"]

    announce = next(item for item in events if item["name"] == "audio:announce")["args"][0]
    assert announce["text"] == "KLH101 changed to KLH102."
    ws.disconnect()


def test_reconnect_snapshot_carries_recent_switch_notice(app, client):
    _login(client)
    session = client.post("/api/sessions", json={"room_name": "KLH101"}).get_json()["session"]
    client.post(f"/api/sessions/{session['id']}/switch", json={"room_name": "KLH102"})

    ws = socketio.test_client(app, flask_test_client=client)
    snapshot = _snapshot(ws.get_received())
    assert snapshot["sessions"][0]["room_name"] == "KLH102"
    assert snapshot["switch_notice"]["from_room"] == "KLH101"
    assert snapshot["switch_notice"]["to_room"] == "KLH102"
    ws.disconnect()


def test_reconnect_snapshot_has_no_ghost_rooms(app, client):
    _login(client)
    ws = socketio.test_client(app, flask_test_client=client)
    _snapshot(ws.get_received())
    session = client.post("/api/sessions", json={"room_name": "KLH101"}).get_json()["session"]
    client.post(f"/api/sessions/{session['id']}/end")
    ws.disconnect()

    ws2 = socketio.test_client(app, flask_test_client=client)
    snapshot = _snapshot(ws2.get_received())
    assert snapshot["sessions"] == []
    ws2.disconnect()


def test_display_can_connect_without_login_when_token_not_required(app):
    ws = socketio.test_client(app)
    assert ws.is_connected()
    snapshot = _snapshot(ws.get_received())
    assert snapshot["building"]["name"] == "Building A"
    ws.disconnect()
