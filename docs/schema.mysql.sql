-- Smart Lecture Room Notification System — reference MySQL 8 schema
--
-- The application normally creates these tables with SQLAlchemy's db.create_all().
-- This file is provided for DBA review, manual provisioning, and documentation of
-- the constraints. If you apply it manually, still run:
--     python manage.py init-db
--     python manage.py seed
-- against the same database so the settings rows and demo accounts exist.
--
-- MySQL 8.0.13+ required for the stored generated column.

CREATE DATABASE IF NOT EXISTS smart_rooms
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

USE smart_rooms;

CREATE TABLE officers (
  id             BIGINT       NOT NULL AUTO_INCREMENT,
  name           VARCHAR(120) NOT NULL,
  username       VARCHAR(60)  NOT NULL,
  password_hash  VARCHAR(255) NOT NULL,
  role           ENUM('OFFICER', 'ADMIN') NOT NULL DEFAULT 'OFFICER',
  active         TINYINT(1)   NOT NULL DEFAULT 1,
  created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_officers_username (username)
) ENGINE = InnoDB;

CREATE TABLE rooms (
  id           BIGINT      NOT NULL AUTO_INCREMENT,
  room_name    VARCHAR(40) NOT NULL,
  room_number  INT         NOT NULL DEFAULT 0,
  building     VARCHAR(40) NOT NULL DEFAULT 'A',
  active       TINYINT(1)  NOT NULL DEFAULT 1,
  created_at   DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_rooms_room_name (room_name),
  KEY ix_rooms_room_number (room_number)
) ENGINE = InnoDB;

CREATE TABLE sessions (
  id                BIGINT      NOT NULL AUTO_INCREMENT,
  room_name         VARCHAR(40) NOT NULL,
  room_number       INT         NOT NULL DEFAULT 0,
  lecturer_name     VARCHAR(120) NULL,
  status            ENUM('IN_PROGRESS', 'ENDED') NOT NULL DEFAULT 'IN_PROGRESS',
  started_at        DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  ended_at          DATETIME    NULL,
  ticked_by         BIGINT      NOT NULL,
  ended_by          BIGINT      NULL,

  -- NULL for ended sessions, the room name for an active session.
  -- Because MySQL allows many NULLs in a UNIQUE index, this enforces
  -- "at most one IN_PROGRESS session per room" at the database level.
  active_room_name  VARCHAR(40)
    GENERATED ALWAYS AS (
      CASE WHEN status = 'IN_PROGRESS' THEN room_name ELSE NULL END
    ) STORED,

  PRIMARY KEY (id),
  UNIQUE KEY uq_sessions_active_room (active_room_name),
  KEY ix_sessions_room_name (room_name),
  KEY ix_sessions_room_number (room_number),
  KEY ix_sessions_status (status),
  KEY ix_sessions_status_room (status, room_name),
  KEY ix_sessions_started_at (started_at),
  CONSTRAINT fk_sessions_ticked_by FOREIGN KEY (ticked_by) REFERENCES officers (id),
  CONSTRAINT fk_sessions_ended_by   FOREIGN KEY (ended_by)   REFERENCES officers (id)
) ENGINE = InnoDB;

CREATE TABLE settings (
  `key`        VARCHAR(60)  NOT NULL,
  value        VARCHAR(255) NOT NULL,
  updated_by   BIGINT       NULL,
  updated_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                            ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`key`),
  CONSTRAINT fk_settings_updated_by FOREIGN KEY (updated_by) REFERENCES officers (id)
) ENGINE = InnoDB;

CREATE TABLE audit_log (
  id          BIGINT      NOT NULL AUTO_INCREMENT,
  officer_id  BIGINT      NOT NULL,
  action      VARCHAR(60) NOT NULL,
  room_name   VARCHAR(40) NULL,
  detail      JSON        NULL,
  created_at  DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY ix_audit_log_officer_id (officer_id),
  KEY ix_audit_log_action (action),
  KEY ix_audit_log_created_at (created_at),
  KEY ix_audit_created_action (created_at, action),
  CONSTRAINT fk_audit_log_officer FOREIGN KEY (officer_id) REFERENCES officers (id)
) ENGINE = InnoDB;

-- Seed the six settings keys (the CLI also does this idempotently).
INSERT INTO settings (`key`, value) VALUES
  ('lecture_start', '07:00'),
  ('lecture_duration_min', '180'),
  ('audio_window_min', '30'),
  ('repeat_interval_sec', '300'),
  ('audio_extended_until', ''),
  ('audio_paused', '0')
ON DUPLICATE KEY UPDATE value = VALUES(value);

-- Verification: this must return one row with a non-NULL active_room_name.
-- SELECT id, room_name, status, active_room_name FROM sessions;
