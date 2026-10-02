"use client";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { ApiError, api } from "@/lib/api.client";
import { Campo } from "../Campo";
import { Modal } from "../Modal";
import { toast } from "../Toasts";
import type { Item, Menu } from "./menu";

export type ShellProps = {
  menu: Menu;
  /** Texto de la etiqueta derecha del header: "3.- PRESUPUESTACION", "SUPER ADMIN"… */
  etiquetaUsuario: string;
  /** Endpoint de logout de ámbito (/api/auth/logout | /api/admin/auth/logout). */
  logoutUrl: string;
  /** Notificaciones (nube + badge verde). El badge se oculta en 0. */
  notificaciones?: number;
  /** Logo/nombre del municipio junto a los iconos del header (solo contenido, no estilo). */
  marca?: { nombre: string; logo_url: string | null; mostrar_logos: boolean };
  /** Muestra "Cambiar contraseña" en el menú de usuario (voluntario, nunca obligatorio). */
  cambiarPassword?: boolean;
  children: React.ReactNode;
};

function Fila({ item, abierto, onToggle, activo, hijo }: {
  item: Item; abierto?: boolean; onToggle?: () => void; activo?: boolean; hijo?: boolean;
}) {
  const deshabilitado = !item.href && !item.hijos;
  return (
    <li className={[item.hijos ? "menu-list" : "", abierto ? "nav-active" : "", activo ? "active" : "",
      deshabilitado ? "proximamente" : ""].join(" ").trim()}>
      <a
        href={item.href ?? "#"}
        title={deshabilitado ? "Próximamente" : item.label}
        aria-disabled={deshabilitado || undefined}
        onClick={(e) => {
          if (item.hijos) { e.preventDefault(); onToggle?.(); } else if (!item.href) e.preventDefault();
        }}
      >
        {item.icon && !hijo && <i className={`fa ${item.icon}`} />}
        <span>{item.label}</span>
      </a>
      {item.hijos && (
        <ul className="child-list">
          {item.hijos.map((h) => <Fila key={h.label} item={h} hijo />)}
        </ul>
      )}
    </li>
  );
}

/** Cascarón ÚNICO (menú lateral + header + contenido). Lo usan /sa y /mun sin variantes. */
function CambiarPassword({ onClose }: { onClose: () => void }) {
  const [f, setF] = useState({ password_actual: "", password_nueva: "", repetir: "" });
  const [errores, setErrores] = useState<Record<string, string>>({});

  async function guardar() {
    if (f.password_nueva !== f.repetir) return void setErrores({ repetir: "No coincide" });
    setErrores({});
    try {
      await api("/api/auth/cambiar-password", { method: "POST", json: { password_actual: f.password_actual, password_nueva: f.password_nueva } });
      toast.success("Contraseña actualizada");
      onClose();
    } catch (e) {
      if (e instanceof ApiError) { setErrores(e.campos); toast.error(e.message); } else toast.error("Error de conexión");
    }
  }
  return (
    <Modal titulo="Cambiar contraseña" onClose={onClose} footer={<>
      <button className="btn btn-default" onClick={onClose}>Cancelar</button>
      <button className="btn btn-success" onClick={guardar}>Guardar</button></>}>
      <Campo label="Contraseña actual" error={errores.password_actual}>
        <input type="password" className="form-control" value={f.password_actual} autoFocus autoComplete="off"
          onChange={(e) => setF({ ...f, password_actual: e.target.value })} /></Campo>
      <Campo label="Contraseña nueva" error={errores.password_nueva}>
        <input type="password" className="form-control" value={f.password_nueva} autoComplete="off"
          onChange={(e) => setF({ ...f, password_nueva: e.target.value })} /></Campo>
      <Campo label="Repetir contraseña nueva" error={errores.repetir}>
        <input type="password" className="form-control" value={f.repetir} autoComplete="off"
          onChange={(e) => setF({ ...f, repetir: e.target.value })} /></Campo>
    </Modal>
  );
}

export function AppShell({ menu, etiquetaUsuario, logoutUrl, notificaciones = 0, marca, cambiarPassword, children }: ShellProps) {
  const router = useRouter();
  const path = usePathname().replace(/^\/(sa|mun)/, "") || "/";
  const [colapsado, setColapsado] = useState(false);
  const [movil, setMovil] = useState(false);
  const [userMenu, setUserMenu] = useState(false);
  const [modalPassword, setModalPassword] = useState(false);
  // Acordeón como el sistema de referencia: un solo submenú abierto a la vez
  const [abierto, setAbierto] = useState<string | null>(null);

  useEffect(() => { // el menú de /sa y /mun no comparte body: marca la clase una vez montado
    document.body.classList.add("app-body");
    return () => document.body.classList.remove("app-body");
  }, []);

  async function salir() {
    try { await api(logoutUrl, { method: "POST" }); } catch { /* sesión ya vencida */ }
    router.replace("/login");
    router.refresh();
  }

  return (
    <div className={`${colapsado ? "sidebar-collapsed" : ""} ${movil ? "sidebar-open" : ""}`}>
      <div className="logo" />
      <aside className="sidebar-left">
        <ul className="side-navigation">
          <li className="navigation-title">Navegacion</li>
          {menu.map((m) => (
            <Fila key={m.label} item={m} activo={!!m.href && m.href === path}
              abierto={abierto === m.label} onToggle={() => setAbierto(abierto === m.label ? null : m.label)} />
          ))}
        </ul>
      </aside>

      <header className="header-section">
        <button className="toggle-btn" aria-label="Menú" onClick={() => {
          if (window.innerWidth < 992) setMovil(!movil); else { setColapsado(!colapsado); setAbierto(null); }
        }}><i className="fa fa-outdent" /></button>
        <div className="header-notif" title="Notificaciones">
          <i className="fa fa-cloud-download" />
          {notificaciones > 0 && <span className="badge-notif">{notificaciones}</span>}
        </div>
        {marca && (
          <div className="header-municipio">
            {marca.logo_url && marca.mostrar_logos && <img src={marca.logo_url} alt="" />}
            <span>{marca.nombre}</span>
          </div>
        )}
        <ul className="right-notification">
          <li className={userMenu ? "open" : ""}>
            <button className="user-toggle" onClick={() => setUserMenu(!userMenu)}
              onBlur={() => setTimeout(() => setUserMenu(false), 150)}>
              {etiquetaUsuario} <span className="caret" />
            </button>
            <ul className="dropdown-menu" style={{ display: userMenu ? "block" : "none" }}>
              {cambiarPassword && <li><a href="#" onMouseDown={(e) => e.preventDefault()}
                onClick={(e) => { e.preventDefault(); setUserMenu(false); setModalPassword(true); }}><i className="fa fa-key" /> Cambiar contraseña</a></li>}
              <li><a href="#" onClick={(e) => { e.preventDefault(); salir(); }}><i className="fa fa-sign-out" /> Cerrar sesión</a></li>
            </ul>
          </li>
        </ul>
      </header>

      <div className="body-content"><div className="wrapper">{children}</div></div>
      {modalPassword && <CambiarPassword onClose={() => setModalPassword(false)} />}
    </div>
  );
}
