"use client";
import { useEffect } from "react";

/** Modal con el marcado de Bootstrap 3 (modal > modal-dialog > modal-content). */
export function Modal({ titulo, onClose, children, footer, size }: {
  titulo: string; onClose: () => void; children: React.ReactNode; footer?: React.ReactNode; size?: "lg" | "sm";
}) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", k);
    document.body.classList.add("modal-open");
    return () => {
      document.removeEventListener("keydown", k);
      document.body.classList.remove("modal-open");
    };
  }, [onClose]);
  return (
    <>
      <div className="modal-backdrop-static" />
      <div className="modal show-modal in" role="dialog" aria-modal="true" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
        <div className={`modal-dialog${size ? ` modal-${size}` : ""}`}>
          <div className="modal-content">
            <div className="modal-header">
              <button type="button" className="close" aria-label="Cerrar" onClick={onClose}><span aria-hidden>&times;</span></button>
              <h4 className="modal-title">{titulo}</h4>
            </div>
            <div className="modal-body">{children}</div>
            {footer && <div className="modal-footer">{footer}</div>}
          </div>
        </div>
      </div>
    </>
  );
}
