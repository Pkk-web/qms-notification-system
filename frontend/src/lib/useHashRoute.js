import { useEffect, useState } from "react";

function readRoute() {
  const raw = window.location.hash.replace(/^#/, "") || "/";
  const [path, search = ""] = raw.split("?");
  return {
    path: path || "/",
    query: new URLSearchParams(search),
  };
}

export function navigate(to) {
  if (window.location.hash === `#${to}`) return;
  window.location.hash = to;
}

export function useHashRoute() {
  const [route, setRoute] = useState(readRoute);

  useEffect(() => {
    const onChange = () => setRoute(readRoute());
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);

  return route;
}
