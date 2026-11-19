import { useEffect } from "react";
import { AuthProvider, useAuth } from "./state/AuthContext";
import { LiveProvider } from "./state/LiveContext";
import { navigate, useHashRoute } from "./lib/useHashRoute";
import LoginPage from "./pages/LoginPage";
import ConsolePage from "./pages/ConsolePage";
import AdminPage from "./pages/AdminPage";
import DisplayPage from "./pages/DisplayPage";
import { IconBuilding } from "./components/Icons";

function Splash() {
  return (
    <div className="splash">
      <div className="brand-mark brand-mark-lg" aria-hidden="true">
        <IconBuilding size={26} />
      </div>
      <span>Smart Lecture Rooms</span>
      <span className="splash-spinner" aria-label="Loading" />
    </div>
  );
}

function RouteView() {
  const route = useHashRoute();
  const { officer, loading } = useAuth();
  const isDisplay = route.path.startsWith("/display");

  useEffect(() => {
    if (loading || isDisplay) return;
    if (!officer && route.path !== "/login") {
      navigate("/login");
      return;
    }
    if (officer && (route.path === "/login" || route.path === "/" || route.path === "")) {
      navigate("/console");
      return;
    }
    if (officer && route.path === "/admin" && officer.role !== "ADMIN") {
      navigate("/console");
    }
  }, [route.path, officer, loading, isDisplay]);

  useEffect(() => {
    if (isDisplay) {
      document.title = "Smart Lecture Rooms · Display";
    } else if (route.path === "/admin") {
      document.title = "Administration · Smart Lecture Rooms";
    } else if (route.path === "/login") {
      document.title = "Sign in · Smart Lecture Rooms";
    } else {
      document.title = "Console · Smart Lecture Rooms";
    }
  }, [route.path, isDisplay]);

  if (isDisplay) return <DisplayPage />;
  if (loading) return <Splash />;
  if (!officer) return <LoginPage />;
  if (route.path === "/admin" && officer.role === "ADMIN") return <AdminPage />;
  return <ConsolePage />;
}

export default function App() {
  return (
    <AuthProvider>
      <LiveProvider>
        <RouteView />
      </LiveProvider>
    </AuthProvider>
  );
}
