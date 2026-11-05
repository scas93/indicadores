"use client";
import { useEffect, useState } from "react";
import { mensajeError } from "../Campo";
import { toast } from "../Toasts";
import { useTipo } from "../TipoContext";
import { api } from "@/lib/api.client";
import { puede } from "@/lib/permisos";
import { consulta, FiltrosPadronUI, useFiltrosPadron, useHoy } from "./Filtros";
import { Barras, Circular, Grafica, PALETA, Pastel, type Dato } from "./graficas";

type Resultado = {
  total: number; por_localidad: Dato[]; por_grupo_edad: Dato[]; por_nivel: Dato[]; por_apoyo: Dato[];
  genero: { femenino: number; masculino: number; total: number; pct_femenino: number; pct_masculino: number };
};

function TablaTotal({ titulo, columna, datos }: { titulo: string; columna: string; datos: Dato[] }) {
  return (
    <div className="table-responsive">
      <table className="table table-bordered table-hover">
        <thead><tr><th>{titulo}</th><th style={{ width: 90 }}>Total</th></tr></thead>
        <tbody>
          {!datos.length && <tr><td colSpan={2} className="text-center text-muted">Sin datos</td></tr>}
          {datos.map((d) => <tr key={d.nombre}><td>{d.nombre}</td><td className="text-right">{d.total}</td></tr>)}
        </tbody>
      </table>
      <span className="sr-only">{columna}</span>
    </div>
  );
}

/** Estadísticas → Padrón Beneficiario: cinco gráficas sobre las capturas de apoyo del periodo y los filtros elegidos. */
export function PadronDashboard() {
  const tipo = useTipo();
  const f = useFiltrosPadron();
  const hoy = useHoy();
  const [ini, setIni] = useState("");
  const [fin, setFin] = useState("");
  const [r, setR] = useState<Resultado | null>(null);
  const [cargando, setCargando] = useState(false);
  useEffect(() => { if (hoy) { setIni((v) => v || hoy); setFin((v) => v || hoy); } }, [hoy]);

  if (!puede.catalogosPadron(tipo)) return <p className="text-muted">Sin acceso a este módulo.</p>;

  async function generar() {
    setCargando(true);
    try { setR(await api<Resultado>(`/api/padron/estadisticas/dashboard?${consulta(f, { fecha_ini: ini, fecha_fin: fin })}`)); }
    catch (e) { toast.error(mensajeError(e)); } finally { setCargando(false); }
  }

  return (
    <>
      <h3 className="page-heading">Padrón Beneficiario</h3>
      <div className="panel"><div className="panel-body">
        <FiltrosPadronUI f={f} />
        <div className="pe-filtros">
          <div className="form-group"><label className="control-label">Fecha Inicial</label>
            <input type="date" className="form-control" value={ini} onChange={(e) => setIni(e.target.value)} /></div>
          <div className="form-group"><label className="control-label">Fecha Final</label>
            <input type="date" className="form-control" value={fin} onChange={(e) => setFin(e.target.value)} /></div>
          <div className="form-group" style={{ alignSelf: "end" }}>
            <button className="btn btn-success" disabled={cargando || !ini || !fin} onClick={generar}><i className="fa fa-bar-chart" /> Generar Graficas</button></div>
        </div>

        {r && (
          <div className="pe-bloque">
            <p className="text-muted">Total de apoyos otorgados: <strong>{r.total}</strong></p>
            <div className="pe-par">
              <Grafica titulo="Numero de Apoyos por Localidad" archivo="apoyos-por-localidad"><Barras datos={r.por_localidad} etiqueta="Apoyos por localidad" /></Grafica>
              <TablaTotal titulo="Localidad Top 5" columna="Total" datos={r.por_localidad} />
            </div>
            <Grafica titulo="Apoyos por Genero" archivo="apoyos-por-genero">
              <div className="pe-genero">
                <Circular porcentaje={r.genero.pct_femenino} etiqueta="Femenino" color={PALETA[3]} detalle={String(r.genero.femenino)} />
                <Circular porcentaje={r.genero.pct_masculino} etiqueta="Masculino" color={PALETA[0]} detalle={String(r.genero.masculino)} />
              </div>
            </Grafica>
            <div className="pe-par" style={{ gridTemplateColumns: "1fr 1fr" }}>
              <Grafica titulo="Apoyos Por Grupo de Edad" archivo="apoyos-por-grupo-de-edad"><Pastel datos={r.por_grupo_edad} etiqueta="Apoyos por grupo de edad" /></Grafica>
              <Grafica titulo="Apoyos por Nivel Socioeconómico" archivo="apoyos-por-nivel-socioeconomico"><Pastel datos={r.por_nivel} etiqueta="Apoyos por nivel socioeconómico" /></Grafica>
            </div>
            <div className="pe-par">
              <Grafica titulo="Apoyos Otorgados" archivo="apoyos-otorgados"><Barras datos={r.por_apoyo} etiqueta="Apoyos otorgados por tipo" /></Grafica>
              <TablaTotal titulo="Apoyos Otorgados" columna="Total" datos={r.por_apoyo} />
            </div>
          </div>)}
      </div></div>
    </>
  );
}
