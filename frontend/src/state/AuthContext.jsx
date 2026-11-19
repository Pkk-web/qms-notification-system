import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "../lib/api";
import { navigate } from "../lib/useHashRoute";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [officer, setOfficer] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const data = await api("/api/auth/me");
      setOfficer(data.officer);
    } catch {
      setOfficer(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const onExpired = () => setOfficer(null);
    window.addEventListener("auth:expired", onExpired);
    return () => window.removeEventListener("auth:expired", onExpired);
  }, [refresh]);

  const login = useCallback(async (username, password) => {
    const data = await api("/api/auth/login", {
      method: "POST",
      body: { username, password },
    });
    setOfficer(data.officer);
    return data.officer;
  }, []);

  const logout = useCallback(async () => {
    try {
      await api("/api/auth/logout", { method: "POST" });
    } catch {
      /* session may already be gone */
    }
    setOfficer(null);
    navigate("/login");
  }, []);

  return (
    <AuthContext.Provider value={{ officer, loading, login, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
