"use client";
import { useMemo, useState } from "react";
import { mensajeError } from "@/components/Campo";
import { toast } from "@/components/Toasts";
import { api } from "@/lib/api.client";
import { descargar, qs, useAnio, type Opciones } from "@/lib/estadisticas";
import { SelectorAnio } from "./Filtros";

type Tabla = {
  encabezados: string[]; filas: (string | number | null)[][]; nombre_archivo: string;
  titulo?: string; grupos?: [string, number][]; filas_por_indicador?: number; columnas_combinadas?: number; // Cuenta Pública
  previas?: string[][];                                                                                      // Transparencia
};
const CONFIG = {
  "cuenta-publica": { titulo: "Cuenta Pública", franja: "CUENTA PÚBLICA", excel: false },
  transparencia: { titulo: "Transparencia", franja: "TRANSPARENCIA", excel: true },
};
const celda = (v: string | number | null) => (v === null || v === "" ? "" : v);

/** Cuenta Pública y Transparencia: año + centro gestor + programa (selección única, solo lo asignado al
 *  usuario). "Buscar" muestra la misma tabla del export; "Exportar" descarga el .xlsx. */
export function Exportacion({ tipo, op }: { tipo: keyof typeof CONFIG; op: Opciones }) {
  const cfg = CONFIG[tipo];
  const [anio, setAnio] = useAnio(op);
  const [centro, setCentro] = useState("");
  const [programa, setPrograma] = useState("");
  const [tabla, setTabla] = useState<Tabla | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const programas = useMemo(() => (op?.programas ?? []).filter((p) => p.centro_gestor_id === centro), [op, centro]);
  const params = qs({ anio, centro_gestor_id: centro, programa_id: programa });
  const listo = !!centro && !!programa;

  async function buscar() {
    setOcupado(true);
    try { setTabla(await api<Tabla>(`/api/estadisticas/${tipo}?${params}`)); } catch (e) { toast.error(mensajeError(e)); } finally { setOcupado(false); }
  }
  async function exportar() {
    setOcupado(true);
    try { await descargar(`/api/estadisticas/exportar/${tipo}?${params}`, `${tipo}.xlsx`); } catch (e) { toast.error(mensajeError(e)); } finally { setOcupado(false); }
  }

  return (
    <>
      <h3 className="page-heading">{cfg.titulo}</h3>
      <div className="panel"><div className="panel-body">
        <div className="stat-filtros">
          <SelectorAnio op={op} anio={anio} onChange={(v) => { setAnio(v); setTabla(null); }} />
          <div className="form-group">
            <label className="control-label">Centro gestor</label>
            <select className="form-control" style={{ minWidth: 240 }} value={centro} onChange={(e) => { setCentro(e.target.value); setPrograma(""); setTabla(null); }}>
              <option value="">Selecciona…</option>
              {(op?.centros_gestores ?? []).map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label className="control-label">Programas</label>
            <select className="form-control" style={{ minWidth: 280 }} value={programa} disabled={!centro} onChange={(e) => { setPrograma(e.target.value); setTabla(null); }}>
              <option value="">Selecciona…</option>
              {programas.map((p) => <option key={p.id} value={p.id}>{p.clave} — {p.nombre}</option>)}
            </select>
          </div>
          <button className="btn btn-success" disabled={!listo || ocupado} onClick={buscar}><i className="fa fa-search" /> Buscar</button>
          <button className="btn btn-excel" disabled={!listo || ocupado} onClick={exportar}>{cfg.excel && <i className="fa fa-file-excel-o" />} Exportar</button>
        </div>

        {tabla && (
          <>
            <div className="stat-franja">{cfg.franja}</div>
            <div className="stat-tabla-ancha">
              <table className="table table-bordered">
                <thead>
                  {tabla.titulo && <tr><th colSpan={tabla.encabezados.length} style={{ whiteSpace: "pre-line", textAlign: "left", paddingLeft: 16 }}>{tabla.titulo}</th></tr>}
                  {tabla.grupos && <tr>{tabla.grupos.map(([t, n], i) => <th key={i} colSpan={n}>{t}</th>)}</tr>}
                  {tabla.previas?.map((fila, i) => <tr key={i}>{fila.map((t, k) => <th key={k}>{t}</th>)}<th colSpan={tabla.encabezados.length - fila.length} /></tr>)}
                  <tr>{tabla.encabezados.map((h, i) => <th key={i}>{h}</th>)}</tr>
                </thead>
                <tbody>
                  {!tabla.filas.length && <tr><td colSpan={tabla.encabezados.length} className="text-center text-muted">Sin indicadores con datos en {anio}</td></tr>}
                  {tabla.filas.map((fila, i) => {
                    const por = tabla.filas_por_indicador ?? 1, comb = tabla.columnas_combinadas ?? 0;
                    const segunda = por > 1 && i % por !== 0;
                    return (
                      <tr key={i}>
                        {fila.map((v, k) => (segunda && k < comb ? null : <td key={k} rowSpan={!segunda && k < comb ? por : 1}>{celda(v)}</td>))}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div></div>
    </>
  );
}
