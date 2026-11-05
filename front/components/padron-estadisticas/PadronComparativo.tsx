"use client";
import { useState } from "react";
import { mensajeError } from "../Campo";
import { toast } from "../Toasts";
import { useTipo } from "../TipoContext";
import { api } from "@/lib/api.client";
import { puede } from "@/lib/permisos";
import { consulta, FiltrosPadronUI, useFiltrosPadron } from "./Filtros";
import { BarrasPorAnio, Grafica } from "./graficas";

type Resultado = { anios: number[]; localidades: { nombre: string; total: number; anios: Record<string, number> }[] };
export const ANIO_MIN = 2021;
export const aniosDisponibles = () => Array.from({ length: new Date().getFullYear() - ANIO_MIN + 1 }, (_, i) => ANIO_MIN + i);

export function SelectorAnios({ ini, fin, onIni, onFin, deshabilitado }: { ini: string; fin: string; onIni: (v: string) => void; onFin: (v: string) => void; deshabilitado?: boolean }) {
  return (
    <>
      <div className="form-group"><label className="control-label">Año Inicial</label>
        <select className="form-control" value={ini} disabled={deshabilitado} onChange={(e) => onIni(e.target.value)}>
          {aniosDisponibles().map((a) => <option key={a} value={a}>{a}</option>)}</select></div>
      <div className="form-group"><label className="control-label">Año Final</label>
        <select className="form-control" value={fin} disabled={deshabilitado} onChange={(e) => onFin(e.target.value)}>
          {aniosDisponibles().map((a) => <option key={a} value={a}>{a}</option>)}</select></div>
    </>
  );
}

/** Estadísticas → Comparativo Padrón Beneficiario: top 5 de localidades según el total del rango de años, y su conteo por año. */
export function PadronComparativo() {
  const tipo = useTipo();
  const f = useFiltrosPadron();
  const actual = String(new Date().getFullYear());
  const [ini, setIni] = useState(actual);
  const [fin, setFin] = useState(actual);
  const [r, setR] = useState<Resultado | null>(null);
  const [cargando, setCargando] = useState(false);
  if (!puede.catalogosPadron(tipo)) return <p className="text-muted">Sin acceso a este módulo.</p>;

  async function generar() {
    setCargando(true);
    try { setR(await api<Resultado>(`/api/padron/estadisticas/comparativo?${consulta(f, { anio_ini: ini, anio_fin: fin })}`)); }
    catch (e) { toast.error(mensajeError(e)); } finally { setCargando(false); }
  }

  return (
    <>
      <h3 className="page-heading">Comparativo Padrón Beneficiario</h3>
      <div className="panel"><div className="panel-body">
        <FiltrosPadronUI f={f} />
        <div className="pe-filtros">
          <SelectorAnios ini={ini} fin={fin} onIni={setIni} onFin={setFin} />
          <div className="form-group" style={{ alignSelf: "end" }}>
            <button className="btn btn-success" disabled={cargando} onClick={generar}><i className="fa fa-search" /> Generar Reporte</button></div>
        </div>
        {r && (
          <div className="pe-bloque">
            <div className="pe-franja">COMPARATIVO / APOYOS OTORGADOS POR LOCALIDAD TOP 5</div>
            <div className="table-responsive">
              <table className="table table-bordered table-hover">
                <thead><tr><th>Localidad</th><th>Total</th>{r.anios.map((a) => <th key={a}>{a}</th>)}</tr></thead>
                <tbody>
                  {!r.localidades.length && <tr><td colSpan={2 + r.anios.length} className="text-center text-muted">Sin datos en el rango</td></tr>}
                  {r.localidades.map((l) => <tr key={l.nombre}><td>{l.nombre}</td><td className="text-right">{l.total}</td>
                    {r.anios.map((a) => <td key={a} className="text-right">{l.anios[String(a)] ?? 0}</td>)}</tr>)}
                </tbody>
              </table>
            </div>
            <Grafica titulo="Comparativo — Top 5 Localidades" archivo="comparativo-top-5-localidades">
              <BarrasPorAnio grupos={r.localidades} anios={r.anios} />
            </Grafica>
          </div>)}
      </div></div>
    </>
  );
}
