# Test plan and acceptance record

Project: **Smart Lecture Room Notification System v3.0**
Scope: the pilot build in this repository (SQLite default, MySQL 8 production target).

This document maps every functional requirement to an automated test and adds the manual checks
that automation cannot cover: real hardware audio, the projector, browsers, accessibility with a
screen reader, and operational recovery.

---

## 1. How to run the automated suite

```powershell
cd backend
python -m pytest -q
```

Expected result on a clean checkout: **73 passed**. Tests use a temporary SQLite database per test,
seeded demo data, `AUDIO_ENABLED=False`, and `DISPLAY_REQUIRE_TOKEN=False`. They never touch the
pilot database.

Useful variants:

```powershell
python -m pytest -q tests\test_api.py
python -m pytest -q tests\test_audio_engine.py -v
python -m pytest -q -k "parallel or reconnect"
```

Front-end build check (only needed after changing `frontend/src`):

```powershell
cd frontend
npm ci
npm run build
```

The build must finish without errors and write `backend/app/static/index.html` plus hashed assets.

---

## 2. Requirement traceability — automated tests

Legend: **R** = requirement area, **Test** = test function in `backend/tests/`.

### 2.1 Room ordering and identification (D1/D4)

| ID | Requirement | Automated test |
| --- | --- | --- |
| R1.1 | Room numbers are parsed from names (`KLH9` → 9, `LH-205-B` → 205, non-numeric → 0) | `test_rooms.py::test_parse_room_number` (9 cases) |
| R1.2 | Rooms sort numerically, not alphabetically | `test_numeric_ascending_sort`, `test_klh9_before_klh10_before_klh101` |
| R1.3 | Non-numeric names sort deterministically before numbered rooms | `test_non_numeric_rooms_sort_first` |
| R1.4 | Ties are case-insensitive and deterministic (`KLH101a` before `KLH101b`) | `test_ties_are_deterministic_and_case_insensitive` |
| R1.5 | `/api/rooms` returns numeric order in the API | `test_api.py::test_rooms_are_numerically_sorted` |

### 2.2 Authentication, sessions and RBAC (D2/D5)

| ID | Requirement | Automated test |
| --- | --- | --- |
| R2.1 | Correct credentials sign in; `/auth/me` returns the officer | `test_login_and_me` |
| R2.2 | Wrong password is rejected without revealing which field failed | `test_login_rejects_bad_password` |
| R2.3 | Anonymous users cannot read sessions or tick a room | `test_anonymous_access_is_denied` |
| R2.4 | Logout invalidates the session | `test_logout_ends_session` |
| R2.5 | An officer cannot change admin-only settings (lecture start) | `test_officer_cannot_change_lecture_start` |
| R2.6 | An officer may change only the repeat interval | `test_officer_can_change_interval` |
| R2.7 | An admin can change the full schedule | `test_admin_can_change_settings` |
| R2.8 | Invalid times are rejected with a 400 | `test_invalid_time_is_rejected` |
| R2.9 | Deactivated accounts lose access on their next request | `test_deactivated_officer_loses_access` |
| R2.10 | Health endpoint is public and reports `ok` | `test_health` |

### 2.3 Tick / end lifecycle and the one-active-session rule (D1/D2)

| ID | Requirement | Automated test |
| --- | --- | --- |
| R3.1 | Ticking a room creates an `IN_PROGRESS` session visible in the list | `test_tick_and_end_lifecycle` |
| R3.2 | A second active session for the same room is rejected with 409 | `test_second_active_session_is_rejected` |
| R3.3 | A room can be ticked again after its session ends | `test_room_can_be_reticked_after_end` |
| R3.4 | Unknown rooms are rejected | `test_unknown_room_is_rejected` |
| R3.5 | Lecturer name is optional | `test_lecturer_name_is_optional` |
| R3.6 | Ending an unknown session returns 404 | `test_end_unknown_session_returns_404` |
| R3.7 | **Ten concurrent ticks produce exactly one 201 and nine 409s** | `test_ten_parallel_ticks_only_one_succeeds` |
| R3.8 | The database itself rejects duplicates (stored generated column + UNIQUE) | Covered by R3.2/R3.7; the constraint is documented in `docs/DATABASE.md`. Verify manually with SQL in section 5.3. |

### 2.4 Public payload privacy (D2/D4)

| ID | Requirement | Automated test |
| --- | --- | --- |
| R4.1 | Public session JSON omits officer IDs, usernames and staff identifiers | `test_public_session_payload_has_no_staff_identifiers` |
| R4.2 | Socket `session:created` payload also omits `ticked_by` | `test_session_created_event_carries_increasing_revision` |

### 2.5 Audio scheduling engine (D3)

| ID | Requirement | Automated test |
| --- | --- | --- |
| R5.1 | Silent before the listening window | `test_silent_before_window` |
| R5.2 | Announces inside the window in numeric room order | `test_announces_inside_window_in_numeric_order` |
| R5.3 | A cycle is announced at most once | `test_does_not_repeat_within_same_cycle` |
| R5.4 | The next cycle repeats the current rooms | `test_repeats_on_next_cycle` |
| R5.5 | Silent after the window closes | `test_silent_after_window` |
| R5.6 | A room ticked mid-cycle waits for the next cycle | `test_room_that_ticks_mid_cycle_waits_for_next_cycle` |
| R5.7 | A room ended before the cycle is not announced | `test_room_ended_before_cycle_is_not_announced` |
| R5.8 | Skip-if-busy: never overlap an announcement already playing | `test_skip_if_busy_never_overlaps`, `test_engine_estimated_busy_skips_next_cycle` |
| R5.9 | +15 min keeps audio alive past the normal window | `test_extension_keeps_audio_alive_past_normal_window` |
| R5.10 | Pause is silent and reports `PAUSED` | `test_paused_is_silent_and_reports_paused` |
| R5.11 | Next-cycle time is reported for the UI countdown | `test_next_cycle_is_reported` |
| R5.12 | Manual test announcement bypasses the window | `test_manual_test_announcement_bypasses_window` |
| R5.13 | Announcement text omits an empty lecturer name and keeps room order | `test_compose_announcement_omits_empty_name_but_keeps_rooms` |
| R5.14 | API pause / resume / extend change state correctly | `test_pause_resume_and_extend` |
| R5.15 | Test announcement is rejected when nothing is in progress | `test_test_announcement_requires_rooms` |

### 2.6 Real-time protocol and reconnect (D2/D4)

| ID | Requirement | Automated test |
| --- | --- | --- |
| R6.1 | A socket connection immediately receives an authoritative snapshot | `test_socket_snapshot_on_connect` |
| R6.2 | `session:created` carries a strictly increasing revision | `test_session_created_event_carries_increasing_revision` |
| R6.3 | `session:ended` identifies the ended session and room | `test_session_ended_event` |
| R6.4 | Reconnect after an end leaves no ghost room | `test_reconnect_snapshot_has_no_ghost_rooms` |
| R6.5 | A display can connect without a login when tokens are disabled | `test_display_can_connect_without_login_when_token_not_required` |
| R6.6 | Display-snapshot REST access requires a valid token when enabled | Manual case M6.4 (config-dependent) |

### 2.7 Audit trail and administration (D5)

| ID | Requirement | Automated test |
| --- | --- | --- |
| R7.1 | Login/tick/end/audio/settings actions are written to the audit log | `test_audit_records_actions` |
| R7.2 | The audit log is admin-only | `test_audit_is_admin_only` |
| R7.3 | Audit filters by room/action/officer/date work | `test_audit_filters` |
| R7.4 | Admin can create an officer; officers cannot | `test_admin_creates_officer_and_officer_cannot` |
| R7.5 | Duplicate usernames are rejected | `test_duplicate_username_rejected` |
| R7.6 | An admin cannot deactivate their own account | `test_admin_cannot_deactivate_self` |
| R7.7 | Admin can add, rename and deactivate rooms; officers cannot | `test_admin_manages_rooms` |
| R7.8 | A display token and read-only snapshot are issued | `test_display_token_and_snapshot` |

### 2.8 Room switch (D1/D2/D4)

| ID | Requirement | Automated test |
| --- | --- | --- |
| R8.1 | Switching keeps the same session, start time, lecturer and officer, and changes only the room | `test_api.py::test_switch_room_keeps_the_same_session` |
| R8.2 | A switch to a room that already has an active session is rejected with 409 and changes nothing | `test_switch_to_busy_room_is_rejected` |
| R8.3 | Unknown and inactive target rooms are rejected with 404 | `test_switch_to_unknown_or_inactive_room_is_rejected` |
| R8.4 | Switching to the current room is rejected with 400 | `test_switch_to_same_room_is_rejected` |
| R8.5 | Only an in-progress session can be switched | `test_switch_ended_session_is_rejected` |
| R8.6 | Anonymous users cannot switch rooms | `test_anonymous_cannot_switch_rooms` |
| R8.7 | The switch is audited as `SWITCH_ROOM` with from/to rooms and session ID | `test_switch_room_is_audited` |
| R8.8 | `session:switched` carries the updated session, from/to rooms, notice and a higher revision | `test_realtime.py::test_session_switched_event` |
| R8.9 | A reconnect snapshot carries the recent switch notice, so late displays still see it | `test_reconnect_snapshot_carries_recent_switch_notice` |
| R8.10 | The display REST snapshot includes `switch_notice` while it is fresh | `test_api.py::test_display_snapshot_carries_recent_switch_notice` |
| R8.11 | The switch announcement speaks the custom text “KLH101 changed to KLH102.” | `test_audio_engine.py::test_switch_announcement_plays_custom_text` |
| R8.12 | If audio is busy the announcement is skipped but the switch still completes | `test_switch_announcement_skips_when_audio_is_busy` |

---

## 3. Manual acceptance cases

Run these on the pilot hardware before the first lecture and again at handover. Record pass/fail and
the tester's initials. These cover the gaps automation cannot: actual audio, real browsers, sign-in
UX, accessibility, and recovery.

### 3.1 Functional acceptance

| ID | Steps | Expected result | Pass |
| --- | --- | --- | --- |
| M1.1 | Open `http://<server>/#/login`, sign in as an officer. | Console loads, header shows **Live**, room grid sorted `KLH9`, `KLH10`, `KLH101`… | ☐ |
| M1.2 | Select a room, type a lecturer name, press **Mark in progress**, confirm. | Card shows **In progress** + name; live list updates; toast offers **Undo** for 10 s. | ☐ |
| M1.3 | While the display is open, repeat M1.2 for a different room. | Display shows the new room within ~1 s without a refresh. | ☐ |
| M1.4 | Press **End** on a room and confirm. | Card returns to available; room disappears from the display immediately. | ☐ |
| M1.5 | End a room, then press **Undo** within 10 s. | Session is restored and reappears on the display. | ☐ |
| M1.6 | Try to tick the same room from two browser windows at once. | One succeeds; the other shows “already in progress” (409), no duplicate. | ☐ |
| M1.7 | Sign out; press Back; try the console URL directly. | Login is required again; no cached private data is shown. | ☐ |
| M1.8 | Resize the console to phone width. | Grid and controls stack; no horizontal scrolling; buttons remain reachable. | ☐ |
| M1.9 | In the live register press **Switch** on an in-progress room and choose a free room. | The row moves to the new room; start time, lecturer and officer are unchanged; a success toast confirms the move. | ☐ |
| M1.10 | Open **Switch** when every other room is in progress. | No free room can be chosen and a clear message is shown; the session is unchanged. | ☐ |
| M1.11 | Switch to a room that another officer ticked a moment earlier. | Rejected with “already in progress”; no duplicate row and no room change. | ☐ |

### 3.2 Audio acceptance

| ID | Steps | Expected result | Pass |
| --- | --- | --- | --- |
| M2.1 | Admin → Settings → **Set start to now** → Save. | Audio card shows an active window starting now; display footer shows the end time. | ☐ |
| M2.2 | Tick 2–3 rooms, wait for the next cycle. | Display speaks all room names in numeric order, once. | ☐ |
| M2.3 | Wait through another cycle. | The same list repeats at the configured interval. | ☐ |
| M2.4 | Press **Pause**, wait through a cycle, press **Resume**. | No announcement while paused; no backlog is played on resume; the next cycle speaks normally. | ☐ |
| M2.5 | Press **+15 min**. | Window end moves 15 minutes later; display footer updates. Pressing again extends further. | ☐ |
| M2.6 | Let the window close, then press **+15 min**. | Window reopens from now + 15 minutes and announcements resume. | ☐ |
| M2.7 | Try to tick a room while the display is speaking. | The new room is not announced mid-sentence; it waits for the next cycle. | ☐ |
| M2.8 | Press **Test** outside the window. | The current room list is spoken immediately and a `TEST_ANNOUNCE` audit entry appears. | ☐ |
| M2.9 | Click **Tap to enable sound**, then reload the display. | Sound requires the one-time gesture again (expected autoplay policy); toggle shows **Sound on**. | ☐ |
| M2.10 | Mute the display, wait a cycle, unmute. | No sound while muted; unmuting does not replay missed cycles. | ☐ |
| M2.11 | Listen from the far end of the corridor / actual speaker. | Speech is intelligible above normal background noise; adjust speaker volume if not. | ☐ |
| M2.12 | Switch a room while audio is idle and the display sound is enabled. | The display speaks “KLH101 changed to KLH102.” immediately, even outside the normal cycle. | ☐ |
| M2.13 | Switch a room while the display is speaking. | The extra announcement is skipped (no overlap), but the switch and the display banner still happen. | ☐ |

### 3.3 Display acceptance

| ID | Steps | Expected result | Pass |
| --- | --- | --- | --- |
| M3.1 | Open the display link on the kiosk PC in kiosk mode. | Full-screen, no browser chrome; large type; read-only. | ☐ |
| M3.2 | Check status marks. | Every status uses an icon **and** a word, not colour alone. | ☐ |
| M3.3 | Check the clock and date. | Matches the server; updates every second. | ☐ |
| M3.4 | Tick more rooms than fit on the screen. | Display paginates automatically; every room is shown over time; dots and `1 / n` counter are visible. | ☐ |
| M3.4b | Resize the browser window (or open the display on a laptop, then a 1080p screen). | Columns and rows change with the screen; the page holds as many cards as fit and never scrolls vertically. | ☐ |
| M3.5 | Stop the backend for ~30 s, then restart. | Footer shows **RECONNECTING**; on restart it reconnects and shows a correct snapshot with no ghosts. | ☐ |
| M3.6 | With `DISPLAY_REQUIRE_TOKEN=true`, open `/#/display` without a token. | Display shows an error/access message and does not reveal room data. | ☐ |
| M3.7 | Open a display link with a tampered token. | Access denied with 401; no data leaked. | ☐ |
| M3.8 | Leave the display running for two hours. | Clock stays accurate; no memory growth or frozen UI; announcements still work. | ☐ |
| M3.9 | Switch a room while the display is open. | An amber **Room change** banner reads **KLH101 switched to KLH102**, the card shows the new room, and the banner clears after about 90 seconds. | ☐ |
| M3.10 | Reload or reconnect the display during the 90-second window. | The same banner returns from the snapshot; no stale old room remains. | ☐ |

### 3.4 Administration acceptance

| ID | Steps | Expected result | Pass |
| --- | --- | --- | --- |
| M4.1 | Admin → Officers → create an officer; sign in as them. | New account works; role shown correctly. | ☐ |
| M4.2 | Reset an officer's password; sign in with the old and new password. | Old fails, new succeeds. | ☐ |
| M4.3 | Deactivate an officer who is signed in; have them act. | They are signed out on the next request. | ☐ |
| M4.4 | Try to deactivate/demote your own admin account. | Blocked with a clear message. | ☐ |
| M4.5 | Admin → Rooms → add a room, rename a free room, deactivate it. | List updates; deactivated room disappears from the console; history remains. | ☐ |
| M4.6 | Try to rename a room while it is in progress. | Blocked with a clear message. | ☐ |
| M4.7 | Change lecture start / duration / window / interval. | Preview and audio card update; the change is audited. | ☐ |
| M4.8 | Admin → Audit log; filter by room, action, officer, date. | Only matching rows appear; pagination works; newest first. | ☐ |
| M4.9 | Check the audit log after M1.2–M2.8. | TICK, END, PAUSE, RESUME, EXTEND, SETTINGS and TEST_ANNOUNCE are attributed to the right officer. | ☐ |
| M4.10 | Set the A/V system to the wrong time; check the display and scheduler. | Server time is authoritative; correct the clock and restart between lectures. | ☐ |
| M4.11 | Admin → Audit log after a room switch. | A `SWITCH_ROOM` row shows the destination room, `KLH101 → KLH102`, and the officer who made the change. | ☐ |

### 3.5 Operational recovery

| ID | Steps | Expected result | Pass |
| --- | --- | --- | --- |
| M5.1 | Stop Gunicorn / `run.py`, then start it again. | Service returns; displays reconnect automatically; console shows Live. | ☐ |
| M5.2 | Restart the database. | App reconnects; health is `ok`; no data loss. | ☐ |
| M5.3 | In MySQL run `SHOW CREATE TABLE sessions\G`. | `UNIQUE KEY uq_sessions_active_room (active_room_name)` is present. | ☐ |
| M5.4 | Back up the database and restore into a scratch DB. | App boots against the restore with the same officers, rooms and settings. | ☐ |
| M5.5 | Follow the paper fallback for one arrival. | Desk can operate without the system; the note reaches the administrator. | ☐ |

---

## 4. Accessibility acceptance (WCAG 2.1 AA)

Automated evidence: Lighthouse on `#/console` and `#/display` reports **Accessibility 100,
Best Practices 100, SEO 100**, with zero failed audits. Manual checks below cover what Lighthouse
cannot.

| ID | Criterion | Check | Pass |
| --- | --- | --- | --- |
| A1 | 1.3.1 / 1.4.1 | Status is conveyed by icon + word, never colour alone. Check with a greyscale filter. | ☐ |
| A2 | 1.4.3 | Console text contrast ≥ 4.5:1; display text high contrast. Spot-check with a contrast tool. | ☐ |
| A3 | 1.4.4 | Browser zoom to 200%: no content clipped; controls remain usable. | ☐ |
| A4 | 1.4.10 | At 320 px width: no horizontal scroll; content reflows. | ☐ |
| A5 | 2.1.1 | Complete a tick and an end using only the keyboard (`Tab`, `Enter`, `Esc`, `/`, `Space`). | ☐ |
| A6 | 2.4.7 | Every interactive element shows a visible focus ring. | ☐ |
| A7 | 2.4.3 | Tab order follows the visual order; the skip link works. | ☐ |
| A8 | 3.3.1 | Invalid form input shows a specific, programmatically associated error. | ☐ |
| A9 | 4.1.2 | Buttons and inputs have accessible names; room cards announce room, status and lecturer. | ☐ |
| A10 | 4.1.3 | Toast, live-list and audio changes are announced via `aria-live` without being chatty. | ☐ |
| A11 | 2.3.3 | With OS “reduce motion” enabled, pulse/animation is suppressed; no essential motion. | ☐ |
| A12 | 2.5.5 | Touch targets on the console are at least 44 × 44 px on a tablet. | ☐ |
| A13 | Screen reader | With NVDA or VoiceOver: sign in, select a room, confirm, end; the toast and status are announced. | ☐ |
| A14 | 1.2 / audio | Spoken announcements are also visible as text on the display (no audio-only information). | ☐ |

---

## 5. Security and reliability checks

| ID | Check | Expected | Pass |
| --- | --- | --- | --- |
| S1 | Anonymous `GET /api/sessions`, `POST /api/sessions`, `GET /api/audit`. | `401`; no data returned. | ☐ |
| S2 | Officer calls an admin endpoint (`POST /api/officers`). | `403`. | ☐ |
| S3 | Ten rapid wrong passwords. | Throttled after 10 failures per username+IP per 5 minutes. | ☐ |
| S4 | Session left idle for 15+ minutes. | Next request requires sign-in again. | ☐ |
| S5 | Inspect the session cookie. | `HttpOnly`, `SameSite=Lax`; `Secure` when `COOKIE_SECURE=true`. | ☐ |
| S6 | Tick and end concurrently from two tabs. | No duplicate active row; one request gets 409. | ☐ |
| S7 | Tamper with the display token. | 401; cannot mutate state. | ☐ |
| S8 | Error responses in production. | Generic JSON, no stack traces or SQL. | ☐ |
| S9 | `SECRET_KEY`, DB password, and default passwords. | Changed from demo values before go-live. | ☐ |
| S10 | MySQL `SHOW CREATE TABLE sessions`. | Unique generated-column constraint exists. | ☐ |
| S11 | Reconnect after a network drop on the display. | Snapshot replaces state; no ghost rooms; the revision guard holds. | ☐ |
| S12 | Check the browser console during a full flow. | No unexpected errors (the expected 401 on the login page before sign-in is allowed). | ☐ |

---

## 6. Performance targets

| Metric | Target | How to check |
| --- | --- | --- |
| Tick/end round trip on the LAN | < 300 ms | Browser network panel. |
| Display update after tick | < 1 s | Observe both screens; socket event, not polling. |
| Console first load on the LAN | < 2 s | Lighthouse / network panel. |
| Page weight (gzip) | ~75 KB JS + 8 KB CSS | `npm run build` output. |
| Concurrent officers | 10+ on one worker | `test_ten_parallel_ticks_only_one_succeeds` plus a small load test. |
| Long-running display | 8 hours, no freeze/leak | Leave the kiosk running; check responsiveness and memory. |
| Database growth | < 20 MB per academic term at pilot volume | Row counts on `sessions` and `audit_log`. |

---

## 7. Defect log template

| # | Date/time | Environment | Steps to reproduce | Expected | Actual | Severity | Owner | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | | | | | | | | |

Severity: **S1** system unusable during a lecture · **S2** workaround exists but data/audit is
wrong · **S3** cosmetic or minor · **S4** suggestion.

Any S1 or S2 must be logged and reported to the administrator immediately; the paper fallback in
`docs/PILOT_RUNBOOK.md` applies until it is cleared.

---

## 8. Entry / exit criteria

**Entry criteria**

- Automated suite green (73 passed).
- Production front-end build present and served.
- Test database seeded; demo credentials known.
- Kiosk PC, speaker and network available for manual checks.

**Exit criteria**

- All automated tests pass.
- All M1–M5 cases pass or have an accepted, documented workaround.
- All A1–A14 checks pass.
- No open S1/S2 defects.
- `SECRET_KEY`, database password and seeded passwords changed.
- Backup and restore tested.
- Runbook printed at the security desk; administrator and officers briefed.

**Sign-off**

| Role | Name | Signature | Date |
| --- | --- | --- | --- |
| ICT administrator | | | |
| Security supervisor | | | |
| Pilot coordinator | | | |
