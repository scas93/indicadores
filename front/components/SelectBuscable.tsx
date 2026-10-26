"use client";
import { useEffect, useId, useMemo, useRef, useState } from "react";

export type OpcionSelect = { valor: string; etiqueta: string };
export type GrupoSelect = { etiqueta: string; opciones: OpcionSelect[] };

/** Sin acentos ni mayúsculas, para buscar "gestion" y encontrar "GESTIÓN". */
export const normalizar = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

/** Selector con buscador y opciones agrupadas (encabezado en negritas, no seleccionable, y las opciones con
 *  sangría debajo). Es el estilo de los selectores del sistema de referencia; sin librería de componentes.
 *  - La primera opción (`placeholder`, valor "") equivale a "ninguno" y se oculta mientras se busca.
 *  - Teclado: ↑ ↓ Inicio Fin mueven la opción resaltada, Enter la elige, Esc cierra, Tab cierra.
 *  - Los grupos que se quedan sin opciones al filtrar se ocultan. */
export function SelectBuscable({ grupos, valor, onChange, placeholder, ariaLabel }: {
  grupos: GrupoSelect[]; valor: string; onChange: (valor: string) => void; placeholder: string; ariaLabel: string;
}) {
  const id = useId();
  const [abierto, setAbierto] = useState(false);
  const [q, setQ] = useState("");
  const [activo, setActivo] = useState("");           // valor de la opción resaltada ("" = placeholder)
  const raiz = useRef<HTMLDivElement>(null);
  const boton = useRef<HTMLButtonElement>(null);
  const buscador = useRef<HTMLInputElement>(null);
  const lista = useRef<HTMLUListElement>(null);

  const buscando = q.trim() !== "";
  const filtrados = useMemo(() => {
    const n = normalizar(q.trim());
    return grupos.map((g) => ({ ...g, opciones: n ? g.opciones.filter((o) => normalizar(o.etiqueta).includes(n)) : g.opciones }))
      .filter((g) => g.opciones.length > 0);
  }, [grupos, q]);
  // opciones que el teclado recorre, en el orden en que se ven
  const navegables = useMemo(() => [...(buscando ? [] : [""]), ...filtrados.flatMap((g) => g.opciones.map((o) => o.valor))],
    [buscando, filtrados]);
  const etiquetaDe = useMemo(() => new Map(grupos.flatMap((g) => g.opciones.map((o) => [o.valor, o.etiqueta] as const))), [grupos]);
  const idOpcion = (v: string) => `${id}-op-${v || "ninguno"}`;

  function abrir() { setQ(""); setActivo(valor); setAbierto(true); }
  function cerrar(devolverFoco = true) { setAbierto(false); if (devolverFoco) boton.current?.focus(); }
  function elegir(v: string) { onChange(v); cerrar(); }

  useEffect(() => { if (abierto) buscador.current?.focus(); }, [abierto]);
  useEffect(() => { // al filtrar, el cursor pasa a la primera opción visible
    if (abierto && buscando) setActivo(navegables[0] ?? "");
  }, [q]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { // mantiene a la vista la opción resaltada
    if (abierto) lista.current?.querySelector<HTMLElement>(`[id="${idOpcion(activo)}"]`)?.scrollIntoView({ block: "nearest" });
  }, [activo, abierto]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { // clic fuera cierra sin quitar el foco de donde el usuario hizo clic
    if (!abierto) return;
    const fuera = (e: MouseEvent) => { if (!raiz.current?.contains(e.target as Node)) cerrar(false); };
    document.addEventListener("mousedown", fuera);
    return () => document.removeEventListener("mousedown", fuera);
  }, [abierto]); // eslint-disable-line react-hooks/exhaustive-deps

  function mover(delta: number | "inicio" | "fin") {
    if (!navegables.length) return;
    const i = navegables.indexOf(activo);
    const j = delta === "inicio" ? 0 : delta === "fin" ? navegables.length - 1 : Math.min(navegables.length - 1, Math.max(0, (i < 0 ? 0 : i) + delta));
    setActivo(navegables[j]);
  }
  function teclas(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") { e.preventDefault(); mover(1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); mover(-1); }
    else if (e.key === "Home") { e.preventDefault(); mover("inicio"); }
    else if (e.key === "End") { e.preventDefault(); mover("fin"); }
    else if (e.key === "Enter") { e.preventDefault(); if (navegables.includes(activo)) elegir(activo); }
    else if (e.key === "Escape") { e.preventDefault(); cerrar(); }
    else if (e.key === "Tab") cerrar(false);
  }

  const opcion = (v: string, texto: string, extra = "") => (
    <li key={v || "ninguno"} id={idOpcion(v)} role="option" aria-selected={v === valor}
      className={`sb-op ${extra} ${v === activo ? "sb-activa" : ""}`}
      onMouseMove={() => v !== activo && setActivo(v)} onMouseDown={(e) => e.preventDefault()} onClick={() => elegir(v)}>{texto}</li>
  );
  const seleccionada = valor ? etiquetaDe.get(valor) : undefined;

  return (
    <div className={`sb ${abierto ? "sb-abierto" : ""}`} ref={raiz}>
      <button type="button" ref={boton} className="form-control sb-boton" aria-haspopup="listbox" aria-expanded={abierto} aria-label={ariaLabel}
        onClick={() => (abierto ? cerrar() : abrir())}
        onKeyDown={(e) => { if (!abierto && (e.key === "ArrowDown" || e.key === "ArrowUp")) { e.preventDefault(); abrir(); } }}>
        <span className={seleccionada ? "" : "sb-placeholder"}>{seleccionada ?? placeholder}</span>
        <span className="sb-flecha" aria-hidden="true" />
      </button>
      {abierto && (
        <div className="sb-panel">
          <div className="sb-buscar">
            <input ref={buscador} type="text" role="combobox" aria-expanded="true" aria-controls={`${id}-lista`} aria-label={`Buscar: ${ariaLabel}`}
              aria-activedescendant={navegables.includes(activo) ? idOpcion(activo) : undefined} autoComplete="off"
              value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={teclas} />
            <i className="fa fa-search" aria-hidden="true" />
          </div>
          <ul id={`${id}-lista`} ref={lista} role="listbox" aria-label={ariaLabel} className="sb-lista">
            {!buscando && opcion("", placeholder)}
            {filtrados.map((g, i) => (
              <li key={g.etiqueta} role="presentation">
                <div className="sb-grupo" id={`${id}-g${i}`}>{g.etiqueta}</div>
                <ul role="group" aria-labelledby={`${id}-g${i}`} className="sb-opciones">
                  {g.opciones.map((o) => opcion(o.valor, o.etiqueta, "sb-op-grupo"))}
                </ul>
              </li>
            ))}
            {!filtrados.length && <li role="presentation" className="sb-vacio">Sin resultados</li>}
          </ul>
        </div>
      )}
    </div>
  );
}
