# Smart Lecture Room Notification System

A complete, pilot-ready system for marking a lecturer's arrival in a lecture room and telling the
rest of the building — on a public display and through timed spoken announcements — without the
security officer leaving the desk.

Built to the **v3.0 specification**: React 18 + Vite front end, Flask 3 + Flask-SocketIO back end,
SQLite for the zero-setup pilot and MySQL 8 for production, Argon2id passwords, an audit trail for
every action, and a database-level guarantee that a room cannot be in progress twice.

---

## 1. What it does

**Officer console**

- Choose a room from a numerically sorted grid (`KLH9`, `KLH10`, `KLH101` — not alphabetical).
- Optionally type the lecturer's name.
- One confirmation marks the room in progress; it appears on the display immediately.
- Switch an in-progress lecture to another free room. The session keeps its start time, lecturer
  and officer, and the move is shown and spoken immediately.
- End a session with one click, with a 10-second undo.
- Pause / resume announcements and extend the listening window by 15 minutes.
- Change the repeat interval; admins can change the full schedule.
- Keyboard-first: `/` search, `Enter` confirm, `Esc` cancel, `Space` pause.
- Offline banner: registration is blocked while the socket is down; state reconciles on reconnect.

**Public display**

- Full-screen, high-contrast, large-type room list ordered numerically.
- Icon **and** word for status (never colour alone).
- Live clock and date, LIVE / RECONNECTING indicator, last-update time.
- A room-change banner such as **KLH101 switched to KLH102** stays visible for 90 seconds, including
  for displays that reconnect during the window.
- Fits as many room cards as the screen can hold and paginates the rest. Columns and rows are
  measured from the viewport, so a 1080p wall display shows many more rooms than a laptop and a
  phone shows only a few — never a vertical scrollbar.
- Speaks each announcement through the Web Speech API; the display is the audio endpoint in the
  default `browser` TTS mode, so no server sound card is required.
- Mute control and a one-time **Tap to enable sound** prompt for browser autoplay policies.
- Read-only signed display link, optional in production.

**Administration**

- Officer accounts: create, rename, change role, deactivate/reactivate, reset password.
- Room register: add, rename, deactivate; renaming is blocked while the room is in progress.
- Settings: lecture start, lecture duration, audio window, repeat interval.
- Audit log with date / room / action / officer filters and pagination.
- Safety rails: you cannot deactivate or demote yourself, and the last active admin cannot be removed.

**Audio engine**

- Fixed cycles counted from the lecture start (`floor((now − start) / interval)`).
- A cycle is announced at most once, so a paused, busy, or empty cycle is consumed and the next
  cycle starts fresh — the “skip if busy, announce next cycle” rule is enforced without overlap.
- Pause/resume, +15-minute extension, manual test announcement, skipped-cycle counter.
- Pluggable adapters: `browser` (default), `log`, `command`, `pyttsx3`.

**Reliability and accountability**

- One active session per room enforced by a **UNIQUE stored generated column** in the database,
  not just in application code. Concurrent requests are also serialised with `SELECT … FOR UPDATE`
  and an `IntegrityError` fallback.
- Monotonic revision counter on every state change; clients discard out-of-order events and replace
  state with an authoritative snapshot on every (re)connect.
- Every login, tick, end, room switch, audio change, settings change and account/room change is
  written to the audit log with officer, room, timestamp and detail.
- Individual sessions expire after 15 minutes of inactivity.

**Accessibility**

- WCAG 2.1 AA target: keyboard operation, visible focus rings, labelled controls, status text as
  well as colour, `aria-live` announcements, reduced-motion support, 4.5:1 contrast on console text.
- Lighthouse on the console and display: **Accessibility 100, Best Practices 100, SEO 100**.

---

## 2. Quick start (SQLite, no MySQL needed)

Requirements: Python 3.11+ and, only if you want to change the front end, Node 20+.

### Windows: one-click installer

Double-click **`install.bat`** once. It checks for Python 3.11+, creates `backend\.venv`, installs
the dependencies, writes `backend\.env` with a random `SECRET_KEY`, and creates the database and
demo accounts. It is safe to run again; existing data and `.env` are kept.

Then double-click **`start.bat`** whenever you want to use the system. It starts the server and
opens `http://127.0.0.1:5000` in the default browser. Keep the window open while the system is in
use; press `Ctrl+C` in that window to stop it.

### Manual start (all platforms)

```powershell
cd backend

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
python manage.py seed          # create tables + demo officers/rooms
python run.py                  # http://127.0.0.1:5000
```

On macOS/Linux the only difference is `source .venv/bin/activate`.

The production front-end build is already included in `backend/app/static`. If you change anything
under `frontend/src`, rebuild it:

```powershell
cd frontend
npm install
npm run build                  # writes backend/app/static
```

### Demo accounts

| Role | Username | Password |
| --- | --- | --- |
| Administrator | `admin` | `Admin@123` |
| Security officer | `otieno` | `Officer@123` |

Change these before any real deployment:

```powershell
python manage.py reset-password admin --password "a-new-long-password"
```

### Five-minute demo script

1. Sign in as `otieno`.
2. Tick **KLH101**, add `Mr Paul`, confirm. The toast offers **Undo**.
3. In the top-right menu, choose **Admin** (sign in as `admin` if needed) →
   **Settings** → **Set start to now** → **Save settings**.
   Announcements are now inside the active window. Tick a second room; the public display speaks on
   the next cycle, or press **Test** on the console to speak immediately.
4. Console → **Open display** (or open `#/display`). Keep it on the projector / second monitor.
5. Pause and resume audio from the console; extend the window +15 and show the new end time.
6. In the live register, press **Switch** on KLH101 and choose KLH102. The row moves to KLH102, the
   display shows **KLH101 switched to KLH102**, and the speaker says “KLH101 changed to KLH102.”
7. End a room; it disappears from the display within a fraction of a second.
8. Admin → **Audit log**: show the TICK / SWITCH_ROOM / END / PAUSE / SETTINGS entries attributed to
   each officer.

Outside the audio window the display intentionally shows `Announcements start at 07:00` instead of
speaking. The settings step above is the quickest way to demonstrate audio at any time of day.

---

## 3. Project layout

```text
.
├── install.bat                    Windows one-click installer
├── start.bat                      Windows launcher (starts server + opens browser)
├── backend/
│   ├── app/
│   │   ├── __init__.py            app factory, SPA serving, error handlers
│   │   ├── config.py              environment/config
│   │   ├── models.py              officers, rooms, sessions, settings, audit
│   │   ├── seed.py                idempotent demo data
│   │   ├── settings_store.py      typed settings + audio window maths
│   │   ├── rooms.py               numeric room sort helpers
│   │   ├── auth.py                Argon2id, login/admin decorators
│   │   ├── audit.py               audit helper
│   │   ├── realtime.py            snapshots, events, broadcasters
│   │   ├── realtime_state.py      monotonic revision store
│   │   ├── switch_state.py        short-lived room-switch notice
│   │   ├── serializers.py         public JSON shapes
│   │   ├── api/                   auth, sessions, rooms, settings, audio, admin, display
│   │   ├── audio/                 engine, players, background service
│   │   └── static/                built React app (generated)
│   ├── tests/                     pytest suite (73 tests)
│   ├── instance/                  SQLite database (generated)
│   ├── manage.py                  init-db / seed / reset-password / run
│   ├── run.py                     dev + WSGI entry point
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── pages/                 Login, Console, Display, Admin
│   │   ├── components/            TopBar, Modal, Toast, Icons
│   │   ├── state/                 AuthContext, LiveContext (Socket.IO)
│   │   ├── lib/                   API, time, room sort, hash router
│   │   └── styles.css             design tokens + responsive layout
│   ├── public/robots.txt
│   └── vite.config.js
└── docs/
    ├── DEPLOYMENT.md              MySQL 8 + Nginx + Gunicorn gthread
    ├── PILOT_RUNBOOK.md           day-of operation and fallback
    ├── TEST_PLAN.md               requirement → test traceability
    └── DATABASE.md                schema, constraints, MySQL DDL
```

---

## 4. Configuration

Copy `backend/.env.example` to `backend/.env` and edit. Environment variables override defaults.

| Variable | Default | Purpose |
| --- | --- | --- |
| `SECRET_KEY` | dev placeholder | Signs session cookies and display links. **Change in production.** |
| `DATABASE_URL` | `sqlite:///backend/instance/smart_rooms.db` | `mysql+pymysql://user:pass@host/db?charset=utf8mb4` for MySQL 8. |
| `COOKIE_SECURE` | `false` | Set `true` behind HTTPS. |
| `INACTIVITY_MINUTES` | `15` | Signed-in session lifetime. |
| `DISPLAY_REQUIRE_TOKEN` | `false` | `true` in production; display links are signed and read-only. |
| `DISPLAY_TOKEN_MAX_AGE_SEC` | `2592000` | Display-link lifetime (30 days). |
| `BUILDING_NAME` / `BUILDING_LABEL` | `Building A` / `LECTURE ROOMS` | Display header text. |
| `AUDIO_ENABLED` | `true` | Start the background scheduler. |
| `TTS_ADAPTER` | `browser` | `browser`, `log`, `command`, `pyttsx3`. |
| `TTS_COMMAND` | empty | e.g. `espeak-ng` or `powershell -File C:\tts.ps1 {text}` for `command`. |
| `AUDIO_SECONDS_PER_ROOM` | `2.4` | Busy-time estimate used for skip-if-busy. |
| `AUDIO_SECONDS_OVERHEAD` | `1.0` | Fixed overhead per announcement. |
| `AUTO_INIT_DB` | `true` | Create missing tables at boot. |
| `AUTO_SEED` | `true` | Seed demo data only when the tables are empty. |
| `DEFAULT_*_USERNAME/PASSWORD` | demo values | Initial accounts created by the seed. |

---

## 5. How the audio schedule works

Let `start` be the lecture start (default `07:00`), `interval` the repeat interval (default 300 s)
and `window` the audio window (default 30 min).

```text
slot = floor((now - start) / interval)
```

- Outside `[start, start + window)` the engine is silent (`BEFORE_WINDOW` or `WINDOW_CLOSED`).
- A slot is announced **at most once**. When the slot arrives:
  - paused → the slot is consumed silently;
  - no rooms in progress → consumed silently;
  - player still busy (or the previous announcement's estimated duration has not elapsed) →
    the slot is consumed and counted in `skipped_cycles`;
  - otherwise the room list is read in numeric order and broadcast.
- A room ticked in the middle of a slot waits for the next slot. This is what prevents surprise
  announcements immediately after registration.
- **+15** sets the window end to `max(current end, now) + 15 min`; it never shortens an existing
  window and works after the normal window has closed.
- Changing lecture start, audio window or interval resets the cycle counter so the new timetable
  takes effect immediately.
- The display client also skips an announcement if its own speech engine is still speaking, so two
  cycles can never overlap acoustically.

In the default `browser` mode the server decides *when* and *what*, and every connected display
speaks it. If more than one display has sound enabled, they will all speak; use the mute control on
secondary screens.

---

## 6. API and real-time protocol (summary)

All endpoints are under `/api`. Session endpoints require a signed-in officer; admin endpoints
additionally require `ADMIN`.

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/auth/login`, `/auth/logout` | Sign in/out. Throttled after repeated failures. |
| `GET` | `/auth/me` | Current officer. |
| `GET` | `/sessions` | In-progress sessions, numerical order. |
| `POST` | `/sessions` | Tick a room: `{room_name, lecturer_name?}`. `409` if already active. |
| `POST` | `/sessions/{id}/switch` | Move an in-progress lecture: `{room_name}`. `409` if the target is busy. |
| `POST` | `/sessions/{id}/end` | End a session (`{undo:true}` for the undo toast). |
| `GET` | `/rooms?include_inactive=1` | Room register (admin for inactive). |
| `GET/PATCH` | `/settings` | Read/update schedule; officers may only change the interval. |
| `GET` | `/audio/state` | Full audio state. |
| `POST` | `/audio/pause`, `/resume`, `/extend`, `/test` | Audio controls. |
| `GET/POST/PATCH` | `/officers`, `/officers/{id}` | Admin account management. |
| `POST/PATCH` | `/rooms`, `/rooms/{id}` | Admin room management. |
| `GET` | `/audit` | Admin audit search (`date`, `room`, `action`, `officer_id`, `limit`, `offset`). |
| `GET` | `/display/token`, `/display/snapshot` | Signed read-only display link and snapshot. |
| `GET` | `/health` | Liveness probe. |

Socket.IO (same origin):

- On connect the server emits `snapshot` with `{sessions, audio_state, settings, revision,
  server_now, building, switch_notice}`. The same payload can be requested with `request:snapshot`.
  `switch_notice` is the most recent room switch while it is less than 90 seconds old.
- `session:created`, `session:switched`, `session:ended`, `settings:updated`, `rooms:updated`,
  `audio:state`, `audio:announce` carry a monotonically increasing `revision`.
- Clients ignore any event with `revision <= current` and adopt the next snapshot wholesale, so a
  reconnect cannot leave ghost rooms or missed state.
- The console authenticates with its session cookie; the display uses the signed display token when
  `DISPLAY_REQUIRE_TOKEN=true`.

---

## 7. Security notes

- Argon2id (`time_cost=3`, `memory_cost=64 MiB`, `parallelism=2`) with automatic rehash.
- Server-side session cookie: `HttpOnly`, `SameSite=Lax`, optional `Secure`, 15-minute inactivity
  lifetime, refreshed on activity.
- Login throttling: 10 failures per username+IP per 5 minutes; dummy hash verification keeps timing
  similar for unknown usernames.
- Public session payloads deliberately omit officer IDs, staff numbers and unit codes.
- Display links are signed with `itsdangerous` and scoped to `display`; they cannot mutate state.
- All state-changing requests are JSON and audited; errors return generic JSON without stack traces.
- Set `DISPLAY_REQUIRE_TOKEN=true`, `COOKIE_SECURE=true`, and a strong `SECRET_KEY` in production.

---

## 8. Tests

```powershell
cd backend
python -m pytest -q
```

73 tests cover: numeric room sorting, fixed-slot scheduling, skip-if-busy, pause, next-cycle
behaviour, extension, test and switch announcements, auth and RBAC, one-active-session enforcement
under ten parallel requests, room switching and its audit entry, audit filters, room/officer
administration, display tokens, socket snapshot on connect, event revisions, reconnect with no ghost
rooms, and display access.

See `docs/TEST_PLAN.md` for the requirement → test mapping and manual acceptance checks.

---

## 9. Deployment

SQLite is fine for the pilot. For the production target (MySQL 8 + Nginx + Gunicorn) follow
`docs/DEPLOYMENT.md`. The short version:

```bash
pip install -r requirements.txt
export SECRET_KEY="$(python -c 'import secrets;print(secrets.token_urlsafe(48))')"
export DATABASE_URL="mysql+pymysql://smartroom:...@127.0.0.1:3306/smart_rooms?charset=utf8mb4"
export DISPLAY_REQUIRE_TOKEN=true
export COOKIE_SECURE=true
python manage.py init-db
python manage.py seed
gunicorn -k gthread -w 1 --threads 100 --timeout 120 -b 127.0.0.1:5000 run:app
```

Run **one** Gunicorn worker. Socket.IO rooms, the revision counter and the audio scheduler live in
process memory; multiple workers would produce duplicate announcements and divergent revisions.
Scale out only after adding a Socket.IO message queue (Redis) and a shared scheduler lock.

---

## 10. Troubleshooting

| Symptom | Likely cause / fix |
| --- | --- |
| Login page loads, console says “You are offline” | Socket.IO blocked by a proxy. Forward `/socket.io/` with WebSocket upgrade headers (see `docs/DEPLOYMENT.md`). |
| Display shows “Announcements start at 07:00” | Current time is outside the audio window. Admin → Settings → **Set start to now** → Save. |
| Display shows rooms but never speaks | Click **Tap to enable sound** once (browser autoplay policy), or launch kiosk Chrome with `--autoplay-policy=no-user-gesture-required`. Check the sound toggle is on. |
| “That room is already in progress” | Another officer ticked it first, or an old session was not ended. Use the room's **End** button or the live register. |
| `python run.py` says port 5000 is in use | Stop the other process or run `python manage.py run --port 5001`. |
| Database errors after changing models | The pilot uses `db.create_all()`. For schema changes in production use a real migration (Alembic) or recreate the database during the pilot. |
| Passwords rejected after import | Re-seed or reset: `python manage.py reset-password <username>`. |

---

## 11. License / handover

Internal university pilot project. No third-party assets are bundled; icons are inline SVG, fonts
use the system UI stack, and the only runtime dependencies are listed in `requirements.txt` and
`frontend/package.json`.
