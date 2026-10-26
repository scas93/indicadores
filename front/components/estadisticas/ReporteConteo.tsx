"use client";
import { useState } from "react";
import { mensajeError } from "@/components/Campo";
import { toast } from "@/components/Toasts";
import { api } from "@/lib/api.client";
import { qs, useAnio, type Opciones, useSesion, type ColorConteo, type DetalleIndicador, type Grupo, type TipoCumplimiento } from "@/lib/estadisticas";
import { Detalle } from "./Detalle";
import { SelectorAnio, SelectorTipo } from "./Filtros";
import { BarrasAgrupadas, BarrasApiladas } from "./graficas";

type Vista = "dependencias" | "ejes" | "consolidado";
const TITULO: Record<Vista, string> = { dependencias: "Dependencias", ejes: "Ejes", consolidado: "Consolidado" };

/** Dependencias, Ejes y Consolidado: mismos filtros y mismo clic-a-detalle; cambian el agrupador
 *  (centro gestor / eje) y la gráfica (conteos agrupados / % apilado). */
export function ReporteConteo({ vista, op }: { vista: Vista; op: Opciones }) {
  const porEje = vista === "ejes";
  const [anio, setAnio] = useAnio(op);
  const [tipo, setTipo] = useSesion<TipoCumplimiento>(`tipo:${vista}`, "obtenido");
  const [sel, setSel] = useState<string[]>([]);
  const [grupos, setGrupos] = useState<Grupo[] | null>(null);
  const [detalle, setDetalle] = useState<{ titulo: string; color: ColorConteo | null; filas: DetalleIndicador[] | null } | null>(null);
  const [cargando, setCargando] = useState(false);
  const [usado, setUsado] = useState({ anio: "", tipo: "obtenido" as TipoCumplimiento }); // filtros de la gráfica que se ve

  const lista = porEje ? op?.ejes : op?.centros_gestores;

  async function generar() {
    setCargando(true); setDetalle(null);
    try {
      const r = await api<{ grupos: Grupo[] }>(`/api/estadisticas/${vista}?${qs({ anio, tipo_cumplimiento: tipo, [porEje ? "eje_ids" : "centro_gestor_ids"]: sel })}`);
      setGrupos(r.grupos); setUsado({ anio, tipo });
    } catch (e) { toast.error(mensajeError(e)); } finally { setCargando(false); }
  }

  async function abrir(g: Grupo, color: ColorConteo | null) {
    setDetalle({ titulo: g.nombre, color, filas: null });
    try {
      const r = await api<{ indicadores: DetalleIndicador[] }>(`/api/estadisticas/indicadores?${qs({
        anio: usado.anio, tipo_cumplimiento: usado.tipo, color,
        ...(porEje ? { eje_id: g.id } : { centro_gestor_ids: g.id ? [g.id] : [] }),
      })}`);
      // "Sin eje" no tiene id para filtrar en la API: se filtra aquí por el eje vacío
      setDetalle({ titulo: g.nombre, color, filas: porEje && !g.id ? r.indicadores.filter((i) => i.eje === null) : r.indicadores });
    } catch (e) { toast.error(mensajeError(e)); setDetalle(null); }
  }

  return (
    <>
      <h3 className="page-heading">{TITULO[vista]}</h3>
      <div className="panel"><div className="panel-body">
        <div className="stat-filtros">
          <div className="form-group">
            <label className="control-label">{porEje ? "Ejes" : "Centro gestor"}</label>
            <select multiple size={6} className="form-control" style={{ minWidth: 260 }} value={sel}
              onChange={(e) => setSel(Array.from(e.target.selectedOptions, (o) => o.value))}>
              {(lista ?? []).map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
            </select>
            <p className="stat-nota">Ctrl/Cmd para elegir varios; vacío = todos los de tus programas</p>
          </div>
          <SelectorAnio op={op} anio={anio} onChange={setAnio} />
          <SelectorTipo tipo={tipo} onChange={setTipo} />
          <button className="btn btn-success" disabled={cargando} onClick={generar}><i className="fa fa-bar-chart" /> Generar grafica</button>
        </div>

        {grupos && !grupos.length && <p className="text-muted text-center">Sin datos: no tienes programas asignados.</p>}
        {grupos && grupos.length > 0 && (vista === "consolidado" ? <BarrasApiladas grupos={grupos} onClick={abrir} /> : <BarrasAgrupadas grupos={grupos} onClick={abrir} />)}
        {detalle && <Detalle {...detalle} />}
      </div></div>
    </>
  );
}
