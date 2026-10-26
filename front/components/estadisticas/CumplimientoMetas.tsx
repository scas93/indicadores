"use client";
import { useState } from "react";
import { mensajeError } from "@/components/Campo";
import { toast } from "@/components/Toasts";
import { api } from "@/lib/api.client";
import { COLORES, pct, qs, useAnio, type Opciones, useSesion, type ColorConteo, type DetalleIndicador, type Grupo, type TipoCumplimiento } from "@/lib/estadisticas";
import { Detalle } from "./Detalle";
import { SelectorAnio, SelectorTipo } from "./Filtros";
import { BarraPorcentaje } from "./graficas";

/** Cumplimiento de Metas: una dependencia a la vez; 4 gráficas (una por color) con el % de sus metas. */
export function CumplimientoMetas({ op }: { op: Opciones }) {
  const [anio, setAnio] = useAnio(op);
  const [tipo, setTipo] = useSesion<TipoCumplimiento>("tipo:cumplimiento-metas", "obtenido");
  const [centro, setCentro] = useState("");
  const [g, setG] = useState<Grupo | null>(null);
  const [usado, setUsado] = useState({ anio: "", tipo: "obtenido" as TipoCumplimiento });
  const [detalle, setDetalle] = useState<{ titulo: string; color: ColorConteo | null; filas: DetalleIndicador[] | null } | null>(null);

  async function generar() {
    if (!centro) { toast.error("Elige una dependencia"); return; }
    setDetalle(null);
    try {
      const r = await api<{ grupos: Grupo[] }>(`/api/estadisticas/cumplimiento-metas?${qs({ anio, tipo_cumplimiento: tipo, centro_gestor_id: centro })}`);
      setG(r.grupos[0] ?? null); setUsado({ anio, tipo });
    } catch (e) { toast.error(mensajeError(e)); }
  }

  async function abrir(color: ColorConteo) {
    if (!g) return;
    setDetalle({ titulo: g.nombre, color, filas: null });
    try {
      const r = await api<{ indicadores: DetalleIndicador[] }>(`/api/estadisticas/indicadores?${qs({ anio: usado.anio, tipo_cumplimiento: usado.tipo, color, centro_gestor_ids: [centro] })}`);
      setDetalle({ titulo: g.nombre, color, filas: r.indicadores });
    } catch (e) { toast.error(mensajeError(e)); setDetalle(null); }
  }

  return (
    <>
      <h3 className="page-heading">Cumplimiento de Metas</h3>
      <div className="panel"><div className="panel-body">
        <div className="stat-filtros">
          <div className="form-group">
            <label className="control-label">Dependencia</label>
            <select className="form-control" style={{ minWidth: 260 }} value={centro} onChange={(e) => setCentro(e.target.value)}>
              <option value="">Selecciona…</option>
              {(op?.centros_gestores ?? []).map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
            </select>
          </div>
          <SelectorAnio op={op} anio={anio} onChange={setAnio} />
          <SelectorTipo tipo={tipo} onChange={setTipo} />
          <button className="btn btn-success" onClick={generar}><i className="fa fa-bar-chart" /> Generar grafica</button>
        </div>
        {g && (
          <div style={{ textAlign: "center" }}>
            <h4>{g.nombre} — {g.total} {g.total === 1 ? "meta" : "metas"}</h4>
            {COLORES.map((c) => <BarraPorcentaje key={c} color={c} valor={pct(g[c], g.total)} cantidad={g[c]} total={g.total} onClick={() => abrir(c)} />)}
          </div>
        )}
        {detalle && <Detalle {...detalle} />}
      </div></div>
    </>
  );
}
