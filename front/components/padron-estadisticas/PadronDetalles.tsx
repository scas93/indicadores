"use client";
import { useEffect, useState } from "react";
import { Campo, mensajeError } from "../Campo";
import { toast } from "../Toasts";
import { useTipo } from "../TipoContext";
import { ApiError, api } from "@/lib/api.client";
import { descargar } from "@/lib/estadisticas";
import { puede } from "@/lib/permisos";
import { consulta, FiltrosPadronUI, useFiltrosPadron, useHoy } from "./Filtros";
import { SelectorAnios } from "./PadronComparativo";

type Detallado = { tipo: "detallado"; titulo: string; total: number; encabezados: string[]; filas: (string | number | null)[][] };
type Concentrado = {
  tipo: "concentrado"; anios: number[];
  beneficiario: { curp: string; nombre: string; edad_actual: number | null; genero: string | null; grupo_edad_actual: string | null; localidad: string | null; nivel_socioeconomico: string | null };
  beneficio: { programa: string; apoyo: string; anios: Record<string, number> }[]; documentos: unknown[];
};
const MSG_CURP = "Para Generar Tipo Concentrado debe tener un CURP valido";

/** Estadísticas → Detalles Padrón Beneficiario. Detallado (una fila por captura, usa fechas) o Concentrado (ficha de un
 *  beneficiario, usa años y exige su CURP). */
export function PadronDetalles() {
  const tipoUsuario = useTipo();
  const f = useFiltrosPadron();
  const hoy = useHoy();
  const actual = String(new Date().getFullYear());
  const [curp, setCurp] = useState("");
  const [nombre, setNombre] = useState("");
  const [ini, setIni] = useState("");
  const [fin, setFin] = useState("");
  const [aIni, setAIni] = useState(actual);
  const [aFin, setAFin] = useState(actual);
  const [tipo, setTipo] = useState<"detallado" | "concentrado">("detallado");
  const [r, setR] = useState<Detallado | Concentrado | null>(null);
  const [aviso, setAviso] = useState("");
  const [ocupado, setOcupado] = useState(false);
  useEffect(() => { if (hoy) { setIni((v) => v || hoy); setFin((v) => v || hoy); } }, [hoy]);

  if (!puede.catalogosPadron(tipoUsuario)) return <p className="text-muted">Sin acceso a este módulo.</p>;
  const concentrado = tipo === "concentrado";
  const q = () => consulta(f, { curp, nombre, tipo, ...(concentrado ? { anio_ini: aIni, anio_fin: aFin } : { fecha_ini: ini, fecha_fin: fin }) });
  const sinCurp = concentrado && !curp.trim();

  async function generar() {
    setAviso("");
    if (sinCurp) { setAviso(MSG_CURP); setR(null); return; }
    setOcupado(true);
    try { setR(await api<Detallado | Concentrado>(`/api/padron/estadisticas/detalles?${q()}`)); }
    catch (e) { setR(null); if (e instanceof ApiError && e.codigo === "CURP_INVALIDA") setAviso(e.message); else toast.error(mensajeError(e)); }
    finally { setOcupado(false); }
  }
  async function exportar() {
    if (sinCurp) { setAviso(MSG_CURP); return; }
    setOcupado(true);
    try { await descargar(`/api/padron/estadisticas/detalles/exportar?${q()}`, `${tipo}_padron_beneficiario.xlsx`); }
    catch (e) { toast.error(mensajeError(e)); } finally { setOcupado(false); }
  }

  return (
    <>
      <h3 className="page-heading">Detalles Padrón Beneficiario</h3>
      <div className="panel"><div className="panel-body">
        <FiltrosPadronUI f={f} />
        <div className="pe-filtros">
          <Campo label="CURP"><input className="form-control" value={curp} onChange={(e) => setCurp(e.target.value)} /></Campo>
          <Campo label="Nombre"><input className="form-control" value={nombre} onChange={(e) => setNombre(e.target.value)} /></Campo>
          <div className="form-group"><label className="control-label">Fecha Inicial</label>
            <input type="date" className="form-control" value={ini} disabled={concentrado} onChange={(e) => setIni(e.target.value)} /></div>
          <div className="form-group"><label className="control-label">Fecha Final</label>
            <input type="date" className="form-control" value={fin} disabled={concentrado} onChange={(e) => setFin(e.target.value)} /></div>
          <SelectorAnios ini={aIni} fin={aFin} onIni={setAIni} onFin={setAFin} deshabilitado={!concentrado} />
          <div className="form-group"><label className="control-label">Tipo</label>
            <select className="form-control" value={tipo} onChange={(e) => { setTipo(e.target.value as typeof tipo); setR(null); setAviso(""); }}>
              <option value="detallado">Detallado</option><option value="concentrado">Concentrado</option></select></div>
        </div>
        <div className="toolbar">
          <button className="btn btn-success" disabled={ocupado} onClick={generar}><i className="fa fa-search" /> Generar Reporte</button>
          <button className="btn btn-default" disabled={ocupado} onClick={exportar}><i className="fa fa-file-excel-o" /> Exportar</button>
        </div>
        {aviso && <p className="pe-aviso" role="alert">{aviso}</p>}

        {r?.tipo === "detallado" && (
          <div className="pe-bloque">
            <div className="pe-franja">{r.titulo}</div>
            <p>Total de Apoyos Otorgados: <strong>{r.total}</strong></p>
            <div className="stat-tabla-ancha">
              <table className="table table-bordered table-hover">
                <thead><tr>{r.encabezados.map((h) => <th key={h}>{h}</th>)}</tr></thead>
                <tbody>
                  {!r.filas.length && <tr><td colSpan={r.encabezados.length} className="text-center text-muted">Sin apoyos en el periodo</td></tr>}
                  {r.filas.map((fila, i) => <tr key={i}>{fila.map((v, k) => <td key={k}>{v ?? ""}</td>)}</tr>)}
                </tbody>
              </table>
            </div>
          </div>)}

        {r?.tipo === "concentrado" && (
          <div className="pe-bloque">
            <div className="pe-franja">{r.beneficiario.nombre}</div>
            <div className="pe-ficha">
              <dl>
                <dt>Edad Actual</dt><dd>{r.beneficiario.edad_actual ?? "—"}</dd>
                <dt>Genero</dt><dd>{r.beneficiario.genero ?? "—"}</dd>
                <dt>Grupo Edad Actual</dt><dd>{r.beneficiario.grupo_edad_actual ?? "—"}</dd>
                <dt>Localidad</dt><dd>{r.beneficiario.localidad ?? "—"}</dd>
                <dt>Nivel Socioeconomico (ultimo registro)</dt><dd>{r.beneficiario.nivel_socioeconomico ?? "—"}</dd>
              </dl>
              <div className="table-responsive">
                <table className="table table-bordered table-hover">
                  <thead><tr><th colSpan={2 + r.anios.length} className="text-center">BENEFICIO</th></tr>
                    <tr><th>Programa</th><th>Apoyo</th>{r.anios.map((a) => <th key={a}>{a}</th>)}</tr></thead>
                  <tbody>
                    {!r.beneficio.length && <tr><td colSpan={2 + r.anios.length} className="text-center text-muted">Sin apoyos en el rango</td></tr>}
                    {r.beneficio.map((b, i) => <tr key={i}><td>{b.programa}</td><td>{b.apoyo}</td>
                      {r.anios.map((a) => <td key={a} className="text-right">{b.anios[String(a)] ?? 0}</td>)}</tr>)}
                  </tbody>
                </table>
              </div>
            </div>
            <div className="pe-franja">Documentos del Beneficiario</div>
          </div>)}
      </div></div>
    </>
  );
}
