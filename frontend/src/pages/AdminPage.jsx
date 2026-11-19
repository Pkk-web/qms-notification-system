import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import {
  formatClock,
  formatCountdown,
  formatDateTime,
  formatInterval,
} from "../lib/time";
import { navigate } from "../lib/useHashRoute";
import { useAuth } from "../state/AuthContext";
import { useClock, useLive } from "../state/LiveContext";
import { TopBar } from "../components/TopBar";
import { Modal } from "../components/Modal";
import { Toast, useToast } from "../components/Toast";
import {
  IconArrowLeft,
  IconChevronLeft,
  IconChevronRight,
  IconDoor,
  IconKey,
  IconList,
  IconPlus,
  IconRefresh,
  IconSettings,
  IconUsers,
  IconX,
} from "../components/Icons";

const TABS = [
  { id: "officers", label: "Officers", icon: IconUsers },
  { id: "rooms", label: "Rooms", icon: IconDoor },
  { id: "settings", label: "Settings", icon: IconSettings },
  { id: "audit", label: "Audit log", icon: IconList },
];

const AUDIT_ACTIONS = [
  "TICK",
  "SWITCH_ROOM",
  "END",
  "LOGIN",
  "LOGOUT",
  "PAUSE",
  "RESUME",
  "EXTEND",
  "SET_INTERVAL",
  "SETTINGS",
  "TEST_ANNOUNCE",
  "OFFICER_CREATE",
  "OFFICER_UPDATE",
  "ROOM_CREATE",
  "ROOM_UPDATE",
];

function pad(value) {
  return String(value).padStart(2, "0");
}

function addMinutes(time, minutes) {
  const [hours, mins] = String(time || "00:00")
    .split(":")
    .map(Number);
  if (Number.isNaN(hours) || Number.isNaN(mins)) return "—";
  const total = ((hours * 60 + mins + Number(minutes || 0)) % 1440 + 1440) % 1440;
  return `${pad(Math.floor(total / 60))}:${pad(total % 60)}`;
}

function actionTone(action) {
  if (action === "TICK") return "success";
  if (action === "END") return "danger";
  if (action === "SWITCH_ROOM" || action === "PAUSE" || action === "SET_INTERVAL") return "warning";
  if (action === "LOGIN" || action === "LOGOUT") return "neutral";
  return "info";
}

function describeDetail(entry) {
  const detail = entry.detail || {};
  if (detail.from_room && detail.to_room) return `${detail.from_room} → ${detail.to_room}`;
  if (detail.lecturer_name) return detail.lecturer_name;
  if (detail.until) return `until ${formatClock(detail.until)}`;
  if (detail.text) return detail.text;
  if (detail.username) return detail.username;
  if (detail.changed) {
    return Object.entries(detail.changed)
      .map(([key, value]) => `${key.replaceAll("_", " ")}: ${value}`)
      .join(", ");
  }
  if (detail.undo) return "undo";
  if (detail.minutes) return `+${detail.minutes} min`;
  return "—";
}

export default function AdminPage() {
  const { officer, logout } = useAuth();
  const { connected, building } = useLive();
  const [tab, setTab] = useState("officers");
  const { toast, show: showToast, clear } = useToast();

  return (
    <div className="admin-page">
      <TopBar
        officer={officer}
        connected={connected}
        onLogout={logout}
        subtitle={`Administration · ${building?.name || "Building A"}`}
      >
        <button type="button" className="btn btn-quiet btn-sm" onClick={() => navigate("/console")}>
          <IconArrowLeft size={16} /> Console
        </button>
      </TopBar>

      <main className="admin-main">
        <div className="page-head">
          <div>
            <p className="eyebrow">Building A · Pilot</p>
            <h1>Administration</h1>
            <p className="page-lede">
              Manage officer accounts, rooms, scheduling and the complete audit trail.
            </p>
          </div>
        </div>

        <nav className="tabs" role="tablist" aria-label="Administration sections">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              role="tab"
              id={`tab-${id}`}
              aria-selected={tab === id}
              aria-controls={`panel-${id}`}
              className={`tab ${tab === id ? "is-active" : ""}`}
              onClick={() => setTab(id)}
            >
              <Icon size={17} />
              {label}
            </button>
          ))}
        </nav>

        <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
          {tab === "officers" && <OfficersTab officer={officer} showToast={showToast} />}
          {tab === "rooms" && <RoomsTab showToast={showToast} />}
          {tab === "settings" && <SettingsTab showToast={showToast} />}
          {tab === "audit" && <AuditTab showToast={showToast} />}
        </div>
      </main>

      <div className="toast-stack">
        <Toast toast={toast} onClose={clear} />
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ officers */

function OfficersTab({ officer, showToast }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ name: "", username: "", password: "", role: "OFFICER" });
  const [saving, setSaving] = useState(false);
  const [resetTarget, setResetTarget] = useState(null);
  const [resetPassword, setResetPassword] = useState("");
  const [resetSaving, setResetSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api("/api/officers");
      setRows(data.officers || []);
    } catch (error) {
      showToast(error.message, "error");
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    load();
  }, [load]);

  async function createOfficer(event) {
    event.preventDefault();
    setSaving(true);
    try {
      await api("/api/officers", { method: "POST", body: form });
      showToast(`Officer ${form.username} created.`, "success");
      setForm({ name: "", username: "", password: "", role: "OFFICER" });
      load();
    } catch (error) {
      showToast(error.message, "error");
    } finally {
      setSaving(false);
    }
  }

  async function patchOfficer(row, body, message) {
    try {
      await api(`/api/officers/${row.id}`, { method: "PATCH", body });
      showToast(message, "success");
      load();
    } catch (error) {
      showToast(error.message, "error");
    }
  }

  async function submitReset(event) {
    event.preventDefault();
    setResetSaving(true);
    try {
      await api(`/api/officers/${resetTarget.id}`, {
        method: "PATCH",
        body: { password: resetPassword },
      });
      showToast(`Password reset for ${resetTarget.username}.`, "success");
      setResetTarget(null);
      setResetPassword("");
    } catch (error) {
      showToast(error.message, "error");
    } finally {
      setResetSaving(false);
    }
  }

  return (
    <div className="stack">
      <form className="panel form-panel" onSubmit={createOfficer}>
        <div className="panel-head">
          <div>
            <p className="eyebrow">New account</p>
            <h2>Add an officer</h2>
          </div>
          <span className="panel-note">Individual accounts keep the audit trail honest.</span>
        </div>
        <div className="form-grid">
          <label className="field">
            <span>Full name</span>
            <input
              value={form.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
              placeholder="e.g. Mary Wambui"
              required
            />
          </label>
          <label className="field">
            <span>Username</span>
            <input
              value={form.username}
              onChange={(event) => setForm({ ...form, username: event.target.value })}
              placeholder="e.g. mwambui"
              autoComplete="off"
              required
            />
          </label>
          <label className="field">
            <span>Password</span>
            <input
              type="password"
              value={form.password}
              onChange={(event) => setForm({ ...form, password: event.target.value })}
              placeholder="At least 8 characters"
              autoComplete="new-password"
              minLength={8}
              required
            />
          </label>
          <label className="field">
            <span>Role</span>
            <select
              value={form.role}
              onChange={(event) => setForm({ ...form, role: event.target.value })}
            >
              <option value="OFFICER">Officer</option>
              <option value="ADMIN">Administrator</option>
            </select>
          </label>
        </div>
        <div className="form-actions">
          <button type="submit" className="btn btn-primary" disabled={saving}>
            <IconPlus size={16} /> {saving ? "Creating…" : "Create account"}
          </button>
        </div>
      </form>

      <section className="panel">
        <div className="panel-head">
          <div>
            <p className="eyebrow">Access control</p>
            <h2>
              Officers <span className="count-badge">{rows.length}</span>
            </h2>
          </div>
          <span className="panel-note">Deactivated officers are signed out on their next action.</span>
        </div>

        {loading ? (
          <div className="table-loading">Loading officers…</div>
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Username</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th className="align-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const isSelf = row.id === officer.id;
                  return (
                    <tr key={row.id}>
                      <td>
                        <span className="cell-strong">{row.name}</span>
                        {isSelf && <span className="badge">You</span>}
                      </td>
                      <td className="mono">{row.username}</td>
                      <td>
                        <select
                          className="inline-select"
                          value={row.role}
                          disabled={isSelf}
                          aria-label={`Role for ${row.name}`}
                          onChange={(event) =>
                            patchOfficer(row, { role: event.target.value }, "Role updated.")
                          }
                        >
                          <option value="OFFICER">Officer</option>
                          <option value="ADMIN">Administrator</option>
                        </select>
                      </td>
                      <td>
                        <span className={`status-pill ${row.active ? "success" : "muted"}`}>
                          <span className="dot" /> {row.active ? "Active" : "Disabled"}
                        </span>
                      </td>
                      <td className="align-right">
                        <div className="row-actions">
                          <button
                            type="button"
                            className="btn btn-quiet btn-sm"
                            onClick={() => {
                              setResetTarget(row);
                              setResetPassword("");
                            }}
                          >
                            <IconKey size={15} /> Reset password
                          </button>
                          <button
                            type="button"
                            className="btn btn-quiet btn-sm"
                            disabled={isSelf}
                            onClick={() =>
                              patchOfficer(
                                row,
                                { active: !row.active },
                                row.active ? "Account deactivated." : "Account reactivated.",
                              )
                            }
                          >
                            {row.active ? "Deactivate" : "Activate"}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {resetTarget && (
        <Modal
          title={`Reset password for ${resetTarget.name}`}
          description="The new password takes effect immediately."
          onClose={() => setResetTarget(null)}
          footer={
            <>
              <button type="button" className="btn btn-quiet" onClick={() => setResetTarget(null)}>
                Cancel
              </button>
              <button
                type="submit"
                form="reset-password-form"
                className="btn btn-primary"
                disabled={resetSaving}
              >
                {resetSaving ? "Saving…" : "Set password"}
              </button>
            </>
          }
        >
          <form id="reset-password-form" onSubmit={submitReset}>
            <label className="field">
              <span>New password</span>
              <input
                type="password"
                value={resetPassword}
                onChange={(event) => setResetPassword(event.target.value)}
                minLength={8}
                autoComplete="new-password"
                required
              />
              <small>At least 8 characters.</small>
            </label>
          </form>
        </Modal>
      )}
    </div>
  );
}

/* --------------------------------------------------------------------- rooms */

function RoomsTab({ showToast }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ room_name: "", building: "A" });
  const [saving, setSaving] = useState(false);
  const [renameTarget, setRenameTarget] = useState(null);
  const [renameValue, setRenameValue] = useState("");
  const [renameSaving, setRenameSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api("/api/rooms?include_inactive=1");
      setRows(data.rooms || []);
    } catch (error) {
      showToast(error.message, "error");
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    load();
  }, [load]);

  async function createRoom(event) {
    event.preventDefault();
    setSaving(true);
    try {
      await api("/api/rooms", { method: "POST", body: form });
      showToast(`Room ${form.room_name.toUpperCase()} added.`, "success");
      setForm({ room_name: "", building: "A" });
      load();
    } catch (error) {
      showToast(error.message, "error");
    } finally {
      setSaving(false);
    }
  }

  async function patchRoom(row, body, message) {
    try {
      await api(`/api/rooms/${row.id}`, { method: "PATCH", body });
      showToast(message, "success");
      load();
    } catch (error) {
      showToast(error.message, "error");
    }
  }

  async function submitRename(event) {
    event.preventDefault();
    setRenameSaving(true);
    try {
      await api(`/api/rooms/${renameTarget.id}`, {
        method: "PATCH",
        body: { room_name: renameValue },
      });
      showToast("Room renamed.", "success");
      setRenameTarget(null);
      load();
    } catch (error) {
      showToast(error.message, "error");
    } finally {
      setRenameSaving(false);
    }
  }

  return (
    <div className="stack">
      <form className="panel form-panel" onSubmit={createRoom}>
        <div className="panel-head">
          <div>
            <p className="eyebrow">Room register</p>
            <h2>Add a room</h2>
          </div>
          <span className="panel-note">Room names are sorted by their integer part.</span>
        </div>
        <div className="form-grid two">
          <label className="field">
            <span>Room name</span>
            <input
              value={form.room_name}
              onChange={(event) => setForm({ ...form, room_name: event.target.value })}
              placeholder="e.g. KLH106"
              required
            />
          </label>
          <label className="field">
            <span>Building</span>
            <input
              value={form.building}
              onChange={(event) => setForm({ ...form, building: event.target.value })}
              placeholder="A"
              maxLength={40}
            />
          </label>
        </div>
        <div className="form-actions">
          <button type="submit" className="btn btn-primary" disabled={saving}>
            <IconPlus size={16} /> {saving ? "Adding…" : "Add room"}
          </button>
        </div>
      </form>

      <section className="panel">
        <div className="panel-head">
          <div>
            <p className="eyebrow">Inventory</p>
            <h2>
              Rooms <span className="count-badge">{rows.length}</span>
            </h2>
          </div>
          <span className="panel-note">Renaming is blocked while a room is in progress.</span>
        </div>

        {loading ? (
          <div className="table-loading">Loading rooms…</div>
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Room</th>
                  <th>Number</th>
                  <th>Building</th>
                  <th>Status</th>
                  <th className="align-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td className="room-cell">{row.room_name}</td>
                    <td className="mono">{row.room_number}</td>
                    <td>{row.building}</td>
                    <td>
                      <span className={`status-pill ${row.active ? "success" : "muted"}`}>
                        <span className="dot" /> {row.active ? "Active" : "Disabled"}
                      </span>
                    </td>
                    <td className="align-right">
                      <div className="row-actions">
                        <button
                          type="button"
                          className="btn btn-quiet btn-sm"
                          onClick={() => {
                            setRenameTarget(row);
                            setRenameValue(row.room_name);
                          }}
                        >
                          Rename
                        </button>
                        <button
                          type="button"
                          className="btn btn-quiet btn-sm"
                          onClick={() =>
                            patchRoom(
                              row,
                              { active: !row.active },
                              row.active ? "Room deactivated." : "Room reactivated.",
                            )
                          }
                        >
                          {row.active ? "Deactivate" : "Activate"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {renameTarget && (
        <Modal
          title={`Rename ${renameTarget.room_name}`}
          description="The numeric sort position updates automatically."
          onClose={() => setRenameTarget(null)}
          footer={
            <>
              <button type="button" className="btn btn-quiet" onClick={() => setRenameTarget(null)}>
                Cancel
              </button>
              <button
                type="submit"
                form="rename-room-form"
                className="btn btn-primary"
                disabled={renameSaving}
              >
                {renameSaving ? "Saving…" : "Save name"}
              </button>
            </>
          }
        >
          <form id="rename-room-form" onSubmit={submitRename}>
            <label className="field">
              <span>Room name</span>
              <input
                value={renameValue}
                onChange={(event) => setRenameValue(event.target.value)}
                required
              />
            </label>
          </form>
        </Modal>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ settings */

function SettingsTab({ showToast }) {
  const { settings, audio, connected } = useLive();
  const nowMs = useClock(1000);
  const [form, setForm] = useState({
    lecture_start: "07:00",
    lecture_duration_min: 180,
    audio_window_min: 30,
    repeat_interval_sec: 300,
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!settings) return;
    setForm({
      lecture_start: settings.lecture_start,
      lecture_duration_min: settings.lecture_duration_min,
      audio_window_min: settings.audio_window_min,
      repeat_interval_sec: settings.repeat_interval_sec,
    });
  }, [settings]);

  const windowEnd = addMinutes(form.lecture_start, form.audio_window_min);
  const lectureEnd = addMinutes(form.lecture_start, form.lecture_duration_min);
  const nextRead =
    audio?.state === "ACTIVE" && audio.next_cycle_at
      ? Math.max(0, Math.floor((Date.parse(audio.next_cycle_at) - nowMs) / 1000))
      : null;

  async function save(event) {
    event.preventDefault();
    setSaving(true);
    try {
      await api("/api/settings", {
        method: "PATCH",
        body: {
          lecture_start: form.lecture_start,
          lecture_duration_min: Number(form.lecture_duration_min),
          audio_window_min: Number(form.audio_window_min),
          repeat_interval_sec: Number(form.repeat_interval_sec),
        },
      });
      showToast("Settings saved. The announcement schedule has been updated.", "success");
    } catch (error) {
      showToast(error.message, "error");
    } finally {
      setSaving(false);
    }
  }

  function setStartNow() {
    setForm((current) => ({ ...current, lecture_start: formatClock(nowMs) }));
    showToast("Lecture start set to the current server time. Save to apply.", "info");
  }

  function resetDefaults() {
    setForm({
      lecture_start: "07:00",
      lecture_duration_min: 180,
      audio_window_min: 30,
      repeat_interval_sec: 300,
    });
    showToast("Defaults restored in the form. Save to apply.", "info");
  }

  return (
    <div className="stack">
      <form className="panel form-panel" onSubmit={save}>
        <div className="panel-head">
          <div>
            <p className="eyebrow">Schedule</p>
            <h2>Lecture and announcement timing</h2>
          </div>
          <span className="panel-note">Times use the server clock.</span>
        </div>

        <div className="form-grid">
          <label className="field">
            <span>Lecture start</span>
            <input
              type="time"
              value={form.lecture_start}
              onChange={(event) => setForm({ ...form, lecture_start: event.target.value })}
              required
            />
            <small>24-hour clock, e.g. 07:00.</small>
          </label>
          <label className="field">
            <span>Lecture duration (minutes)</span>
            <input
              type="number"
              min={30}
              max={720}
              value={form.lecture_duration_min}
              onChange={(event) =>
                setForm({ ...form, lecture_duration_min: event.target.value })
              }
              required
            />
            <small>Used for the end-of-lecture warning.</small>
          </label>
          <label className="field">
            <span>Audio window (minutes)</span>
            <input
              type="number"
              min={5}
              max={180}
              value={form.audio_window_min}
              onChange={(event) => setForm({ ...form, audio_window_min: event.target.value })}
              required
            />
            <small>Counted from the lecture start.</small>
          </label>
          <label className="field">
            <span>Repeat interval</span>
            <select
              value={form.repeat_interval_sec}
              onChange={(event) =>
                setForm({ ...form, repeat_interval_sec: Number(event.target.value) })
              }
            >
              <option value={60}>1 minute</option>
              <option value={120}>2 minutes</option>
              <option value={300}>5 minutes (default)</option>
              <option value={600}>10 minutes</option>
              <option value={900}>15 minutes</option>
            </select>
            <small>Officers can also change this from the console.</small>
          </label>
        </div>

        <div className="settings-preview">
          <div>
            <span>Audio window</span>
            <strong>
              {form.lecture_start}–{windowEnd}
            </strong>
          </div>
          <div>
            <span>Lecture ends</span>
            <strong>{lectureEnd}</strong>
          </div>
          <div>
            <span>Current audio</span>
            <strong>
              {!audio
                ? "—"
                : audio.paused
                  ? "Paused"
                  : audio.state === "ACTIVE"
                    ? "Active"
                    : audio.reason === "BEFORE_WINDOW"
                      ? "Scheduled"
                      : "Closed"}
            </strong>
          </div>
          <div>
            <span>Next read</span>
            <strong>{nextRead != null ? formatCountdown(nextRead) : "—"}</strong>
          </div>
        </div>

        <div className="form-actions split">
          <button type="submit" className="btn btn-primary" disabled={saving || !connected}>
            {saving ? "Saving…" : "Save settings"}
          </button>
          <div className="row-actions">
            <button type="button" className="btn btn-quiet" onClick={setStartNow}>
              Set start to now
            </button>
            <button type="button" className="btn btn-quiet" onClick={resetDefaults}>
              <IconRefresh size={16} /> Reset defaults
            </button>
          </div>
        </div>
        <p className="field-hint">
          To demo announcements outside the normal window, set the lecture start a few minutes before now,
          save, then tick a room. Pause, resume and extend stay available to officers.
        </p>
      </form>
    </div>
  );
}

/* --------------------------------------------------------------------- audit */

function AuditTab({ showToast }) {
  const [officers, setOfficers] = useState([]);
  const [filters, setFilters] = useState({ date: "", room: "", action: "", officer_id: "" });
  const [applied, setApplied] = useState({ date: "", room: "", action: "", officer_id: "" });
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState({ entries: [], total: 0, limit: 50 });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api("/api/officers")
      .then((response) => setOfficers(response.officers || []))
      .catch((error) => showToast(error.message, "error"));
  }, [showToast]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: "50", offset: String(offset) });
      Object.entries(applied).forEach(([key, value]) => {
        if (value) params.set(key, value);
      });
      const response = await api(`/api/audit?${params.toString()}`);
      setData(response);
    } catch (error) {
      showToast(error.message, "error");
    } finally {
      setLoading(false);
    }
  }, [applied, offset, showToast]);

  useEffect(() => {
    load();
  }, [load]);

  function applyFilters(event) {
    event.preventDefault();
    setOffset(0);
    setApplied({ ...filters });
  }

  const from = data.total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + (data.limit || 50), data.total);

  return (
    <div className="stack">
      <section className="panel">
        <div className="panel-head">
          <div>
            <p className="eyebrow">Accountability</p>
            <h2>Audit log</h2>
          </div>
          <button type="button" className="btn btn-quiet btn-sm" onClick={load} disabled={loading}>
            <IconRefresh size={15} /> Refresh
          </button>
        </div>

        <form className="filter-bar" onSubmit={applyFilters}>
          <label className="field compact-field">
            <span>Date</span>
            <input
              type="date"
              value={filters.date}
              onChange={(event) => setFilters({ ...filters, date: event.target.value })}
            />
          </label>
          <label className="field compact-field">
            <span>Room</span>
            <input
              value={filters.room}
              onChange={(event) => setFilters({ ...filters, room: event.target.value })}
              placeholder="e.g. KLH101"
            />
          </label>
          <label className="field compact-field">
            <span>Action</span>
            <select
              value={filters.action}
              onChange={(event) => setFilters({ ...filters, action: event.target.value })}
            >
              <option value="">All actions</option>
              {AUDIT_ACTIONS.map((action) => (
                <option key={action} value={action}>
                  {action}
                </option>
              ))}
            </select>
          </label>
          <label className="field compact-field">
            <span>Officer</span>
            <select
              value={filters.officer_id}
              onChange={(event) => setFilters({ ...filters, officer_id: event.target.value })}
            >
              <option value="">All officers</option>
              {officers.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.name}
                </option>
              ))}
            </select>
          </label>
          <div className="filter-actions">
            <button type="submit" className="btn btn-primary btn-sm">
              Apply
            </button>
            <button
              type="button"
              className="btn btn-quiet btn-sm"
              onClick={() => {
                const cleared = { date: "", room: "", action: "", officer_id: "" };
                setFilters(cleared);
                setApplied(cleared);
                setOffset(0);
              }}
            >
              <IconX size={14} /> Clear
            </button>
          </div>
        </form>

        {loading ? (
          <div className="table-loading">Loading audit entries…</div>
        ) : data.entries.length === 0 ? (
          <div className="empty-state compact">
            <IconList size={26} />
            <p>No audit entries match these filters.</p>
          </div>
        ) : (
          <div className="table-wrap">
            <table className="data-table audit-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Officer</th>
                  <th>Action</th>
                  <th>Room</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {data.entries.map((entry) => (
                  <tr key={entry.id}>
                    <td className="mono nowrap">{formatDateTime(entry.created_at)}</td>
                    <td>
                      <span className="cell-strong">{entry.officer?.name || "—"}</span>
                      <span className="cell-sub">@{entry.officer?.username || "unknown"}</span>
                    </td>
                    <td>
                      <span className={`audit-action ${actionTone(entry.action)}`}>{entry.action}</span>
                    </td>
                    <td>{entry.room_name || <span className="muted">—</span>}</td>
                    <td className="detail-cell">{describeDetail(entry)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="pagination">
          <span>
            {from}–{to} of {data.total}
          </span>
          <div className="row-actions">
            <button
              type="button"
              className="btn btn-quiet btn-sm"
              onClick={() => setOffset((value) => Math.max(0, value - 50))}
              disabled={offset === 0 || loading}
            >
              <IconChevronLeft size={15} /> Previous
            </button>
            <button
              type="button"
              className="btn btn-quiet btn-sm"
              onClick={() => setOffset((value) => value + 50)}
              disabled={offset + 50 >= data.total || loading}
            >
              Next <IconChevronRight size={15} />
            </button>
          </div>
        </div>
      </section>

      <p className="panel-note">
        Every tick, end, login and audio change is recorded automatically. Times use the server clock.
      </p>
    </div>
  );
}
