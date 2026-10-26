"use client";
import { useEffect, useState } from "react";
import { mensajeError } from "@/components/Campo";
import { toast } from "@/components/Toasts";
import { useTipo } from "@/components/TipoContext";
import { api } from "@/lib/api.client";
import type { Programa } from "@/lib/mir";
import { useDescargas } from "@/components/shell/Descargas";
import { ArbolTab } from "./ArbolTab";
import { CapturaTab } from "./CapturaTab";
import { MatrizTab } from "./MatrizTab";

type Pestana = "arbol" | "matriz" | "captura";
const PESTANAS: { id: Pestana; nombre: string }[] = [
  { id: "arbol", nombre: "Árbol de problemas y objetivos" },
  { id: "matriz", nombre: "Matriz de indicadores" },
  { id: "captura", nombre: "Captura de avances" },
];

/** Módulo Inicio: selector de programa (solo los asignados al usuario) + 3 pestañas.
 *  La 4a pestaña (Presupuestación) llega en Fase 4. */
export function Inicio() {
  const tipo = useTipo();
  const [programas, setProgramas] = useState<Programa[] | null>(null);
  const [pid, setPid] = useState("");
  const [tab, setTab] = useState<Pestana>("arbol");
  const { setItems } = useDescargas();

  useEffect(() => {
    if (tipo === "padron") return;
    // /api/programas ya filtra por usuario_programa (administrador y alcalde ven todos)
    api<Programa[]>("/api/programas?activo=true").then((l) => {
      setProgramas(l);
      const reciente = Math.max(0, ...l.map((p) => p.ejercicio_fiscal));
      setPid((l.find((p) => p.ejercicio_fiscal === reciente) ?? l[0])?.id ?? "");
    }).catch((e) => { setProgramas([]); toast.error(mensajeError(e)); });
  }, [tipo]);

  // Las descargas viven en el ícono de nube del encabezado; dependen del programa elegido
  useEffect(() => {
    if (!pid) { setItems([]); return; }
    const g = (ruta: string) => `/api/programas/${pid}/${ruta}`;
    setItems([
      { label: "Árbol de problemas y objetivos", href: g("arbol/descarga?tipo=completo") },
      { label: "Árbol de problemas", href: g("arbol/descarga?tipo=problemas") },
      { label: "Árbol de objetivos", href: g("arbol/descarga?tipo=objetivos") },
      { label: "Matriz de Indicadores de Resultados", href: g("matriz/descarga?tipo=resultados") },
      { label: "Matriz de Cumplimiento de Indicadores", href: g("matriz/descarga?tipo=cumplimiento") },
    ]);
    return () => setItems([]);
  }, [pid, setItems]);

  if (tipo === "padron") return <p className="text-muted">Tu tipo de usuario no tiene acceso al módulo Inicio.</p>;
  // Solo el nombre; si dos programas se llaman igual (mismo programa en varios ejercicios) se desambigua
  // agregando ejercicio y clave solo a esos, para no dejar opciones indistinguibles.
  const repetidos = new Set((programas ?? []).map((p) => p.nombre).filter((n, i, a) => a.indexOf(n) !== i));
  const etiqueta = (p: Programa) => (repetidos.has(p.nombre) ? `${p.nombre} (${p.ejercicio_fiscal} · ${p.clave})` : p.nombre);

  return (
    <>
      <div className="inicio-selector">
        <select className="form-control" aria-label="Programa" value={pid} onChange={(e) => setPid(e.target.value)}>
          {programas === null && <option>Cargando…</option>}
          {programas?.length === 0 && <option value="">Sin programas asignados</option>}
          {(programas ?? []).map((p) => <option key={p.id} value={p.id}>{etiqueta(p)}</option>)}
        </select>
      </div>
      {pid && (
        <div className="inicio-panel">
          <ul className="nav nav-tabs inicio-tabs">
            {PESTANAS.map((p) => (
              <li key={p.id} className={tab === p.id ? "active" : ""}>
                <a href="#" onClick={(e) => { e.preventDefault(); setTab(p.id); }}>{p.nombre}</a>
              </li>
            ))}
          </ul>
          <div className="inicio-panel-cuerpo">
            {tab === "arbol" && <ArbolTab key={pid} programaId={pid} />}
            {tab === "matriz" && <MatrizTab key={pid} programaId={pid} />}
            {tab === "captura" && <CapturaTab key={pid} programaId={pid} />}
          </div>
        </div>
      )}
    </>
  );
}
