"use client";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { api } from "@/lib/api.client";
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
export function AppShell({ menu, etiquetaUsuario, logoutUrl, notificaciones = 0, marca, children }: ShellProps) {
  const router = useRouter();
  const path = usePathname().replace(/^\/(sa|mun)/, "") || "/";
  const [colapsado, setColapsado] = useState(false);
  const [movil, setMovil] = useState(false);
  const [userMenu, setUserMenu] = useState(false);
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
              <li><a href="#" onClick={(e) => { e.preventDefault(); salir(); }}><i className="fa fa-sign-out" /> Cerrar sesión</a></li>
            </ul>
          </li>
        </ul>
      </header>

      <div className="body-content"><div className="wrapper">{children}</div></div>
    </div>
  );
}
