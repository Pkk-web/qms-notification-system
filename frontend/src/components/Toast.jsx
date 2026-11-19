import { useCallback, useEffect, useRef, useState } from "react";
import { IconCheckCircle, IconAlert, IconX } from "./Icons";

export function useToast() {
  const [toast, setToast] = useState(null);
  const timer = useRef(null);

  const show = useCallback((message, tone = "info", duration = 4500) => {
    setToast({ message, tone, id: Date.now() });
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setToast(null), duration);
  }, []);

  const clear = useCallback(() => {
    window.clearTimeout(timer.current);
    setToast(null);
  }, []);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  return { toast, show, clear };
}

const TONE_ICON = {
  success: IconCheckCircle,
  error: IconAlert,
  info: IconCheckCircle,
};

export function Toast({ toast, onClose }) {
  if (!toast) return null;
  const Icon = TONE_ICON[toast.tone] || IconCheckCircle;
  return (
    <div className={`toast toast-${toast.tone}`} role="status" aria-live="polite">
      <span className="toast-icon">
        <Icon size={18} />
      </span>
      <span className="toast-message">{toast.message}</span>
      <button type="button" className="icon-btn toast-close" onClick={onClose} aria-label="Dismiss message">
        <IconX size={15} />
      </button>
    </div>
  );
}
