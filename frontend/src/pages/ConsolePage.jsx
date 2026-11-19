import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../lib/api";
import { sortRooms, sortSessions } from "../lib/rooms";
import {
  elapsedSince,
  formatClock,
  formatCountdown,
  formatElapsed,
  formatInterval,
} from "../lib/time";
import { navigate } from "../lib/useHashRoute";
import { useAuth } from "../state/AuthContext";
import { useClock, useLive } from "../state/LiveContext";
import { Modal } from "../components/Modal";
import { TopBar } from "../components/TopBar";
import { Toast, useToast } from "../components/Toast";
import {
  IconArrowRight,
  IconCheck,
  IconCheckCircle,
  IconClock,
  IconDoor,
  IconMonitor,
  IconPause,
  IconPlay,
  IconPlus,
  IconSearch,
  IconShield,
  IconSpeaker,
  IconWifiOff,
  IconX,
} from "../components/Icons";

const INTERVAL_OPTIONS = [
  { value: 60, label: "1 minute" },
  { value: 120, label: "2 minutes" },
  { value: 300, label: "5 minutes (default)" },
  { value: 600, label: "10 minutes" },
  { value: 900, label: "15 minutes" },
];

export default function ConsolePage() {
  const { officer, logout } = useAuth();
  const { sessions, settings, audio, connected, building, roomsVersion, switchNotice } = useLive();
  const nowMs = useClock(1000);
  const { toast, show: showToast, clear: clearToast } = useToast();

  const [rooms, setRooms] = useState([]);
  const [roomsLoading, setRoomsLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState(null);
  const [lecturer, setLecturer] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [endingId, setEndingId] = useState(null);
  const [undo, setUndo] = useState(null);
  const [switchTarget, setSwitchTarget] = useState(null);
  const [switchRoom, setSwitchRoom] = useState("");
  const [switching, setSwitching] = useState(false);
  const [dismissedNotice, setDismissedNotice] = useState(null);

  const searchRef = useRef(null);
  const lecturerRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    setRoomsLoading(true);
    api("/api/rooms")
      .then((data) => {
        if (!cancelled) setRooms(sortRooms(data.rooms || []));
      })
      .catch((error) => {
        if (!cancelled && error.status !== 401) showToast(error.message, "error");
      })
      .finally(() => {
        if (!cancelled) setRoomsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [roomsVersion, showToast]);

  const activeByRoom = useMemo(
    () => new Map(sessions.map((row) => [row.room_name, row])),
    [sessions],
  );
  const sortedSessions = useMemo(() => sortSessions(sessions), [sessions]);
  const filteredRooms = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return rooms;
    return rooms.filter((room) => room.room_name.toLowerCase().includes(term));
  }, [rooms, search]);

  const switchOptions = useMemo(() => {
    if (!switchTarget) return [];
    return rooms.filter(
      (room) =>
        room.room_name !== switchTarget.room_name &&
        !activeByRoom.has(room.room_name),
    );
  }, [rooms, activeByRoom, switchTarget]);

  const noticeKey = switchNotice
    ? `${switchNotice.session_id}-${switchNotice.at}`
    : null;
  const noticeExpiresAt = switchNotice?.expires_at
    ? Date.parse(switchNotice.expires_at)
    : null;
  const noticeFresh =
    Boolean(switchNotice) &&
    (noticeExpiresAt == null || noticeExpiresAt > nowMs) &&
    dismissedNotice !== noticeKey;

  const windowStart = audio ? formatClock(audio.window_start) : settings?.lecture_start || "07:00";
  const windowEnd = audio ? formatClock(audio.window_end) : "—";
  const nextIn =
    audio?.state === "ACTIVE" && audio.next_cycle_at
      ? Math.max(0, Math.floor((Date.parse(audio.next_cycle_at) - nowMs) / 1000))
      : null;

  const audioTone = !audio
    ? "muted"
    : audio.paused
      ? "warning"
      : audio.state === "ACTIVE"
        ? "success"
        : "muted";
  const audioLabel = !audio
    ? "—"
    : audio.paused
      ? "Paused"
      : audio.state === "ACTIVE"
        ? "Active"
        : audio.reason === "BEFORE_WINDOW"
          ? "Scheduled"
          : "Closed";
  const audioSummary = !audio
    ? "Loading audio state…"
    : audio.paused
      ? "Paused — no announcements"
      : audio.state === "ACTIVE"
        ? nextIn != null
          ? `Next read in ${formatCountdown(nextIn)}`
          : "Announcements active"
        : audio.reason === "BEFORE_WINDOW"
          ? `Starts ${formatClock(audio.window_start)}`
          : "Audio window closed";

  const lectureEndMs = audio?.lecture_end ? Date.parse(audio.lecture_end) : null;
  const minutesToLectureEnd = lectureEndMs ? (lectureEndMs - nowMs) / 60000 : null;
  const lectureWarning =
    sessions.length > 0 && minutesToLectureEnd != null && minutesToLectureEnd <= 15
      ? minutesToLectureEnd < 0
        ? "The lecture window has ended. End sessions manually when each room is free."
        : `The lecture window ends at ${formatClock(audio.lecture_end)}. Remember to end sessions manually.`
      : null;

  useEffect(() => {
    if (selected && activeByRoom.has(selected)) {
      setSelected(null);
      setLecturer("");
    }
  }, [activeByRoom, selected]);

  useEffect(() => {
    if (!undo) return undefined;
    const timer = window.setTimeout(() => setUndo(null), 10000);
    return () => window.clearTimeout(timer);
  }, [undo]);

  const selectRoom = useCallback((roomName) => {
    setSelected(roomName);
    window.requestAnimationFrame(() => lecturerRef.current?.focus());
  }, []);

  const clearSelection = useCallback(() => {
    setSelected(null);
    setLecturer("");
  }, []);

  const handleTick = useCallback(
    async (event) => {
      event?.preventDefault();
      if (!selected || submitting || !connected) return;
      setSubmitting(true);
      try {
        const data = await api("/api/sessions", {
          method: "POST",
          body: {
            room_name: selected,
            lecturer_name: lecturer.trim() || undefined,
          },
        });
        setUndo({
          sessionId: data.session.id,
          roomName: data.session.room_name,
          at: Date.now(),
        });
        setSelected(null);
        setLecturer("");
        showToast(`${data.session.room_name} marked in progress.`, "success");
      } catch (error) {
        showToast(error.message, "error");
        if (error.status === 409) clearSelection();
      } finally {
        setSubmitting(false);
      }
    },
    [selected, lecturer, submitting, connected, showToast, clearSelection],
  );

  const endSession = useCallback(
    async (session) => {
      if (endingId) return;
      setEndingId(session.id);
      try {
        await api(`/api/sessions/${session.id}/end`, { method: "POST" });
        setUndo((current) => (current?.sessionId === session.id ? null : current));
        showToast(`${session.room_name} session ended.`, "info");
      } catch (error) {
        showToast(error.message, "error");
      } finally {
        setEndingId(null);
      }
    },
    [endingId, showToast],
  );

  const openSwitch = useCallback(
    (session) => {
      const firstFree = rooms.find(
        (room) =>
          room.room_name !== session.room_name &&
          !activeByRoom.has(room.room_name),
      );
      setSwitchTarget(session);
      setSwitchRoom(firstFree?.room_name || "");
    },
    [rooms, activeByRoom],
  );

  const closeSwitch = useCallback(() => {
    if (switching) return;
    setSwitchTarget(null);
    setSwitchRoom("");
  }, [switching]);

  const handleSwitch = useCallback(
    async (event) => {
      event?.preventDefault();
      if (!switchTarget || !switchRoom || switching) return;
      setSwitching(true);
      try {
        const data = await api(`/api/sessions/${switchTarget.id}/switch`, {
          method: "POST",
          body: { room_name: switchRoom },
        });
        setDismissedNotice(null);
        setSwitchTarget(null);
        setSwitchRoom("");
        showToast(`${data.from_room} moved to ${data.to_room}.`, "success");
      } catch (error) {
        showToast(error.message, "error");
      } finally {
        setSwitching(false);
      }
    },
    [switchTarget, switchRoom, switching, showToast],
  );

  const undoEnd = useCallback(async () => {
    if (!undo) return;
    try {
      await api(`/api/sessions/${undo.sessionId}/end`, {
        method: "POST",
        body: { undo: true },
      });
      showToast("Tick undone — the room has been removed from the display.", "info");
    } catch (error) {
      showToast(error.message, "error");
    } finally {
      setUndo(null);
    }
  }, [undo, showToast]);

  const togglePause = useCallback(async () => {
    if (!connected) return;
    const pausing = !audio?.paused;
    try {
      await api(`/api/audio/${pausing ? "pause" : "resume"}`, { method: "POST" });
      showToast(pausing ? "Audio paused." : "Audio resumed.", "info");
    } catch (error) {
      showToast(error.message, "error");
    }
  }, [audio?.paused, connected, showToast]);

  const extendWindow = useCallback(async () => {
    if (!connected) return;
    try {
      await api("/api/audio/extend", { method: "POST", body: { minutes: 15 } });
      showToast("Audio window extended by 15 minutes.", "success");
    } catch (error) {
      showToast(error.message, "error");
    }
  }, [connected, showToast]);

  const changeInterval = useCallback(
    async (event) => {
      const seconds = Number(event.target.value);
      try {
        await api("/api/settings", {
          method: "PATCH",
          body: { repeat_interval_sec: seconds },
        });
        showToast(`Announcement interval set to ${formatInterval(seconds)}.`, "success");
      } catch (error) {
        showToast(error.message, "error");
      }
    },
    [showToast],
  );

  const testAnnouncement = useCallback(async () => {
    try {
      const data = await api("/api/audio/test", { method: "POST" });
      showToast(data.text, "success");
    } catch (error) {
      showToast(error.message, "error");
    }
  }, [showToast]);

  const openDisplay = useCallback(async () => {
    const popup = window.open("about:blank", "_blank");
    try {
      const data = await api("/api/display/token");
      const url = `${window.location.origin}${data.path}`;
      if (popup) popup.location.href = url;
      else window.open(url, "_blank");
    } catch (error) {
      popup?.close();
      showToast(error.message, "error");
    }
  }, [showToast]);

  useEffect(() => {
    const onKeyDown = (event) => {
      const tag = (event.target.tagName || "").toLowerCase();
      const typing =
        ["input", "textarea", "select"].includes(tag) || event.target.isContentEditable;

      if (event.key === "/" && !typing) {
        event.preventDefault();
        searchRef.current?.focus();
        return;
      }
      if (event.key === "Escape") {
        clearSelection();
        if (typing) event.target.blur();
        return;
      }
      if (
        event.code === "Space" &&
        !typing &&
        !event.target.closest("button, a")
      ) {
        event.preventDefault();
        if (connected && audio) togglePause();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [audio, connected, clearSelection, togglePause]);

  return (
    <div className="console-page">
      <TopBar
        officer={officer}
        connected={connected}
        onLogout={logout}
        subtitle={`Security console · ${building?.name || "Building A"}`}
      >
        <div className="audio-mini" title={`Audio window ${windowStart}–${windowEnd}`}>
          <span className={`pulse-dot tone-${audioTone}`} aria-hidden="true" />
          <div>
            <strong>{audioSummary}</strong>
            <span>
              Audio {windowStart}–{windowEnd}
            </span>
          </div>
        </div>
        <div className="topbar-buttons">
          <button
            type="button"
            className="btn btn-quiet btn-sm"
            onClick={togglePause}
            disabled={!connected || !audio}
            data-audio-toggle
          >
            {audio?.paused ? <IconPlay size={16} /> : <IconPause size={16} />}
            {audio?.paused ? "Resume" : "Pause"}
          </button>
          <button
            type="button"
            className="btn btn-quiet btn-sm"
            onClick={extendWindow}
            disabled={!connected}
          >
            Extend +15
          </button>
        </div>
        {officer.role === "ADMIN" && (
          <button type="button" className="btn btn-quiet btn-sm" onClick={() => navigate("/admin")}>
            <IconShield size={16} /> Admin
          </button>
        )}
      </TopBar>

      {!connected && (
        <div className="banner banner-offline" role="alert">
          <IconWifiOff size={18} />
          <div>
            <strong>You are offline.</strong> Registration is disabled while the connection is down. Use the
            manual fallback at the desk and the room list will reconcile automatically when you reconnect.
          </div>
        </div>
      )}
      {lectureWarning && (
        <div className="banner banner-warning" role="status">
          <IconClock size={18} />
          <div>{lectureWarning}</div>
        </div>
      )}
      {noticeFresh && (
        <div className="banner banner-info" role="status">
          <IconArrowRight size={18} />
          <div>
            <strong>
              {switchNotice.from_room} switched to {switchNotice.to_room}.
            </strong>{" "}
            The public display and announcement have been updated.
          </div>
          <button
            type="button"
            className="icon-btn banner-dismiss"
            onClick={() => setDismissedNotice(noticeKey)}
            aria-label="Dismiss room change notice"
          >
            <IconX size={14} />
          </button>
        </div>
      )}

      <main className="console-main">
        <section className="panel room-panel" aria-labelledby="rooms-title">
          <div className="panel-head">
            <div>
              <p className="eyebrow">
                <span className="step">1</span> Choose a room
              </p>
              <h2 id="rooms-title">Room grid</h2>
            </div>
            <div className="search-field">
              <IconSearch size={17} />
              <input
                ref={searchRef}
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search room…"
                aria-label="Search rooms"
              />
              {search ? (
                <button
                  type="button"
                  className="icon-btn search-clear"
                  onClick={() => setSearch("")}
                  aria-label="Clear search"
                >
                  <IconX size={14} />
                </button>
              ) : (
                <kbd>/</kbd>
              )}
            </div>
          </div>

          {roomsLoading ? (
            <div className="room-grid" aria-busy="true" aria-label="Loading rooms">
              {Array.from({ length: 9 }).map((_, index) => (
                <div className="room-card skeleton" key={index} />
              ))}
            </div>
          ) : filteredRooms.length === 0 ? (
            <div className="empty-state compact">
              <IconDoor size={28} />
              <p>No rooms match &ldquo;{search}&rdquo;.</p>
              <button type="button" className="link-btn" onClick={() => setSearch("")}>
                Clear search
              </button>
            </div>
          ) : (
            <div className="room-grid">
              {filteredRooms.map((room) => {
                const active = activeByRoom.get(room.room_name);
                const isSelected = selected === room.room_name;
                return (
                  <div
                    key={room.id}
                    className={`room-card ${active ? "is-active" : ""} ${isSelected ? "is-selected" : ""}`}
                  >
                    <button
                      type="button"
                      className="room-card-hit"
                      onClick={() => selectRoom(room.room_name)}
                      disabled={Boolean(active)}
                      aria-pressed={isSelected}
                    >
                      <span className="room-code">{room.room_name}</span>
                      <span className={`room-status ${active ? "active" : isSelected ? "selected" : ""}`}>
                        {active ? (
                          <>
                            <IconCheck size={14} /> In progress
                          </>
                        ) : isSelected ? (
                          "Selected"
                        ) : (
                          "Available"
                        )}
                      </span>
                      {active?.lecturer_name && (
                        <span className="room-lecturer">{active.lecturer_name}</span>
                      )}
                    </button>
                    {active && (
                      <button
                        type="button"
                        className="room-end"
                        onClick={() => endSession(active)}
                        disabled={endingId === active.id}
                        aria-label={`End ${room.room_name} session`}
                      >
                        {endingId === active.id ? "Ending…" : "End"}
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          <div className="room-legend">
            <span>
              <span className="legend-swatch available" /> Available
            </span>
            <span>
              <span className="legend-swatch selected" /> Selected
            </span>
            <span>
              <span className="legend-swatch active" /> In progress
            </span>
            <span className="legend-spacer" />
            <span>{rooms.length} rooms</span>
          </div>
        </section>

        <div className="side-column">
          <form className="panel confirm-panel" onSubmit={handleTick}>
            <div className="panel-head">
              <div>
                <p className="eyebrow">
                  <span className="step">2</span> Lecturer <span className="step">3</span> Confirm
                </p>
                <h2>Mark in progress</h2>
              </div>
            </div>

            <label className="field">
              <span>
                Lecturer name <em>optional</em>
              </span>
              <input
                ref={lecturerRef}
                value={lecturer}
                onChange={(event) => setLecturer(event.target.value)}
                placeholder="e.g. Mr Paul"
                maxLength={120}
              />
            </label>

            <div className={`confirm-summary ${selected ? "has-room" : ""}`}>
              <div>
                <span>Selected room</span>
                <strong>{selected || "None selected"}</strong>
              </div>
              {selected && (
                <button type="button" className="link-btn" onClick={clearSelection}>
                  Cancel
                </button>
              )}
            </div>

            <button
              type="submit"
              className="btn btn-primary btn-lg confirm-btn"
              disabled={!selected || !connected || submitting}
            >
              {submitting ? "Marking…" : "Mark in progress"}
              <kbd>Enter</kbd>
            </button>
            <p className="field-hint">
              {connected
                ? "The room appears on the display immediately and joins the next audio cycle."
                : "Registration is disabled while offline."}
            </p>
          </form>

          <section className="panel audio-card" aria-labelledby="audio-title">
            <div className="panel-head">
              <div>
                <p className="eyebrow">Announcements</p>
                <h2 id="audio-title">Audio window</h2>
              </div>
              <span className={`status-pill ${audioTone}`}>
                <span className="dot" aria-hidden="true" />
                {audioLabel}
              </span>
            </div>

            <div className="audio-window">
              <span className="audio-window-time">
                {windowStart}–{windowEnd}
              </span>
              {audio?.extended && <span className="badge badge-warning">Extended</span>}
            </div>
            <p className="audio-summary">
              {audio?.state === "ACTIVE" && !audio.paused
                ? nextIn != null
                  ? `Next read in ${formatCountdown(nextIn)}`
                  : "Announcements active"
                : audio?.paused
                  ? "Announcements are paused"
                  : audio?.reason === "BEFORE_WINDOW"
                    ? `Announcements start at ${formatClock(audio.window_start)}`
                    : "Audio window is closed"}
            </p>

            <div className="audio-controls">
              <button
                type="button"
                className="btn btn-quiet"
                onClick={togglePause}
                disabled={!connected || !audio}
              >
                {audio?.paused ? <IconPlay size={16} /> : <IconPause size={16} />}
                {audio?.paused ? "Resume" : "Pause"}
              </button>
              <button type="button" className="btn btn-quiet" onClick={extendWindow} disabled={!connected}>
                <IconPlus size={16} /> Extend +15
              </button>
              <button
                type="button"
                className="btn btn-quiet"
                onClick={testAnnouncement}
                disabled={!connected || sessions.length === 0}
                title={
                  sessions.length === 0
                    ? "Tick a room first"
                    : "Speak the current list on the display now"
                }
              >
                <IconSpeaker size={16} /> Test
              </button>
            </div>

            <div className="audio-select-row">
              <label className="field compact-field">
                <span>Repeat interval</span>
                <select value={settings?.repeat_interval_sec || 300} onChange={changeInterval}>
                  {INTERVAL_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <button type="button" className="btn btn-quiet" onClick={openDisplay}>
                <IconMonitor size={16} /> Open display
              </button>
            </div>

            {audio?.last_announcement_at && (
              <p className="audio-last">
                Last read at {formatClock(audio.last_announcement_at)}
                {audio.skipped_cycles > 0 ? ` · ${audio.skipped_cycles} cycle(s) skipped` : ""}
              </p>
            )}
          </section>
        </div>

        <section className="panel sessions-panel" aria-labelledby="sessions-title">
          <div className="panel-head">
            <div>
              <p className="eyebrow">Live register</p>
              <h2 id="sessions-title">
                In-progress sessions <span className="count-badge">{sortedSessions.length}</span>
              </h2>
            </div>
            <span className="panel-note">Updates live · numeric room order</span>
          </div>

          {sortedSessions.length === 0 ? (
            <div className="empty-state">
              <span className="empty-icon">
                <IconDoor size={30} />
              </span>
              <h3>No rooms in progress yet</h3>
              <p>Pick a room above when its lecturer arrives. It will appear here and on the public display.</p>
            </div>
          ) : (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Room</th>
                    <th>Lecturer</th>
                    <th>Since</th>
                    <th>Elapsed</th>
                    <th className="align-right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedSessions.map((session) => {
                    const elapsed = elapsedSince(session.started_at, nowMs);
                    const elapsedTone =
                      elapsed >= 3 * 3600 ? "danger" : elapsed >= 2 * 3600 ? "warning" : "";
                    return (
                      <tr key={session.id}>
                        <td className="room-cell">{session.room_name}</td>
                        <td>{session.lecturer_name || <span className="muted">—</span>}</td>
                        <td className="mono">{formatClock(session.started_at)}</td>
                        <td>
                          <span className={`elapsed ${elapsedTone}`}>{formatElapsed(elapsed)}</span>
                        </td>
                        <td className="align-right">
                          <div className="row-actions">
                            <button
                              type="button"
                              className="btn btn-quiet btn-sm"
                              onClick={() => openSwitch(session)}
                              disabled={endingId === session.id}
                            >
                              <IconArrowRight size={15} /> Switch
                            </button>
                            <button
                              type="button"
                              className="btn btn-danger-quiet btn-sm"
                              onClick={() => endSession(session)}
                              disabled={endingId === session.id}
                            >
                              {endingId === session.id ? "Ending…" : "End"}
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
      </main>

      <footer className="console-footer">
        <span>
          Keyboard: <kbd>/</kbd> search · <kbd>Enter</kbd> confirm · <kbd>Esc</kbd> cancel · <kbd>Space</kbd>{" "}
          pause
        </span>
        <span>Updates in real time · WCAG 2.1 AA target</span>
      </footer>

      {switchTarget && (
        <Modal
          title="Switch room"
          description={`Move the ${switchTarget.room_name} lecture to another room. The start time, lecturer and officer stay the same.`}
          onClose={closeSwitch}
          width={470}
          footer={
            <>
              <button type="button" className="btn btn-quiet" onClick={closeSwitch} disabled={switching}>
                Cancel
              </button>
              <button
                type="submit"
                form="switch-room-form"
                className="btn btn-primary"
                disabled={!switchRoom || switching}
              >
                {switching ? "Switching…" : "Switch room"}
              </button>
            </>
          }
        >
          <form id="switch-room-form" onSubmit={handleSwitch} className="switch-form">
            <div className="switch-route" aria-hidden="true">
              <span className="switch-route-room">{switchTarget.room_name}</span>
              <IconArrowRight size={18} />
              <span className="switch-route-room target">{switchRoom || "Choose room"}</span>
            </div>

            {switchOptions.length === 0 ? (
              <p className="empty-state compact">
                No other rooms are free right now. End a session before switching.
              </p>
            ) : (
              <label className="field">
                <span>Move to room</span>
                <select value={switchRoom} onChange={(event) => setSwitchRoom(event.target.value)}>
                  {switchOptions.map((room) => (
                    <option key={room.id} value={room.room_name}>
                      {room.room_name}
                    </option>
                  ))}
                </select>
              </label>
            )}

            <p className="field-hint">
              {switchRoom
                ? `The display will show “${switchTarget.room_name} switched to ${switchRoom}” and the speaker will announce the change.`
                : "Choose a free room to continue."}
            </p>
          </form>
        </Modal>
      )}

      <div className="toast-stack">
        {undo && (
          <div className="undo-toast" key={undo.at} role="status" aria-live="polite">
            <span className="undo-icon">
              <IconCheckCircle size={20} />
            </span>
            <div className="undo-copy">
              <strong>{undo.roomName} is in progress</strong>
              <span>Undo available for 10 seconds</span>
            </div>
            <button type="button" className="btn btn-inverse btn-sm" onClick={undoEnd}>
              Undo
            </button>
            <span className="undo-bar" aria-hidden="true" />
          </div>
        )}
        <Toast toast={toast} onClose={clearToast} />
      </div>
    </div>
  );
}
