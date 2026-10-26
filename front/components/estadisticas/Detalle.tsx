"use client";
import { COLOR_ETIQUETA, COLOR_HEX, fmtPct, type ColorConteo, type DetalleIndicador } from "@/lib/estadisticas";

/** Tabla de drill-down bajo la gráfica: Programa | Indicador | Cumplimiento (2 decimales y "%"). */
export function Detalle({ titulo, color, filas }: { titulo: string; color: ColorConteo | null; filas: DetalleIndicador[] | null }) {
  return (
    <div>
      <div className="stat-detalle-titulo">
        <span>{titulo}</span>
        {color && <span title={COLOR_ETIQUETA[color]} style={{ display: "inline-block", width: 28, height: 16, background: COLOR_HEX[color] }} />}
      </div>
      <div className="table-responsive">
        <table className="table table-hover table-bordered">
          <thead><tr><th>Programa</th><th>Indicador</th><th style={{ width: 140 }}>Cumplimiento</th></tr></thead>
          <tbody>
            {filas === null && <tr><td colSpan={3} className="text-center text-muted">Cargando…</td></tr>}
            {filas && !filas.length && <tr><td colSpan={3} className="text-center text-muted">Sin indicadores</td></tr>}
            {filas?.map((f) => (
              <tr key={f.indicador_id}><td>{f.programa}</td><td>{f.nombre}</td><td className="text-right">{fmtPct(f.cumplimiento)}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
