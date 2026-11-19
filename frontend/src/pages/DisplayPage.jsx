import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { sortSessions } from "../lib/rooms";
import {
  formatClock,
  formatClockSeconds,
  formatDateLong,
  formatInterval,
} from "../lib/time";
import { useClock, useLive } from "../state/LiveContext";
import {
  IconAlert,
  IconArrowRight,
  IconCheckCircle,
  IconMonitor,
  IconSpeaker,
  IconSpeakerOff,
  IconWifiOff,
} from "../components/Icons";

const MIN_CARD_WIDTH = 280;
const MIN_CARD_HEIGHT = 170;
const MAX_CARD_HEIGHT = 250;
const MAX_PAGE_SIZE = 42;

/**
 * Work out how many cards fit on this screen. The grid and the pagination use
 * the same numbers, so a wall display shows more rooms than a laptop and a
 * phone shows only a few without any vertical scrolling.
 */
function measureDisplayLayout(element) {
  if (!element) return { columns: 3, pageSize: 6 };

  const width = element.clientWidth;
  const height = element.clientHeight;
  if (!width || !height) return { columns: 3, pageSize: 6 };

  const gap = Math.min(26, Math.max(16, window.innerWidth * 0.02));
  const columns = Math.max(
    1,
    Math.floor((width + gap) / (MIN_CARD_WIDTH + gap)),
  );

  const cardHeight = Math.min(
    MAX_CARD_HEIGHT,
    Math.max(MIN_CARD_HEIGHT, window.innerHeight * 0.24),
  );
  const styles = window.getComputedStyle(element);
  const verticalPadding =
    (Number.parseFloat(styles.paddingTop) || 0) +
    (Number.parseFloat(styles.paddingBottom) || 0);
  // Reserve room for the page dots once there is more than one page. The
  // value is deliberately a little generous so pagination never pushes the
  // grid into a scrollbar.
  const usableHeight = Math.max(
    cardHeight,
    height - verticalPadding - 48,
  );
  const rows = Math.max(1, Math.floor((usableHeight + gap) / (cardHeight + gap)));
  const pageSize = Math.max(1, Math.min(MAX_PAGE_SIZE, columns * rows));

  return { columns, pageSize };
}

export default function DisplayPage() {
  const {
    sessions,
    audio,
    building,
    connected,
    connectError,
    lastSnapshotAt,
    lastUpdatedAt,
    announcement,
    switchNotice,
    token,
    clockOffset,
  } = useLive();
  const nowMs = useClock(1000);
  const mainRef = useRef(null);
  const [layout, setLayout] = useState({ columns: 3, pageSize: 6 });
  const [page, setPage] = useState(0);
  const [voice, setVoice] = useState(() => window.localStorage.getItem("display-voice") !== "off");
  const [unlocked, setUnlocked] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [authError, setAuthError] = useState(false);
  const lastSpoken = useRef(null);

  const sorted = sortSessions(sessions);
  const pageCount = Math.max(1, Math.ceil(sorted.length / layout.pageSize));
  const safePage = Math.min(page, pageCount - 1);
  const visible = sorted.slice(
    safePage * layout.pageSize,
    safePage * layout.pageSize + layout.pageSize,
  );

  useEffect(() => {
    const element = mainRef.current;
    if (!element) return undefined;

    let frame = 0;
    const apply = () => {
      const next = measureDisplayLayout(element);
      setLayout((current) =>
        current.columns === next.columns && current.pageSize === next.pageSize
          ? current
          : next,
      );
    };
    // Measure once straight away. A screen that is opened in a background tab
    // does not run animation frames, so relying on requestAnimationFrame here
    // would leave a projector showing the default page size.
    const schedule = () => {
      window.cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(apply);
    };

    apply();
    const observer = new ResizeObserver(apply);
    observer.observe(element);
    window.addEventListener("resize", schedule);
    window.addEventListener("orientationchange", schedule);
    document.addEventListener("visibilitychange", apply);

    return () => {
      window.cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener("resize", schedule);
      window.removeEventListener("orientationchange", schedule);
      document.removeEventListener("visibilitychange", apply);
    };
  }, []);

  useEffect(() => {
    setPage(0);
  }, [layout.pageSize]);

  useEffect(() => {
    let cancelled = false;
    const query = token ? `?token=${encodeURIComponent(token)}` : "";
    api(`/api/display/snapshot${query}`).catch((error) => {
      if (!cancelled && error.status === 401) setAuthError(true);
    });
    return () => {
      cancelled = true;
    };
  }, [token]);

  useEffect(() => {
    if (pageCount <= 1) {
      setPage(0);
      return undefined;
    }
    if (page >= pageCount) setPage(0);
    const timer = window.setInterval(() => {
      setPage((current) => (current + 1) % pageCount);
    }, 8000);
    return () => window.clearInterval(timer);
  }, [pageCount, page]);

  useEffect(() => {
    window.localStorage.setItem("display-voice", voice ? "on" : "off");
  }, [voice]);

  useEffect(() => {
    if (!announcement || !voice || !unlocked || !announcement.id) return;
    if (lastSpoken.current === announcement.id) return;
    lastSpoken.current = announcement.id;

    if (!("speechSynthesis" in window)) return;
    const synth = window.speechSynthesis;
    // Skip the cycle rather than overlap an announcement already playing.
    if (synth.speaking) return;

    const utterance = new SpeechSynthesisUtterance(announcement.text);
    utterance.lang = "en-GB";
    utterance.rate = 0.95;
    const voices = synth.getVoices();
    const preferred =
      voices.find((item) => /^en[-_](KE|GB|US)/i.test(item.lang)) ||
      voices.find((item) => /^en/i.test(item.lang));
    if (preferred) utterance.voice = preferred;
    utterance.onstart = () => setSpeaking(true);
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    synth.speak(utterance);
  }, [announcement, voice, unlocked]);

  function enableSound() {
    // A user gesture unlocks speech synthesis on browsers that apply an
    // autoplay policy. The pending announcement is then read immediately.
    if ("speechSynthesis" in window) window.speechSynthesis.resume();
    setUnlocked(true);
    if (!voice) {
      setVoice(true);
      window.localStorage.setItem("display-voice", "on");
    }
  }

  const rejected = connectError && /reject|unauthor|forbidden/i.test(connectError);
  if (authError || rejected) {
    return (
      <div className="display-page display-access-error">
        <div className="access-card">
          <span className="access-icon">
            <IconMonitor size={42} />
          </span>
          <h1>Display link not valid</h1>
          <p>
            This read-only display link is missing or has expired. Open the security console and use
            <strong> Open display</strong> to generate a new one.
          </p>
        </div>
      </div>
    );
  }

  const intervalLabel = audio ? formatInterval(audio.interval_sec) : "5 min";
  const noticeExpiresAt = switchNotice?.expires_at ? Date.parse(switchNotice.expires_at) : null;
  const activeSwitch =
    switchNotice && (noticeExpiresAt == null || noticeExpiresAt > nowMs) ? switchNotice : null;
  const audioFooter = !audio
    ? "Announcements ready"
    : audio.paused
      ? "Announcements paused"
      : audio.state === "ACTIVE"
        ? `Announcements every ${intervalLabel} · window until ${formatClock(audio.window_end)}`
        : audio.reason === "BEFORE_WINDOW"
          ? `Announcements start at ${formatClock(audio.window_start)}`
          : "Announcements finished for this window";

  return (
    <div className="display-page">
      <header className="display-header">
        <div className="display-title">
          <span className="display-building">{building?.name || "Building A"}</span>
          <h1>{building?.label || "LECTURE ROOMS"}</h1>
          <p className="display-tagline">
            Lecturer arrived <span aria-hidden="true">·</span>{" "}
            <span lang="sw">Mhadhiri amefika</span>
          </p>
        </div>

        <div className="display-right">
          <div className="display-clock">
            <div className="clock-time">{formatClock(nowMs)}</div>
            <div className="clock-date">{formatDateLong(nowMs)}</div>
          </div>
          <div className={`live-badge ${connected ? "is-live" : "is-stale"}`}>
            {connected ? (
              <>
                <span className="live-dot" aria-hidden="true" /> LIVE
              </>
            ) : (
              <>
                <IconWifiOff size={16} /> RECONNECTING
              </>
            )}
          </div>
        </div>
      </header>

      {!connected && (
        <div className="stale-banner" role="status" aria-live="polite">
          <IconWifiOff size={18} />
          <span>
            Connection lost. Showing the last known room status
            {lastSnapshotAt ? ` from ${formatClockSeconds(lastSnapshotAt)}` : ""}. Reconnecting automatically…
          </span>
        </div>
      )}

      {activeSwitch && (
        <div
          className="display-switch-banner"
          role="status"
          aria-live="polite"
          key={`${activeSwitch.session_id}-${activeSwitch.at}`}
        >
          <span className="switch-banner-icon" aria-hidden="true">
            <IconArrowRight size={26} />
          </span>
          <div className="switch-banner-copy">
            <span className="switch-banner-label">Room change</span>
            <p>
              <strong>{activeSwitch.from_room}</strong>
              <span className="switch-banner-word">switched to</span>
              <strong>{activeSwitch.to_room}</strong>
            </p>
          </div>
        </div>
      )}

      <main className="display-main" ref={mainRef}>
        {visible.length === 0 ? (
          <div className="display-empty">
            <span className="display-empty-icon">
              <IconCheckCircle size={48} />
            </span>
            <h2>No rooms in progress yet</h2>
            <p>Rooms appear here the moment a lecturer arrives and the officer ticks them in.</p>
          </div>
        ) : (
          <div
            className={`display-grid ${visible.length === 1 ? "one" : visible.length === 2 ? "two" : ""}`}
            style={{ "--display-columns": layout.columns }}
          >
            {visible.map((session) => (
              <article className="display-card" key={session.id}>
                <h2 className="display-card-code">{session.room_name}</h2>
                <div className="display-card-status">
                  <IconCheckCircle size={24} />
                  <span>in progress</span>
                </div>
                {session.lecturer_name && (
                  <p className="display-card-lecturer">{session.lecturer_name}</p>
                )}
              </article>
            ))}
          </div>
        )}

        {pageCount > 1 && (
          <div className="display-pagination" aria-hidden="true">
            {Array.from({ length: pageCount }).map((_, index) => (
              <span key={index} className={`page-dot ${index === safePage ? "is-active" : ""}`} />
            ))}
            <span className="page-count">
              {safePage + 1} / {pageCount}
            </span>
          </div>
        )}
      </main>

      <footer className="display-footer">
        <div className="display-audio-state">
          <IconSpeaker size={18} />
          <span>{audioFooter}</span>
          {speaking && (
            <span className="announcing">
              <span className="speaking-dot" aria-hidden="true" /> Announcing…
            </span>
          )}
        </div>

        <div className="display-updated">
          {lastUpdatedAt ? `Updated ${formatClockSeconds(lastUpdatedAt)}` : "Waiting for data…"}
        </div>

        <div className="display-sound">
          {voice && !unlocked && (
            <button type="button" className="audio-unlock" onClick={enableSound}>
              Tap to enable sound
            </button>
          )}
          <button
            type="button"
            className="sound-toggle"
            onClick={() => {
              const next = !voice;
              setVoice(next);
              if (next) {
                enableSound();
              } else if ("speechSynthesis" in window) {
                window.speechSynthesis.cancel();
                setSpeaking(false);
              }
            }}
            aria-pressed={voice}
            title={voice ? "Mute announcements on this screen" : "Unmute announcements on this screen"}
          >
            {voice ? <IconSpeaker size={17} /> : <IconSpeakerOff size={17} />}
            <span>{voice ? "Sound on" : "Sound off"}</span>
          </button>
        </div>
      </footer>

      <div className="sr-only" role="status" aria-live="polite">
        {announcement?.text || ""}
      </div>
      {!audio && connected && (
        <div className="display-audio-warning">
          <IconAlert size={15} /> Audio state unavailable
        </div>
      )}
    </div>
  );
}
