import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { io } from "socket.io-client";
import { sortSessions } from "../lib/rooms";
import { useHashRoute } from "../lib/useHashRoute";
import { useAuth } from "./AuthContext";

const LiveContext = createContext(null);

const INITIAL = {
  sessions: [],
  settings: null,
  audio: null,
  revision: 0,
  building: { name: "Building A", label: "LECTURE ROOMS" },
  connected: false,
  connectError: null,
  lastSnapshotAt: null,
  lastUpdatedAt: null,
  roomsVersion: 0,
  announcement: null,
  switchNotice: null,
};

function withRevision(state, revision, updater) {
  // Discard out-of-order events; snapshots bypass this and replace state.
  if (typeof revision === "number" && revision <= (state.revision || 0)) {
    return state;
  }
  return updater(state);
}

export function LiveProvider({ children }) {
  const { officer, loading } = useAuth();
  const route = useHashRoute();
  const isDisplay = route.path.startsWith("/display");
  const token = isDisplay ? route.query.get("token") : null;
  const [state, setState] = useState(INITIAL);
  const [clockOffset, setClockOffset] = useState(0);
  const socketRef = useRef(null);
  const offsetRef = useRef(0);

  const syncClock = useCallback((serverNow) => {
    if (!serverNow) return;
    const parsed = Date.parse(serverNow);
    if (Number.isNaN(parsed)) return;
    const offset = parsed - Date.now();
    offsetRef.current = offset;
    setClockOffset(offset);
  }, []);

  useEffect(() => {
    if (loading) return;

    // The display connects read-only (optionally with a signed token); the
    // console only connects once an officer session exists.
    if (!officer && !isDisplay) {
      if (socketRef.current) {
        socketRef.current.disconnect();
        socketRef.current = null;
      }
      return undefined;
    }

    const socket = io({
      auth: token ? { token } : {},
      withCredentials: true,
      transports: ["websocket", "polling"],
      reconnectionDelayMax: 5000,
    });
    socketRef.current = socket;

    const touch = () => setState((prev) => ({ ...prev, lastUpdatedAt: Date.now() }));

    socket.on("connect", () => {
      setState((prev) => ({ ...prev, connected: true, connectError: null }));
    });

    socket.on("disconnect", () => {
      setState((prev) => ({ ...prev, connected: false }));
    });

    socket.on("connect_error", (error) => {
      setState((prev) => ({
        ...prev,
        connected: false,
        connectError: error?.message || "Cannot reach the server.",
      }));
    });

    socket.on("snapshot", (snapshot) => {
      syncClock(snapshot.server_now);
      setState((prev) => ({
        ...prev,
        sessions: sortSessions(snapshot.sessions || []),
        settings: snapshot.settings || prev.settings,
        audio: snapshot.audio_state || prev.audio,
        revision: snapshot.revision ?? prev.revision,
        building: snapshot.building || prev.building,
        switchNotice: snapshot.switch_notice || null,
        lastSnapshotAt: Date.now(),
        lastUpdatedAt: Date.now(),
        connected: true,
        connectError: null,
      }));
    });

    socket.on("session:created", ({ session, revision }) => {
      setState((prev) =>
        withRevision(prev, revision, (current) => ({
          ...current,
          revision,
          sessions: sortSessions([
            ...current.sessions.filter((row) => row.id !== session.id),
            session,
          ]),
          lastUpdatedAt: Date.now(),
        })),
      );
    });

    socket.on("session:ended", ({ session, session_id, revision }) => {
      setState((prev) =>
        withRevision(prev, revision, (current) => ({
          ...current,
          revision,
          sessions: current.sessions.filter(
            (row) => row.id !== (session?.id ?? session_id),
          ),
          lastUpdatedAt: Date.now(),
        })),
      );
    });

    socket.on(
      "session:switched",
      ({ session, from_room, to_room, switch_notice, revision }) => {
        setState((prev) =>
          withRevision(prev, revision, (current) => ({
            ...current,
            revision,
            sessions: sortSessions([
              ...current.sessions.filter((row) => row.id !== session.id),
              session,
            ]),
            switchNotice:
              switch_notice || {
                session_id: session.id,
                from_room,
                to_room,
                text: `${from_room} switched to ${to_room}`,
              },
            lastUpdatedAt: Date.now(),
          })),
        );
      },
    );

    socket.on("settings:updated", ({ settings, audio_state, revision }) => {
      setState((prev) =>
        withRevision(prev, revision, (current) => ({
          ...current,
          revision,
          settings,
          audio: audio_state || current.audio,
          lastUpdatedAt: Date.now(),
        })),
      );
      syncClock(audio_state?.server_now);
    });

    socket.on("audio:state", (audio) => {
      setState((prev) => ({ ...prev, audio, lastUpdatedAt: Date.now() }));
      syncClock(audio?.server_now);
    });

    socket.on("audio:announce", (payload) => {
      setState((prev) => ({
        ...prev,
        announcement: {
          ...payload,
          id: `${payload.at}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        },
        lastUpdatedAt: Date.now(),
      }));
      touch();
    });

    socket.on("rooms:updated", () => {
      setState((prev) => ({ ...prev, roomsVersion: prev.roomsVersion + 1 }));
    });

    return () => {
      socket.disconnect();
      if (socketRef.current === socket) socketRef.current = null;
    };
  }, [loading, officer?.id, isDisplay, token, syncClock]);

  const requestSnapshot = useCallback(() => {
    socketRef.current?.emit("request:snapshot");
  }, []);

  return (
    <LiveContext.Provider
      value={{ ...state, clockOffset, token, requestSnapshot, socket: socketRef.current }}
    >
      {children}
    </LiveContext.Provider>
  );
}

export function useLive() {
  const context = useContext(LiveContext);
  if (!context) throw new Error("useLive must be used inside LiveProvider");
  return context;
}

export function useClock(interval = 1000) {
  const { clockOffset } = useLive();
  const [now, setNow] = useState(() => Date.now() + clockOffset);

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now() + clockOffset), interval);
    return () => clearInterval(timer);
  }, [clockOffset, interval]);

  return now;
}
