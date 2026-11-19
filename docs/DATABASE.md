# Database design and schema

The application creates its tables from the SQLAlchemy models in
`backend/app/models.py`. SQLite is used for the zero-setup pilot; MySQL 8 is the production target.
`docs/schema.mysql.sql` is a reference DDL for DBAs and for reviewing the constraints — the
application does not execute it.

Times are stored as **naive local time** (the pilot server runs in Africa/Nairobi). The server clock
is the single source of truth for the console, display and scheduler. If the server timezone changes,
update the scheduler settings and restart during a quiet period.

---

## 1. Entity relationship overview

```text
┌──────────────┐        ┌────────────────────┐        ┌──────────────────┐
│   officers   │1      *│      sessions      │        │      rooms       │
│──────────────│────────│────────────────────│        │──────────────────│
│ id (PK)      │        │ id (PK)            │        │ id (PK)          │
│ name         │        │ room_name          │        │ room_name UNIQUE │
│ username UQ  │        │ room_number        │        │ room_number      │
│ password_hash│        │ lecturer_name      │        │ building         │
│ role         │        │ status             │        │ active           │
│ active       │        │ started_at         │        │ created_at       │
│ created_at   │        │ ended_at           │        └──────────────────┘
└──────┬───────┘        │ ticked_by (FK)     │
       │                │ ended_by (FK)      │
       │                │ active_room_name   │  ← generated, UNIQUE
       │                │   (generated)      │
       │                └────────────────────┘
       │1
       │*
┌──────┴───────┐        ┌──────────────────────────────┐
│  audit_log   │        │          settings            │
│──────────────│        │──────────────────────────────│
│ id (PK)      │        │ key (PK)                     │
│ officer_id FK│        │ value                        │
│ action       │        │ updated_by FK → officers     │
│ room_name    │        │ updated_at                   │
│ detail JSON  │        └──────────────────────────────┘
│ created_at   │
└──────────────┘
```

`rooms` is intentionally not a foreign-key parent of `sessions`: the room register can be edited
(deactivated/renamed) while historical sessions keep the name that was in use. The live console
validates that a room exists and is active before inserting a session.

---

## 2. The critical constraint: one active session per room

A room may have many historical sessions but only one `IN_PROGRESS` row. Application checks alone
are not enough: two officers clicking at the same time can both pass a `SELECT` before either
`INSERT` commits.

The specification's preferred solution is a partial/filtered unique index. MySQL 8 has no filtered
indexes, so the schema uses an equivalent portable trick:

```sql
active_room_name VARCHAR(40)
  GENERATED ALWAYS AS (CASE WHEN status = 'IN_PROGRESS' THEN room_name ELSE NULL END) STORED,
UNIQUE KEY uq_sessions_active_room (active_room_name)
```

- For an active session the generated value is the room name.
- For an ended session it is `NULL`.
- SQL standard — and both MySQL and SQLite — allow **many NULLs** in a unique index, but only one
  non-NULL `KLH101`.
- Therefore the database rejects a second active `KLH101` with an integrity error regardless of how
  many application threads or processes try.

The application layers two more protections:

1. `SELECT … FOR UPDATE` on the active-session lookup serialises competing transactions where the
   database supports row locking.
2. `IntegrityError` is caught and translated into the same friendly `409` response, so the officer
   sees “KLH101 is already in progress” rather than a server error.

The test `test_ten_parallel_ticks_only_one_succeeds` starts ten threads authenticated as the same
officer and asserts exactly one `201` and nine `409`s. A second test verifies that after a session is
ended the same room can be ticked again.

**Never drop `uq_sessions_active_room`.** It is the last line of defence for the display's accuracy.

---

## 3. Tables

### officers

| Column | Type | Notes |
| --- | --- | --- |
| `id` | BIGINT PK, auto-increment | |
| `name` | VARCHAR(120) NOT NULL | Display name in audit. |
| `username` | VARCHAR(60) NOT NULL UNIQUE | Lower-cased by model validator and API. |
| `password_hash` | VARCHAR(255) NOT NULL | Argon2id encoded hash. |
| `role` | ENUM('OFFICER','ADMIN') NOT NULL | |
| `active` | BOOLEAN NOT NULL | Deactivated accounts fail on the next request. |
| `created_at` | DATETIME NOT NULL | Local time. |

### rooms

| Column | Type | Notes |
| --- | --- | --- |
| `id` | BIGINT PK | |
| `room_name` | VARCHAR(40) NOT NULL UNIQUE | e.g. `KLH101`. |
| `room_number` | INT NOT NULL, indexed | Integer extracted from the name; drives numeric sorting. |
| `building` | VARCHAR(40) NOT NULL | Default `A`. |
| `active` | BOOLEAN NOT NULL | Inactive rooms disappear from the console grid but remain for history. |
| `created_at` | DATETIME NOT NULL | |

### sessions

| Column | Type | Notes |
| --- | --- | --- |
| `id` | BIGINT PK | |
| `room_name` | VARCHAR(40) NOT NULL, indexed | Snapshot of the name at tick time. |
| `room_number` | INT NOT NULL, indexed | Snapshot of the numeric sort key. |
| `lecturer_name` | VARCHAR(120) NULL | Optional. Never shown on the public display? It **is** shown when supplied. |
| `status` | ENUM('IN_PROGRESS','ENDED') NOT NULL, indexed | |
| `started_at` | DATETIME NOT NULL | |
| `ended_at` | DATETIME NULL | |
| `ticked_by` | BIGINT NOT NULL FK → officers.id | Audit attribution. |
| `ended_by` | BIGINT NULL FK → officers.id | |
| `active_room_name` | VARCHAR(40) generated STORED, UNIQUE | See section 2. |

Indexes: `(status, room_name)` for the live lookup, `(started_at)` for reporting.

### settings

Key/value pairs, seeded with:

| Key | Default | Meaning |
| --- | --- | --- |
| `lecture_start` | `07:00` | Local wall-clock start of the lecture block. |
| `lecture_duration_min` | `180` | Used for the end-of-lecture warning. |
| `audio_window_min` | `30` | Listening window measured from the start. |
| `repeat_interval_sec` | `300` | Announcement interval. |
| `audio_extended_until` | empty | ISO datetime set by **+15**. |
| `audio_paused` | `0` | `1` while announcements are paused. |

`updated_by` references the officer who last changed a value.

### audit_log

| Column | Type | Notes |
| --- | --- | --- |
| `id` | BIGINT PK | |
| `officer_id` | BIGINT NOT NULL FK → officers.id, indexed | |
| `action` | VARCHAR(60) NOT NULL, indexed | `LOGIN`, `LOGOUT`, `TICK`, `END`, `PAUSE`, `RESUME`, `EXTEND`, `SET_INTERVAL`, `SETTINGS`, `TEST_ANNOUNCE`, `OFFICER_CREATE`, `OFFICER_UPDATE`, `ROOM_CREATE`, `ROOM_UPDATE`. |
| `room_name` | VARCHAR(40) NULL | Copied for filtering, survives room deletion/rename. |
| `detail` | JSON NULL | Lecturer name, changed values, announcement text, etc. |
| `created_at` | DATETIME NOT NULL, indexed | |

Composite index `(created_at, action)` supports the admin audit filters and default newest-first
ordering. Audit rows are never edited or deleted by the application.

---

## 4. SQLite vs MySQL differences

| Concern | SQLite (pilot) | MySQL 8 (production) |
| --- | --- | --- |
| Driver | built in | `PyMySQL` (`mysql+pymysql://…`) |
| `BIGINT` PK | mapped to `INTEGER` via `with_variant` so it auto-increments | native `BIGINT AUTO_INCREMENT` |
| `ENUM` | stored as `VARCHAR` + `CHECK` | native `ENUM` |
| Generated column | supported (stored) | supported (stored) |
| Case sensitivity | `UNIQUE` is case-sensitive by default | default `utf8mb4_0900_ai_ci` is case-insensitive; API also lower-cases usernames and checks room names case-insensitively |
| JSON | stored as JSON text | native `JSON` |
| Concurrency | one writer at a time; WAL recommended | InnoDB row locking; `SELECT … FOR UPDATE` is effective |
| Timezone | server local time | set `default-time-zone='+03:00'` or keep the OS in Africa/Nairobi |

Enable WAL for a busier SQLite pilot:

```sql
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=30000;
```

---

## 5. Bootstrap, seed and reset

```powershell
cd backend

python manage.py init-db       # create missing tables (db.create_all)
python manage.py seed          # insert demo officers/rooms only if tables are empty
python manage.py reset-password admin --password "new-strong-password"
```

`AUTO_INIT_DB=true` and `AUTO_SEED=true` do the same at boot when the tables are empty. After the
initial production deployment, set both to `false` in `.env` so a restart cannot create demo data.

### Recreating the pilot database

Stop the server, delete `backend/instance/smart_rooms.db`, then:

```powershell
python manage.py init-db
python manage.py seed
```

For MySQL, drop and recreate the schema (or truncate tables in FK-safe order: `audit_log`,
`sessions`, `settings`, `rooms`, `officers`) and run `init-db` / `seed`.

---

## 6. Retention and backup

- `audit_log` is append-only and grows slowly (a few rows per tick). Keep at least one academic year.
- Back up nightly: `mysqldump --single-transaction --routines --triggers smart_rooms > smart_rooms.sql`
  (or copy the SQLite file while the server is stopped / use `sqlite3 .backup`).
- Archive ended sessions and audit rows older than the retention period with a scheduled SQL job if
  the institution requires it; the application never depends on old rows for live operation.
- Test a restore into a scratch database before relying on the backup.
