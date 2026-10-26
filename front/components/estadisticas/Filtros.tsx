"use client";
import { TIPOS_CUMPLIMIENTO, type Opciones, type TipoCumplimiento } from "@/lib/estadisticas";

export function SelectorAnio({ op, anio, onChange }: { op: Opciones; anio: string; onChange: (v: string) => void }) {
  const anios = op.anios.length ? op.anios : [new Date().getFullYear()];
  return (
    <div className="form-group">
      <label className="control-label">Año</label>
      <select className="form-control" value={anio} onChange={(e) => onChange(e.target.value)}>
        {!anios.includes(Number(anio)) && <option value={anio}>{anio}</option>}
        {anios.map((a) => <option key={a} value={a}>{a}</option>)}
      </select>
    </div>
  );
}

export function SelectorTipo({ tipo, onChange }: { tipo: TipoCumplimiento; onChange: (v: TipoCumplimiento) => void }) {
  return (
    <div className="form-group">
      <label className="control-label">Tipo cumplimiento</label>
      <select className="form-control" value={tipo} onChange={(e) => onChange(e.target.value as TipoCumplimiento)}>
        {TIPOS_CUMPLIMIENTO.map((t) => <option key={t.valor} value={t.valor}>{t.nombre}</option>)}
      </select>
      <p className="stat-nota">* C.O = Cumplimiento obtenido<br />* C.E = Cumplimiento esperado</p>
    </div>
  );
}
