"use client";
import { useState } from "react";
import { Campo, mensajeError } from "../Campo";
import { toast } from "../Toasts";
import { useTipo } from "../TipoContext";
import { api } from "@/lib/api.client";
import { descargar, qs } from "@/lib/estadisticas";
import { puede } from "@/lib/permisos";

type Resultado = { titulo: string; total: number; encabezados: string[]; filas: (string | null)[][] };
const FALTANTES = [{ v: "todos", t: "TODOS" }, { v: "ine", t: "INE/IFE" }, { v: "curp", t: "CURP" }, { v: "comprobante_domicilio", t: "COMPROBANTE DE DOMICILIO" }];

/** Estadísticas → Reporte Documentos: beneficiarios del municipio a los que les falta algún documento. */
export function PadronReporteDocumentos() {
  const tipoUsuario = useTipo();
  const [curp, setCurp] = useState("");
  const [nombre, setNombre] = useState("");
  const [faltante, setFaltante] = useState("todos");
  const [r, setR] = useState<Resultado | null>(null);
  const [ocupado, setOcupado] = useState(false);
  if (!puede.catalogosPadron(tipoUsuario)) return <p className="text-muted">Sin acceso a este módulo.</p>;
  const q = () => qs({ curp, nombre, faltante });

  async function generar() {
    setOcupado(true);
    try { setR(await api<Resultado>(`/api/padron/estadisticas/documentos?${q()}`)); }
    catch (e) { toast.error(mensajeError(e)); } finally { setOcupado(false); }
  }
  async function exportar() {
    setOcupado(true);
    try { await descargar(`/api/padron/estadisticas/documentos/exportar?${q()}`, "reporte_falta_documentos.xlsx"); }
    catch (e) { toast.error(mensajeError(e)); } finally { setOcupado(false); }
  }

  return (
    <>
      <h3 className="page-heading">Reporte Documentos</h3>
      <div className="panel"><div className="panel-body">
        <div className="pe-filtros">
          <Campo label="CURP"><input className="form-control" value={curp} onChange={(e) => setCurp(e.target.value)} /></Campo>
          <Campo label="Nombre"><input className="form-control" value={nombre} onChange={(e) => setNombre(e.target.value)} /></Campo>
          <Campo label="Documento Faltante">
            <select className="form-control" value={faltante} onChange={(e) => setFaltante(e.target.value)}>
              {FALTANTES.map((f) => <option key={f.v} value={f.v}>{f.t}</option>)}</select></Campo>
        </div>
        <div className="toolbar">
          <button className="btn btn-success" disabled={ocupado} onClick={generar}><i className="fa fa-search" /> Generar Reporte</button>
          <button className="btn btn-default" disabled={ocupado} onClick={exportar}><i className="fa fa-file-excel-o" /> Exportar</button>
        </div>
        {r && (
          <div className="pe-bloque">
            <div className="pe-franja">{r.titulo}</div>
            <p>Total de beneficiarios: <strong>{r.total}</strong></p>
            <div className="stat-tabla-ancha">
              <table className="table table-bordered table-hover">
                <thead><tr>{r.encabezados.map((h) => <th key={h}>{h}</th>)}</tr></thead>
                <tbody>
                  {!r.filas.length && <tr><td colSpan={r.encabezados.length} className="text-center text-muted">Ningún beneficiario con documentos faltantes</td></tr>}
                  {r.filas.map((fila, i) => <tr key={i}>{fila.map((v, k) => <td key={k}>{v ?? ""}</td>)}</tr>)}
                </tbody>
              </table>
            </div>
          </div>)}
      </div></div>
    </>
  );
}
