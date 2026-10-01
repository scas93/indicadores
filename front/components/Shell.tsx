"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api.client";
import { MENU, type Item } from "./menu";

type Marca = { nombre: string; logo_url: string | null; mostrar_logos: boolean };

function Entrada({ item, abierto, onToggle, hijo }: { item: Item; abierto?: boolean; onToggle?: () => void; hijo?: boolean }) {
  const deshabilitado = !item.href;
  const aviso = deshabilitado ? "Próximamente" : undefined;
  const contenido = (
    <>
      {item.icon && <i className={`fa ${item.icon}`} />}
      {hijo && <i className="fa fa-angle-right" />}
      <span>{item.label}</span>
      {deshabilitado && !hijo && <span className="badge-pronto">pronto</span>}
    </>
  );
  const clases = [deshabilitado ? "proximamente" : "", item.hijos ? "menu-list" : "", abierto ? "nav-active" : ""].join(" ").trim();
  return (
    <li className={clases}>
      <a
        href={item.href ?? "#"}
        title={aviso}
        aria-disabled={deshabilitado || undefined}
        onClick={(e) => {
          if (item.hijos) { e.preventDefault(); onToggle?.(); } else if (deshabilitado) e.preventDefault();
        }}
      >
        {contenido}
      </a>
      {item.hijos && (
        <ul className="child-list">
          {item.hijos.map((h) => <Entrada key={h.label + h.fase} item={h} hijo />)}
        </ul>
      )}
    </li>
  );
}

export function Shell({ marca, usuario, children }: {
  marca: Marca; usuario: { nombre: string; tipo: string }; children: React.ReactNode;
}) {
  const router = useRouter();
  const [colapsado, setColapsado] = useState(false);
  const [movil, setMovil] = useState(false);
  const [userMenu, setUserMenu] = useState(false);
  const [abierto, setAbierto] = useState<string | null>(null);

  async function salir() {
    try { await api("/api/auth/logout", { method: "POST" }); } catch { /* sesión ya vencida */ }
    router.replace("/login");
    router.refresh();
  }

  return (
    <div className={`${colapsado ? "sidebar-collapsed" : ""} ${movil ? "sidebar-open" : ""}`}>
      <div className="logo"><a href="/"><i className="fa fa-line-chart" />Indicadores</a></div>
      <aside className="sidebar-left">
        <ul className="side-navigation">
          {MENU.map((m) => (
            <Entrada key={m.label} item={m} abierto={abierto === m.label}
              onToggle={() => setAbierto(abierto === m.label ? null : m.label)} />
          ))}
        </ul>
      </aside>

      <header className="header-section">
        <button className="toggle-btn" aria-label="Menú" onClick={() => {
          if (window.innerWidth < 992) setMovil(!movil); else setColapsado(!colapsado);
        }}><i className="fa fa-bars" /></button>
        <div className="header-municipio">
          {marca.logo_url && marca.mostrar_logos && <img src={marca.logo_url} alt="" />}
          <span>{marca.nombre}</span>
        </div>
        <ul className="right-notification">
          <li className={userMenu ? "open" : ""}>
            <button className="user-toggle" onClick={() => setUserMenu(!userMenu)} onBlur={() => setTimeout(() => setUserMenu(false), 150)}>
              <i className="fa fa-user" />{usuario.nombre} <span className="caret" />
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
