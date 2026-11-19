# Deployment guide — MySQL 8, Gunicorn and Nginx

This guide targets a single Linux server (Ubuntu 22.04/24.04 LTS) on the campus LAN. The pilot can
run on SQLite; production should use MySQL 8. Keep the architecture simple: **one application
process**, many threads, one database, one public display (or a few read-only displays).

> Run one Gunicorn worker. Socket.IO rooms, the monotonic revision counter and the audio scheduler
> are in-process state. Multiple workers would each run their own scheduler and announce the same
> rooms independently, and clients could receive conflicting revisions.
>
> If you later need horizontal scale, add a Socket.IO message queue (Redis) and a distributed lock
> around the audio scheduler before increasing workers.

---

## 1. Prerequisites

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx mysql-server git curl
```

Node.js is only needed on the build machine. The compiled front end is committed under
`backend/app/static`; you can also build it on the server:

```bash
# Optional: only when changing frontend sources
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
```

Confirm versions:

```bash
python3 --version      # 3.11+
mysql --version        # 8.0+
nginx -v
```

Set the server clock and timezone. The scheduler uses naive local time:

```bash
sudo timedatectl set-timezone Africa/Nairobi
sudo timedatectl set-ntp true
timedatectl status
```

---

## 2. MySQL 8

```bash
sudo mysql
```

```sql
CREATE DATABASE smart_rooms
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

CREATE USER 'smartroom'@'127.0.0.1'
  IDENTIFIED BY 'replace-with-a-long-random-password';

GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES
  ON smart_rooms.* TO 'smartroom'@'127.0.0.1';

FLUSH PRIVILEGES;
EXIT;
```

Recommended server settings (`/etc/mysql/mysql.conf.d/mysqld.cnf`):

```ini
[mysqld]
default-time-zone = '+03:00'
character-set-server = utf8mb4
collation-server = utf8mb4_0900_ai_ci
innodb_buffer_pool_size = 512M
max_connections = 150
```

Restart and verify:

```bash
sudo systemctl restart mysql
mysql -h 127.0.0.1 -u smartroom -p -e "SELECT VERSION(), @@time_zone;"
```

`docs/schema.mysql.sql` is a DBA-reviewable DDL, but you do **not** need to run it manually:
`python manage.py init-db` creates the same tables from the SQLAlchemy models. The critical
`uq_sessions_active_room` unique key must exist either way. Verify after bootstrapping:

```sql
SHOW CREATE TABLE sessions\G
-- Look for: UNIQUE KEY `uq_sessions_active_room` (`active_room_name`)
```

---

## 3. Application install

Create a service account and directory:

```bash
sudo useradd --system --create-home --shell /usr/sbin/nologin smartrooms
sudo mkdir -p /opt/smart-rooms
sudo chown -R smartrooms:smartrooms /opt/smart-rooms
sudo -u smartrooms git clone <your-repo-url> /opt/smart-rooms
# or copy the project directory to /opt/smart-rooms
```

Create the virtual environment and install dependencies:

```bash
cd /opt/smart-rooms/backend
sudo -u smartrooms python3 -m venv .venv
sudo -u smartrooms .venv/bin/pip install --upgrade pip
sudo -u smartrooms .venv/bin/pip install -r requirements.txt
```

Build the front end if you changed it (otherwise the committed build is used):

```bash
cd /opt/smart-rooms/frontend
sudo -u smartrooms npm ci
sudo -u smartrooms npm run build
```

Create `/opt/smart-rooms/backend/.env` (mode `600`, owned by `smartrooms`):

```dotenv
SECRET_KEY=REPLACE_WITH_A_LONG_RANDOM_VALUE
DATABASE_URL=mysql+pymysql://smartroom:REPLACE_WITH_DB_PASSWORD@127.0.0.1:3306/smart_rooms?charset=utf8mb4
COOKIE_SECURE=true
INACTIVITY_MINUTES=15
DISPLAY_REQUIRE_TOKEN=true
DISPLAY_TOKEN_MAX_AGE_SEC=2592000
BUILDING_NAME=Building A
BUILDING_LABEL=LECTURE ROOMS
AUDIO_ENABLED=true
TTS_ADAPTER=browser
AUTO_INIT_DB=true
AUTO_SEED=true
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=REPLACE_WITH_A_UNIQUE_PASSWORD
DEFAULT_OFFICER_USERNAME=otieno
DEFAULT_OFFICER_PASSWORD=REPLACE_WITH_A_UNIQUE_PASSWORD
```

Generate a secret key:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Protect the file:

```bash
sudo chown root:smartrooms /opt/smart-rooms/backend/.env
sudo chmod 640 /opt/smart-rooms/backend/.env
```

Bootstrap the database and accounts:

```bash
cd /opt/smart-rooms/backend
sudo -u smartrooms .venv/bin/python manage.py init-db
sudo -u smartrooms .venv/bin/python manage.py seed
```

After the first successful boot, set `AUTO_SEED=false` and `AUTO_INIT_DB=false` in `.env` so demo
data cannot be recreated and schema changes are deliberate. Change both seeded passwords:

```bash
sudo -u smartrooms .venv/bin/python manage.py reset-password admin
sudo -u smartrooms .venv/bin/python manage.py reset-password otieno
```

Quick local smoke test before adding Nginx:

```bash
cd /opt/smart-rooms/backend
sudo -u smartrooms .venv/bin/gunicorn -k gthread -w 1 --threads 100 \
  --timeout 120 -b 127.0.0.1:5000 run:app
curl -s http://127.0.0.1:5000/api/health
```

---

## 4. systemd service

Create `/etc/systemd/system/smart-rooms.service`:

```ini
[Unit]
Description=Smart Lecture Room Notification System
After=network-online.target mysql.service
Wants=network-online.target

[Service]
Type=simple
User=smartrooms
Group=smartrooms
WorkingDirectory=/opt/smart-rooms/backend
EnvironmentFile=/opt/smart-rooms/backend/.env
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/smart-rooms/backend/.venv/bin/gunicorn \
  --worker-class gthread \
  --workers 1 \
  --threads 100 \
  --timeout 120 \
  --graceful-timeout 30 \
  --access-logfile - \
  --error-logfile - \
  --bind 127.0.0.1:5000 \
  run:app
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now smart-rooms
sudo systemctl status smart-rooms
sudo journalctl -u smart-rooms -f
```

`--threads 100` is generous for a few officers and displays. Gunicorn's `gthread` worker is required
for Flask-SocketIO when you are not using eventlet/gevent. Do **not** switch to multiple workers
without the Redis message queue described at the top.

---

## 5. Nginx reverse proxy

`/etc/nginx/sites-available/smart-rooms`:

```nginx
map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}

server {
    listen 80;
    server_name rooms.example.ac.ke;

    # Certbot will add the HTTPS redirect and certificate blocks.
    client_max_body_size 2m;

    # Socket.IO: WebSocket upgrade + long polling.
    location /socket.io/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
        proxy_buffering off;
    }

    # API and the built SPA.
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 90s;
    }

    # Optional: serve immutable assets directly from disk.
    # location /assets/ {
    #     alias /opt/smart-rooms/backend/app/static/assets/;
    #     expires 1y;
    #     add_header Cache-Control "public, immutable";
    #     access_log off;
    # }
}
```

Enable and reload:

```bash
sudo ln -s /etc/nginx/sites-available/smart-rooms /etc/nginx/sites-enabled/smart-rooms
sudo nginx -t
sudo systemctl reload nginx
```

If the proxy forwards HTTP while `COOKIE_SECURE=true`, sign-in will fail. Either put HTTPS in front
first (recommended) or set `COOKIE_SECURE=false` only during an isolated HTTP smoke test.

### HTTPS with Let's Encrypt

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d rooms.example.ac.ke
sudo certbot renew --dry-run
```

After HTTPS works, confirm:

```bash
curl -I https://rooms.example.ac.ke/api/health
```

### Firewall

```bash
sudo ufw allow 'Nginx Full'
sudo ufw allow OpenSSH
sudo ufw enable
sudo ufw status
```

Only ports 80/443 and SSH should be exposed; MySQL and Gunicorn stay on loopback.

---

## 6. Public display kiosk

1. Sign in to the console as an officer or admin.
2. Click **Open display**. With `DISPLAY_REQUIRE_TOKEN=true` the server issues a signed, read-only
   link of the form `https://rooms.example.ac.ke/#/display?token=…`.
3. Open that URL on the display PC and click **Tap to enable sound** once. Browsers may block speech
   until a user gesture; the prompt is intentional.
4. Use kiosk mode so the address bar and tabs are not visible:

```bash
google-chrome --kiosk --noerrdialogs --disable-infobars \
  --autoplay-policy=no-user-gesture-required \
  "https://rooms.example.ac.ke/#/display?token=PASTE_TOKEN_HERE"
```

5. Disable screen blanking and automatic sleep. On Ubuntu:
   `Settings → Power → Screen Blank = Never`. For a dedicated kiosk, configure a locked-down desktop
   session that launches the command above on login.
6. Set the display browser zoom so six room cards fill the screen comfortably; the layout switches to
   two columns below 1080 px and one column on narrow screens.
7. Verify the footer says **LIVE** and the clock matches the server. If it says **RECONNECTING**,
   check the `/socket.io/` proxy block.

The display token is valid for `DISPLAY_TOKEN_MAX_AGE_SEC` (30 days by default). Regenerate it from
the console before it expires, or rotate `SECRET_KEY` and issue a new link. Treat the link as a
read-only secret: anyone with it can see room status, but cannot change anything.

### Optional: server-side TTS instead of browser speech

If the building audio is wired to the server rather than the display PC, set `TTS_ADAPTER=command`
and `TTS_COMMAND` to a local speech command, e.g.:

```dotenv
TTS_ADAPTER=command
TTS_COMMAND=espeak-ng -s 150
```

The command receives the announcement text as its final argument. `TTS_ADAPTER=pyttsx3` requires
`pip install pyttsx3` plus OS speech libraries and is optional. Keep `browser` unless you have a
specific reason: it needs no server sound device and naturally plays on the display that people are
looking at.

---

## 7. Operations

### Health and logs

```bash
curl -s https://rooms.example.ac.ke/api/health
sudo journalctl -u smart-rooms --since "1 hour ago"
sudo tail -f /var/log/nginx/access.log /var/log/nginx/error.log
```

### Restart / deploy a new build

```bash
cd /opt/smart-rooms
sudo -u smartrooms git pull
cd frontend && sudo -u smartrooms npm ci && sudo -u smartrooms npm run build
cd ../backend
sudo -u smartrooms .venv/bin/pip install -r requirements.txt
sudo systemctl restart smart-rooms
```

Restarting drops the sockets; displays automatically reconnect and receive a fresh snapshot. Do it
between lectures. The audio scheduler restarts from the current time slot; it does not replay old
announcements.

### Backup

Daily MySQL dump with retention:

```bash
sudo mkdir -p /var/backups/smart-rooms
sudo chown smartrooms:smartrooms /var/backups/smart-rooms
sudo crontab -u smartrooms -e
```

```cron
15 1 * * * mysqldump --single-transaction --quick smart_rooms | gzip > /var/backups/smart-rooms/smart_rooms-$(date +\%F).sql.gz
30 1 * * * find /var/backups/smart-rooms -type f -mtime +30 -delete
```

Store a copy off the server. Test a restore before relying on it:

```bash
gunzip -c /var/backups/smart-rooms/smart_rooms-YYYY-MM-DD.sql.gz | mysql -u root -p smart_rooms_restore
```

### Log rotation

Gunicorn logs go to the journal; journald rotates them. Nginx has its own logrotate configuration.
If you add file logging, configure logrotate with `copytruncate` or send `USR1` to Gunicorn.

### Time changes

The scheduler, display clock and audit timestamps all use the server clock. If you must change the
server timezone or DST behaviour, do it between lectures and restart the service. Adjust
`lecture_start` in Admin → Settings if the local timetable changes.

---

## 8. Pre-flight checklist

- [ ] `SECRET_KEY` is unique and not the development placeholder.
- [ ] `DATABASE_URL` points at MySQL 8 with `utf8mb4`.
- [ ] `COOKIE_SECURE=true` and HTTPS works.
- [ ] `DISPLAY_REQUIRE_TOKEN=true`; display link regenerated after any secret rotation.
- [ ] `AUTO_SEED=false` and `AUTO_INIT_DB=false` after bootstrap.
- [ ] Default passwords changed; each officer has their own account.
- [ ] `uq_sessions_active_room` exists in MySQL.
- [ ] `/api/health` returns `ok` through Nginx.
- [ ] Console shows **Live**; display shows **LIVE** and updates within a second of a tick.
- [ ] Display PC: kiosk mode, sound unlocked, screen never sleeps, clock synced.
- [ ] Backup cron and restore test completed.
- [ ] Runbook (`docs/PILOT_RUNBOOK.md`) printed at the security desk.
