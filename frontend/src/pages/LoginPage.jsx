import { useState } from "react";
import { useAuth } from "../state/AuthContext";
import { navigate } from "../lib/useHashRoute";
import { IconBuilding, IconDoor, IconShield, IconSpeaker } from "../components/Icons";

export default function LoginPage() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    if (submitting) return;
    setError("");
    setSubmitting(true);
    try {
      await login(username.trim(), password);
      navigate("/console");
    } catch (err) {
      setError(err?.message || "Could not sign in.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login-page">
      <section className="login-brand">
        <div className="login-brand-top">
          <div className="brand-mark brand-mark-lg" aria-hidden="true">
            <IconBuilding size={26} />
          </div>
          <span>Smart Lecture Rooms</span>
        </div>

        <div className="login-copy">
          <p className="eyebrow eyebrow-light">University Information Management System</p>
          <h1>Know which rooms are ready, at a glance.</h1>
          <p className="login-lede">
            Mark a lecturer&rsquo;s arrival once. The public display and the building speakers do the rest.
          </p>

          <ul className="login-points">
            <li>
              <span className="point-icon">
                <IconDoor size={20} />
              </span>
              <div>
                <strong>One-tick registration</strong>
                <span>Choose the room, add the lecturer&rsquo;s name, confirm.</span>
              </div>
            </li>
            <li>
              <span className="point-icon">
                <IconSpeaker size={20} />
              </span>
              <div>
                <strong>Timed announcements</strong>
                <span>Every five minutes during the arrival window, never overlapping.</span>
              </div>
            </li>
            <li>
              <span className="point-icon">
                <IconShield size={20} />
              </span>
              <div>
                <strong>Accountable by design</strong>
                <span>Every tick, end and audio change is written to the audit trail.</span>
              </div>
            </li>
          </ul>
        </div>

        <div className="login-brand-foot">
          <span>Pilot · Building A</span>
          <span>v3.0</span>
        </div>
      </section>

      <section className="login-panel">
        <form className="login-form" onSubmit={handleSubmit}>
          <div className="login-form-head">
            <h2>Security console</h2>
            <p>Sign in to register lecturer arrivals.</p>
          </div>

          {error && (
            <div className="form-error" role="alert">
              {error}
            </div>
          )}

          <label className="field">
            <span>Username</span>
            <input
              autoFocus
              autoComplete="username"
              name="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder="e.g. otieno"
              required
            />
          </label>

          <label className="field">
            <span>Password</span>
            <div className="password-field">
              <input
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                name="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Your password"
                required
              />
              <button
                type="button"
                className="password-toggle"
                onClick={() => setShowPassword((value) => !value)}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>
          </label>

          <button className="btn btn-primary btn-lg login-submit" type="submit" disabled={submitting}>
            {submitting ? "Signing in…" : "Sign in"}
          </button>

          <p className="login-hint">
            Accounts are individual. For shared desks, sign out before handing over. The console locks after 15
            minutes of inactivity.
          </p>

          {/*<div className="login-demo">
            <span>Pilot demo accounts</span>
            <code>otieno / Officer@123</code>
            <code>admin / Admin@123</code>
          </div>*/}
        </form>
      </section>
    </div>
  );
}
