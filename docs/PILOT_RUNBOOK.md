# Pilot runbook — Smart Lecture Room Notification System

This is the desk copy for the security officer and the ICT administrator during the pilot.
Print it, keep it at the security desk, and fill in the contact numbers on the last page.

The system has two jobs:

1. Let the officer record that a lecturer has arrived, once, without leaving the desk.
2. Show that information on the public display and read it aloud during the announcement window.

Everything else (accounts, rooms, schedule, audit) supports those two jobs. If the system is
unavailable, use the paper fallback in section 7 and keep the desk running.

---

## 1. Roles

| Role | Who | Can do |
| --- | --- | --- |
| Security officer | Front desk | Sign in, tick a room, add a lecturer name, switch an in-progress lecture to a free room, end a session, undo, pause/resume audio, extend +15 min, change the repeat interval (1/2/5/10/15 min), open the display, press **Test**. |
| Administrator | ICT / timetabling | Everything an officer can do, plus officers, rooms, full schedule settings, and the audit log. |
| Public display | Projector / kiosk PC | Read-only. Shows live rooms and speaks announcements. Needs no sign-in when opened from the console-issued link. |

Each person must use their **own** account. Shared logins make the audit trail useless. Sign out
before handing the desk over.

---

## 2. Before the pilot day

Complete this once, at least a day before the first lecture.

- [ ] Server time and timezone are correct (`Africa/Nairobi`) and NTP is enabled.
- [ ] Sign in as `admin` and change the seeded passwords:
      `python manage.py reset-password admin` and `python manage.py reset-password otieno`.
- [ ] Create one account per officer (Admin → **Officers**). Use real names.
- [ ] Deactivate the demo accounts you do not need.
- [ ] Check the room register (Admin → **Rooms**) matches the building. Remove typo rooms.
- [ ] Set the schedule (Admin → **Settings**): lecture start, lecture duration, audio window,
      repeat interval. Confirm the preview text is sensible.
- [ ] Open the display on the kiosk PC, click **Tap to enable sound**, and confirm the footer
      reads **LIVE** with the correct clock.
- [ ] Disable screen blanking and sleep on the display PC. Start Chrome in kiosk mode
      (see `docs/DEPLOYMENT.md`, section 6).
- [ ] Run the manual acceptance cases in `docs/TEST_PLAN.md` on the real hardware.
- [ ] Print this runbook and the paper fallback sheet.

---

## 3. Morning setup (5 minutes)

1. **Start the server** if it is not already running as a service:
   - Windows pilot laptop: double-click `start.bat` in the project folder (run `install.bat` once
     beforehand if the laptop is new). The browser opens automatically.
   - Other platforms: `cd backend` then `python run.py`.
   - Production: `sudo systemctl status smart-rooms` should say `active (running)`.
2. **Check health:** open `http://<server>/api/health`. It must return `{"status":"ok"}`.
3. **Open the console:** `http://<server>/#/console` and sign in as yourself.
4. **Check the header:** the connection chip must say **Live**. If it says **Offline**, see
   section 8 before the first lecture.
5. **Open the display** with the **Open display** button (or the existing kiosk shortcut). Confirm:
   - footer says **LIVE**;
   - the clock matches the console;
   - the correct rooms appear in numeric order (`KLH9`, `KLH10`, `KLH101`, …);
   - **no room is left "In progress" from yesterday** (if one is, end it now and note it).
6. **Sound check:** press **Test** on the console. The display must speak the current room list.
   If it does not, click **Tap to enable sound** on the display once, then press **Test** again.
7. **Schedule check:** the audio card shows the window, e.g. `Audio 07:00–07:30`. If the pilot is
   running at a different time today, an admin can set the start to now (Admin → Settings →
   **Set start to now** → Save) and set it back afterwards.

---

## 4. During a lecture

### Record a lecturer's arrival

1. Find the room in the grid. It is sorted numerically, and available rooms are enabled.
2. Optional: type the lecturer's name in **Lecturer name**.
3. Click the room (or focus it and press **Enter**), check the confirmation summary, then press
   **Mark in progress**.
4. The card turns to **In progress**, the room appears in the live list, the display updates within
   about a second, and a toast offers **Undo** for 10 seconds.

Rules:

- A room can only be in progress **once**. If another officer ticked it first you will see
  “That room is already in progress”. Do not retry; check the live list.
- A room that is already in progress has its **End** button on the card. Only end a session when
  the lecture is actually over (or the lecturer has left).
- You do not need to tick again for each announcement. The audio engine repeats automatically
  during the window.
- Press `/` to jump to room search, `Esc` to cancel a selection, `Space` to pause/resume audio.

### End a session

1. Click **End** on the in-progress card, or the matching row under **In-progress sessions**.
2. Confirm. The room disappears from the display immediately.
3. If you ended the wrong room by mistake, click **Undo** in the toast within 10 seconds.

### Move a lecture to another room

Use this when a lecture starts or continues in a different room. Do **not** end the session and tick
another room: that loses the original start time and splits the record.

1. Find the lecture under **In-progress sessions**.
2. Click **Switch** on its row.
3. Choose a free room from the list. Rooms already in progress are not offered.
4. Confirm **Switch room**. The row moves to the new room and the start time, lecturer and officer
   stay the same.
5. The public display shows an amber **Room change** banner (“KLH101 switched to KLH102”) for about
   90 seconds, and the speaker says “KLH101 changed to KLH102.” If the display is already speaking,
   the extra announcement is skipped — the banner and the switch still happen.

If the room was taken a moment earlier, the switch is refused with “already in progress”. Check the
live list and choose another free room. Every switch is written to the audit log.

### Audio controls

| Control | What it does |
| --- | --- |
| **Pause** / **Resume** | Stops/starts spoken announcements. Paused time still consumes cycles; no backlog is played when you resume. |
| **+15 min** | Extends the listening window by 15 minutes from the later of “now” and the current end. Use it when a lecturer starts late or the session runs over. |
| **Interval** | Changes how often the room list is read (1–15 minutes). |
| **Test** | Speaks the current room list immediately, even outside the window. Use for the morning sound check only; it is audited. |

The display footer always shows the truth: `Announcements every 5 min · window until 07:45`,
`Announcements paused`, or `Announcements start at 07:00`.

### What the display says

Example: “KLH101, KLH102, KLH105 in progress.” If a lecturer name was recorded it is included.
Rooms are always read in numeric order. If nothing is in progress, nothing is announced.

A room ticked mid-cycle waits for the next cycle. This is deliberate: it prevents a surprise
announcement immediately after registration. Do not press **Test** to “speed it up” during normal
operation; it will announce the entire list early.

---

## 5. End of day

1. End every remaining in-progress session (check the **In-progress sessions** count is `0`).
   If the last lecture genuinely runs late, leave it and note the time for the administrator.
2. If you extended the window or changed the interval, restore the normal values (admin).
3. Keep the display running overnight if it is a kiosk; it reconnects automatically. Otherwise
   close the browser and shut down the kiosk PC.
4. Sign out of the console. Do not leave an admin session open at the desk.
5. If anything behaved unexpectedly, write it on the pilot log sheet: time, room, what you did,
   what you expected, what happened. This is more useful than a verbal report.
6. The administrator checks Admin → **Audit log** for the day’s TICK/SWITCH_ROOM/END/PAUSE entries
   and files any issues.

---

## 6. Expected behaviour and normal “non-errors”

| Observation | Why it is normal |
| --- | --- |
| Display says `Announcements start at 07:00` | Current time is before the window. |
| Display says `Announcements every … window until …` but is quiet | The next cycle has not arrived yet, or the last cycle was consumed while paused/empty/busy. |
| A newly ticked room is not read for a few minutes | It waits for the next fixed cycle by design. |
| Console briefly shows a 401 in the browser console on the login page | The app checks “am I signed in?” before you sign in. Expected. |
| Display footer says `Updated 10:42:15` a moment behind the clock | Last state change, not the current time. |
| Two displays both speak | Both have sound enabled. Mute the secondary screen. |
| **Undo** disappears after 10 seconds | The undo window has closed; re-tick the room if needed. |
| Room-change banner stays for a minute or two | The notice is deliberately kept for 90 seconds so people walking past still see it. |
| A switch was not spoken aloud | The display was already speaking, or sound is not enabled. The switch itself completed and is on screen. |

---

## 7. Incident fallback (system unavailable)

If the console, display or network fails and cannot be fixed in two minutes:

1. Announce arrivals **verbally** at the desk and by phone/radio to the lecture block, exactly as
   before the pilot.
2. Record every arrival on the paper fallback sheet: **time, room, lecturer name (if given),
   officer initials**.
3. If the display still works but the console does not, keep the display running; it will show
   **RECONNECTING** and recover on its own when the server returns.
4. Do **not** restart the database or delete files to “fix” the app. Note the symptom and call the
   administrator.
5. When the system returns, do **not** back-fill old sessions. Only tick rooms that are still
   in progress. Hand the paper sheet to the administrator for the incident record.

### Quick recovery checks

| Symptom | Check |
| --- | --- |
| Console says **Offline** | Is the server running? Is Wi-Fi/LAN up? Open `/api/health`. |
| Display says **RECONNECTING** | Same network check; refresh once. The display reconnects by itself. |
| Login fails for everyone | Server time/DB up? Check `journalctl -u smart-rooms` or the terminal. |
| “Room already in progress” but no card shows it | Refresh the console once. If it persists, an admin checks the live list / restarts the service. |
| Display never speaks | Click **Tap to enable sound**; check the sound toggle and the PC volume; press **Test**. |

---

## 8. Troubleshooting for the administrator

| Symptom | Likely cause | Action |
| --- | --- | --- |
| Login page loads, console shows Offline | `/socket.io/` not proxied or WebSocket upgrade blocked | Fix the Nginx `location /socket.io/` block; see `docs/DEPLOYMENT.md`. |
| `502 Bad Gateway` | Gunicorn not running | `sudo systemctl restart smart-rooms`, then `journalctl -u smart-rooms -n 100`. |
| `500` on tick/end | Database down or schema mismatch | Check MySQL, then logs. Do not drop tables during teaching hours. |
| Display link expired / `401` | Token older than 30 days or secret rotated | Sign in to the console and **Open display** again. |
| All passwords rejected after moving the DB | Wrong hash column or re-seeded DB | `python manage.py reset-password <username>`. |
| Browser blocks speech | Autoplay policy | Click **Tap to enable sound**, or use the kiosk autoplay flag. |
| Scheduler announces outside the expected time | Server clock/timezone drift or wrong `lecture_start` | Fix the clock/NTP and the schedule; restart between lectures. |
| “Port 5000 already in use” | Old process still running | Stop it, or `python manage.py run --port 5001` for a local test. |

Useful commands (run from `backend/`):

```powershell
python manage.py seed                  # idempotent: only fills an empty database
python manage.py reset-password <user>
python manage.py init-db
python -m pytest -q                    # 73 automated tests
```

Never run `init-db` against a database you have not backed up. `seed` is safe: it leaves existing
rows untouched.

---

## 9. Data, privacy and audit

- The console and display show only room name, status, and the optional lecturer name. They never
  show usernames, staff numbers or unit codes.
- Every login, tick, switch, end, undo, audio change, settings change, account change and room
  change is written to the audit log with the officer, time, room and detail. Audit records are not
  editable.
- The display link is read-only. Treat it as a secret: anyone who has it can see room status.
- Backups: SQLite pilot — copy `backend/instance/smart_rooms.db` while the server is stopped, or use
  `sqlite3 .backup`. MySQL — the nightly dump described in `docs/DEPLOYMENT.md`.

---

## 10. Sign-off and contacts

| Item | Name | Phone |
| --- | --- | --- |
| ICT administrator (system owner) | | |
| Deputy administrator | | |
| Security supervisor | | |
| Building/Audio technician | | |

Pilot start date: ____________________  Review date: ____________________

Before the first lecture, confirm:

- [ ] Officers can sign in with their own accounts.
- [ ] Each room in the register exists in the building.
- [ ] Display is live, sound unlocked, clock correct, screen never sleeps.
- [ ] Test announcement heard at the far end of the corridor.
- [ ] Paper fallback sheet and this runbook at the desk.
- [ ] Administrator knows how to end a stuck session and restart the service.
