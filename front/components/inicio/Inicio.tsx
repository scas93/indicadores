"use client";
import { useEffect, useState } from "react";
import { mensajeError } from "@/components/Campo";
import { toast } from "@/components/Toasts";
import { useTipo } from "@/components/TipoContext";
import { api } from "@/lib/api.client";
import type { Programa } from "@/lib/mir";
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
  const [descargas, setDescargas] = useState(false);

  useEffect(() => {
    if (tipo === "padron") return;
    // /api/programas ya filtra por usuario_programa (administrador y alcalde ven todos)
    api<Programa[]>("/api/programas?activo=true").then((l) => {
      setProgramas(l);
      const reciente = Math.max(0, ...l.map((p) => p.ejercicio_fiscal));
      setPid((l.find((p) => p.ejercicio_fiscal === reciente) ?? l[0])?.id ?? "");
    }).catch((e) => { setProgramas([]); toast.error(mensajeError(e)); });
  }, [tipo]);

  if (tipo === "padron") return <p className="text-muted">Tu tipo de usuario no tiene acceso al módulo Inicio.</p>;
  const g = (ruta: string) => `/api/programas/${pid}/${ruta}`;

  return (
    <>
      <h3 className="page-heading">Inicio</h3>
      <div className="inicio-selector">
        <label className="control-label" style={{ margin: 0 }}>Programa</label>
        <select className="form-control" style={{ maxWidth: 520 }} value={pid} onChange={(e) => setPid(e.target.value)}>
          {programas === null && <option>Cargando…</option>}
          {programas?.length === 0 && <option value="">Sin programas asignados</option>}
          {(programas ?? []).map((p) => <option key={p.id} value={p.id}>{p.ejercicio_fiscal} · {p.clave} — {p.nombre}</option>)}
        </select>
        <span className="spacer" style={{ flex: 1 }} />
        {pid && (
          <div className="descargas-menu">
            <button className="btn btn-default" title="Descargas" onClick={() => setDescargas((x) => !x)}>
              <i className="fa fa-cloud-download" /> Descargas
            </button>
            {descargas && (
              <ul onClick={() => setDescargas(false)}>
                <li><a href={g("arbol/descarga?tipo=completo")}><i className="fa fa-file-pdf-o" /> Árbol de problemas y objetivos</a></li>
                <li><a href={g("arbol/descarga?tipo=problemas")}><i className="fa fa-file-pdf-o" /> Árbol de problemas</a></li>
                <li><a href={g("arbol/descarga?tipo=objetivos")}><i className="fa fa-file-pdf-o" /> Árbol de objetivos</a></li>
                <li><a href={g("matriz/descarga?tipo=resultados")}><i className="fa fa-file-pdf-o" /> Matriz de Indicadores de Resultados</a></li>
                <li><a href={g("matriz/descarga?tipo=cumplimiento")}><i className="fa fa-file-pdf-o" /> Matriz de Cumplimiento de Indicadores</a></li>
              </ul>
            )}
          </div>
        )}
      </div>
      {pid && (
        <div className="panel">
          <div className="panel-heading">
            <ul className="nav nav-tabs">
              {PESTANAS.map((p) => (
                <li key={p.id} className={tab === p.id ? "active" : ""}>
                  <a href="#" onClick={(e) => { e.preventDefault(); setTab(p.id); }}>{p.nombre}</a>
                </li>
              ))}
            </ul>
          </div>
          <div className="panel-body">
            {tab === "arbol" && <ArbolTab key={pid} programaId={pid} />}
            {tab === "matriz" && <MatrizTab key={pid} programaId={pid} />}
            {tab === "captura" && <CapturaTab key={pid} programaId={pid} />}
          </div>
        </div>
      )}
    </>
  );
}
