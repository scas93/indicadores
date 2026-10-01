"use client";
import { useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { api } from "@/lib/api.client";

const ITEMS = [
  { href: "/", label: "Municipios", icon: "fa-building" },
  { href: "/plantillas", label: "Plantillas globales", icon: "fa-clone" },
];

export function AdminShell({ nombre, children }: { nombre: string; children: React.ReactNode }) {
  const router = useRouter();
  const path = usePathname().replace(/^\/sa/, "") || "/";
  const [colapsado, setColapsado] = useState(false);
  const [userMenu, setUserMenu] = useState(false);

  async function salir() {
    try { await api("/api/admin/auth/logout", { method: "POST" }); } catch { /* ya vencida */ }
    router.replace("/login");
    router.refresh();
  }

  return (
    <div className={colapsado ? "sidebar-collapsed" : ""}>
      <div className="logo"><a href="/"><i className="fa fa-line-chart" />Indicadores</a></div>
      <aside className="sidebar-left">
        <ul className="side-navigation">
          <li className="navigation-title">Plataforma</li>
          {ITEMS.map((i) => (
            <li key={i.href} className={path === i.href ? "nav-active" : ""}>
              <a href={i.href}><i className={`fa ${i.icon}`} />{i.label}</a>
            </li>
          ))}
        </ul>
      </aside>
      <header className="header-section">
        <button className="toggle-btn" aria-label="Menú" onClick={() => setColapsado(!colapsado)}><i className="fa fa-bars" /></button>
        <div className="header-municipio"><span>Super admin</span></div>
        <ul className="right-notification">
          <li className={userMenu ? "open" : ""}>
            <button className="user-toggle" onClick={() => setUserMenu(!userMenu)} onBlur={() => setTimeout(() => setUserMenu(false), 150)}>
              <i className="fa fa-user" />{nombre} <span className="caret" />
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
