"use client";
import { useEffect, useState } from "react";

type Tipo = "success" | "error" | "info" | "warning";
type Toast = { id: number; tipo: Tipo; msg: string };
let seq = 0;
const listeners = new Set<(t: Toast) => void>();

/** API mínima equivalente a toastr: toast.success("..."), toast.error("...") */
export const toast = {
  show: (tipo: Tipo, msg: string) => listeners.forEach((l) => l({ id: ++seq, tipo, msg })),
  success: (m: string) => toast.show("success", m),
  error: (m: string) => toast.show("error", m),
  info: (m: string) => toast.show("info", m),
  warning: (m: string) => toast.show("warning", m),
};

export function Toasts() {
  const [items, setItems] = useState<Toast[]>([]);
  useEffect(() => {
    const l = (t: Toast) => {
      setItems((x) => [...x, t]);
      setTimeout(() => setItems((x) => x.filter((i) => i.id !== t.id)), 5000);
    };
    listeners.add(l);
    return () => void listeners.delete(l);
  }, []);
  return (
    <div className="toast-container" aria-live="polite">
      {items.map((t) => (
        <div key={t.id} className={`toast-item toast-${t.tipo}`}>{t.msg}</div>
      ))}
    </div>
  );
}
