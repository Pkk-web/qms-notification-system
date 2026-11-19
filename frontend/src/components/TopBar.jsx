import { IconBuilding, IconLogout, IconWifiOff } from "./Icons";

function initials(name) {
  return (name || "?")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

export function ConnectionState({ connected }) {
  return (
    <span className={`connection ${connected ? "is-live" : "is-offline"}`} role="status">
      {connected ? (
        <>
          <span className="live-dot" aria-hidden="true" /> Live
        </>
      ) : (
        <>
          <IconWifiOff size={15} /> Offline
        </>
      )}
    </span>
  );
}

export function TopBar({ officer, connected, onLogout, subtitle, children }) {
  return (
    <header className="topbar">
      <div className="topbar-inner">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">
            <IconBuilding size={22} />
          </div>
          <div>
            <div className="brand-name">Smart Lecture Rooms</div>
            <div className="brand-sub">{subtitle}</div>
          </div>
        </div>

        <div className="topbar-actions">
          <ConnectionState connected={connected} />
          {children}
          <div className="topbar-divider" aria-hidden="true" />
          <div className="user-menu">
            <div className="avatar" aria-hidden="true">
              {initials(officer.name)}
            </div>
            <div className="user-meta">
              <strong>{officer.name}</strong>
              <span>{officer.role === "ADMIN" ? "Administrator" : "Security officer"}</span>
            </div>
            <button type="button" className="icon-btn" onClick={onLogout} aria-label="Sign out" title="Sign out">
              <IconLogout size={18} />
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
