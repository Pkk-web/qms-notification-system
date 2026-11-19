export function toDate(value) {
  if (!value) return null;
  if (value instanceof Date) return value;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function formatClock(value) {
  const date = toDate(value);
  if (!date) return "--:--";
  return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

export function formatClockSeconds(value) {
  const date = toDate(value);
  if (!date) return "--:--:--";
  return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}:${String(
    date.getSeconds(),
  ).padStart(2, "0")}`;
}

export function formatDateLong(value) {
  const date = toDate(value);
  if (!date) return "";
  return date.toLocaleDateString(undefined, {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export function formatDateShort(value) {
  const date = toDate(value);
  if (!date) return "—";
  return date.toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" });
}

export function formatElapsed(totalSeconds) {
  const seconds = Math.max(0, Math.floor(totalSeconds || 0));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return `${hours}:${String(minutes).padStart(2, "0")}`;
}

export function formatCountdown(totalSeconds) {
  const seconds = Math.max(0, Math.floor(totalSeconds || 0));
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  if (minutes >= 60) {
    const hours = Math.floor(minutes / 60);
    return `${hours}:${String(minutes % 60).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
  }
  return `${minutes}:${String(rest).padStart(2, "0")}`;
}

export function formatInterval(seconds) {
  const minutes = Math.round((seconds || 0) / 60);
  if (minutes < 1) return `${seconds}s`;
  return `${minutes} min`;
}

export function elapsedSince(startedAt, nowMs) {
  const start = toDate(startedAt);
  if (!start) return 0;
  return Math.max(0, Math.floor((nowMs - start.getTime()) / 1000));
}

export function formatDateTime(value) {
  const date = toDate(value);
  if (!date) return "—";
  return `${formatDateShort(date)} · ${formatClockSeconds(date)}`;
}
