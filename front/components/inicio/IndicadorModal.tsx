"use client";
import { useEffect, useState } from "react";
import { Campo } from "@/components/Campo";
import { Modal } from "@/components/Modal";
import { toast } from "@/components/Toasts";
import { ApiError, api } from "@/lib/api.client";
import { ALGORITMOS, DIMENSIONES, NIVEL_NOMBRE, TIPOS_INDICADOR, num, str, type Elemento, type Indicador, type ProgramaInfo } from "@/lib/mir";

type Pestana = "mir" | "ficha" | "metas" | "params";
type Frecuencia = { id: string; clave: string; nombre: string; activo: boolean };
type MetaFila = { anio: string; a: string; b: string; fiscal: boolean };
const COLORES = [["verde", "Verde"], ["amarillo", "Amarillo"], ["rojo", "Rojo"]] as const;

function estadoInicial(e: Elemento, i: Indicador | null) {
  return {
    mir: { resumen_narrativo: e.resumen_narrativo, medios_verificacion: e.medios_verificacion, supuestos: e.supuestos, evidencia: e.evidencia ?? "" },
    ficha: {
      tipo: i?.ficha.tipo ?? "gestion", prioritario: i?.ficha.prioritario ?? false, nombre: i?.ficha.nombre ?? "",
      interpretacion: i?.ficha.interpretacion ?? "", dimension: i?.ficha.dimension ?? "", frecuencia_id: i?.ficha.frecuencia_id ?? "",
      unidad_medida: i?.ficha.unidad_medida ?? "", algoritmo: i?.ficha.algoritmo ?? "", unidad_a: i?.ficha.unidad_a ?? "", unidad_b: i?.ficha.unidad_b ?? "",
    },
    anio_base: str(i?.metas.anio_base), meta_administracion: str(i?.metas.meta_administracion),
    metas: (i?.metas.anuales ?? []).map((m): MetaFila => ({ anio: String(m.anio), a: str(m.valor_a_programado), b: str(m.valor_b_programado), fiscal: m.es_ejercicio_fiscal })),
    rangos: Object.fromEntries(COLORES.map(([c]) => [c, { desde: str(i?.rangos[c].desde), hasta: str(i?.rangos[c].hasta) }])) as Record<string, { desde: string; hasta: string }>,
  };
}

/** Modal de alta/edición de indicador: 4 pestañas (M.I.R., Ficha técnica, Determinación de metas,
 *  Parametrización). Metas y parámetros quedan deshabilitadas hasta elegir algoritmo y frecuencia. */
export function IndicadorModal({ programa, elemento, indicador, onClose, onGuardado }: {
  programa: ProgramaInfo; elemento: Elemento; indicador: Indicador | null; onClose: () => void; onGuardado: () => void;
}) {
  const [tab, setTab] = useState<Pestana>("ficha");
  const [f, setF] = useState(() => estadoInicial(elemento, indicador));
  const [frecuencias, setFrecuencias] = useState<Frecuencia[]>([]);
  const [errores, setErrores] = useState<Record<string, string>>({});
  const [ocupado, setOcupado] = useState(false);
  useEffect(() => { api<Frecuencia[]>("/api/frecuencias").then(setFrecuencias).catch(() => setFrecuencias([])); }, []);

  const usaB = f.ficha.algoritmo !== "a";
  const habilitado = !!f.ficha.algoritmo && !!f.ficha.frecuencia_id;
  const setFicha = (k: keyof typeof f.ficha, v: string | boolean) => setF((x) => ({ ...x, ficha: { ...x.ficha, [k]: v } }));
  const setMeta = (idx: number, p: Partial<MetaFila>) => setF((x) => ({
    ...x, metas: x.metas.map((m, j) => (j === idx ? { ...m, ...p } : p.fiscal ? { ...m, fiscal: false } : m)) }));

  async function guardar() {
    setErrores({});
    setOcupado(true);
    const json = {
      mir: { ...f.mir, evidencia: f.mir.evidencia || null },
      ficha: {
        ...f.ficha, dimension: f.ficha.dimension || null, frecuencia_id: f.ficha.frecuencia_id || null,
        algoritmo: f.ficha.algoritmo || null, unidad_b: usaB ? f.ficha.unidad_b || null : null,
      },
      metas: {
        anio_base: num(f.anio_base), meta_administracion: num(f.meta_administracion),
        anuales: f.metas.filter((m) => m.anio.trim() !== "").map((m) => ({
          anio: Number(m.anio), valor_a_programado: num(m.a), valor_b_programado: usaB ? num(m.b) : null, es_ejercicio_fiscal: m.fiscal })),
      },
      rangos: Object.fromEntries(COLORES.map(([c]) => [c, { desde: num(f.rangos[c].desde), hasta: num(f.rangos[c].hasta) }])),
    };
    try {
      await api(indicador ? `/api/indicadores/${indicador.id}` : `/api/elementos-matriz/${elemento.id}/indicadores`,
        { method: indicador ? "PATCH" : "POST", json });
      toast.success(indicador ? "Indicador actualizado" : "Indicador creado");
      onGuardado();
    } catch (e) {
      if (e instanceof ApiError) {
        setErrores(e.campos);
        toast.error(e.message);
        if (e.codigo === "FICHA_INCOMPLETA" || e.campos.nombre || e.campos.tipo) setTab("ficha");
        else if (e.codigo === "RANGOS_INVALIDOS") setTab("params");
        else if (e.campos.metas || e.campos.anio || e.campos.valor_b_programado) setTab("metas");
      } else toast.error("Error de conexión");
      setOcupado(false);
    }
  }

  const Tab = ({ id, nombre, bloqueada }: { id: Pestana; nombre: string; bloqueada?: boolean }) => (
    <li className={`${tab === id ? "active" : ""} ${bloqueada ? "deshabilitado" : ""}`}>
      <a href="#" title={bloqueada ? "Elige algoritmo y frecuencia en Ficha técnica" : undefined}
        onClick={(e) => { e.preventDefault(); if (!bloqueada) setTab(id); }}>{nombre}</a>
    </li>
  );
  const solo = (v: string | null) => <div className="dato-solo-lectura">{v || "—"}</div>;

  return (
    <Modal titulo={`${indicador ? "Editar" : "Nuevo"} indicador — ${NIVEL_NOMBRE[elemento.nivel]}${elemento.numero ? ` ${elemento.numero}` : ""}`}
      size="lg" onClose={onClose} footer={<>
        <button className="btn btn-default" onClick={onClose}>Cancelar</button>
        <button className="btn btn-success" onClick={guardar} disabled={ocupado}>Guardar</button></>}>
      <div className="row">
        <div className="col-sm-3"><label>Eje</label>{solo(programa.eje)}</div>
        <div className="col-sm-3"><label>Subtema</label>{solo(programa.subtema)}</div>
        <div className="col-sm-3"><label>Estrategia</label>{solo(programa.estrategia)}</div>
        <div className="col-sm-3"><label>Centro gestor</label>{solo(programa.centro_gestor)}</div>
      </div>
      <div className="row" style={{ marginTop: 8 }}>
        <div className="col-sm-3"><label>Nivel</label>{solo(programa.nivel)}</div>
      </div>
      <ul className="nav nav-tabs tabs-modal" style={{ marginTop: 15 }}>
        <Tab id="mir" nombre="M.I.R." /><Tab id="ficha" nombre="Ficha técnica" />
        <Tab id="metas" nombre="Determinación de metas" bloqueada={!habilitado} />
        <Tab id="params" nombre="Parametrización" bloqueada={!habilitado} />
      </ul>

      {tab === "mir" && (["resumen_narrativo", "medios_verificacion", "supuestos", "evidencia"] as const).map((k) => (
        <Campo key={k} label={{ resumen_narrativo: "Resumen narrativo", medios_verificacion: "Medios de verificación", supuestos: "Supuestos", evidencia: "Evidencia" }[k]}>
          <textarea className="form-control" rows={3} value={f.mir[k]} onChange={(e) => setF({ ...f, mir: { ...f.mir, [k]: e.target.value } })} /></Campo>
      ))}

      {tab === "ficha" && (<>
        <div className="row">
          <div className="col-sm-3"><Campo label="Tipo" error={errores.tipo}>
            <select className="form-control" value={f.ficha.tipo} onChange={(e) => setFicha("tipo", e.target.value)}>
              {TIPOS_INDICADOR.map((t) => <option key={t.valor} value={t.valor}>{t.nombre}</option>)}</select></Campo></div>
          <div className="col-sm-3"><Campo label="Dimensión">
            <select className="form-control" value={f.ficha.dimension} onChange={(e) => setFicha("dimension", e.target.value)}>
              <option value="">— Seleccione —</option>{DIMENSIONES.map((t) => <option key={t.valor} value={t.valor}>{t.nombre}</option>)}</select></Campo></div>
          <div className="col-sm-3"><Campo label="Frecuencia" error={errores.frecuencia_id}>
            <select className="form-control" value={f.ficha.frecuencia_id} onChange={(e) => setFicha("frecuencia_id", e.target.value)}>
              <option value="">— Seleccione —</option>
              {frecuencias.filter((x) => x.activo || x.id === f.ficha.frecuencia_id).map((x) => <option key={x.id} value={x.id}>{x.nombre}</option>)}</select></Campo></div>
          <div className="col-sm-3"><Campo label="Prioritario">
            <div className="checkbox" style={{ margin: 0 }}><label><input type="checkbox" checked={f.ficha.prioritario} onChange={(e) => setFicha("prioritario", e.target.checked)} /> Sí</label></div></Campo></div>
        </div>
        <Campo label="Nombre del indicador" error={errores.nombre}>
          <input className="form-control" value={f.ficha.nombre} onChange={(e) => setFicha("nombre", e.target.value)} /></Campo>
        <Campo label="Interpretación"><textarea className="form-control" rows={2} value={f.ficha.interpretacion} onChange={(e) => setFicha("interpretacion", e.target.value)} /></Campo>
        <div className="row">
          <div className="col-sm-4"><Campo label="Unidad de medida"><input className="form-control" value={f.ficha.unidad_medida} onChange={(e) => setFicha("unidad_medida", e.target.value)} /></Campo></div>
          <div className="col-sm-4"><Campo label="Algoritmo de cálculo" error={errores.algoritmo}>
            <select className="form-control" value={f.ficha.algoritmo} onChange={(e) => setFicha("algoritmo", e.target.value)}>
              <option value="">— Seleccione —</option>{ALGORITMOS.map((a) => <option key={a.valor} value={a.valor}>{a.nombre}</option>)}</select></Campo></div>
        </div>
        <div className="row">
          <div className="col-sm-6"><Campo label="Variable A — unidad"><input className="form-control" value={f.ficha.unidad_a} onChange={(e) => setFicha("unidad_a", e.target.value)} /></Campo></div>
          {usaB && <div className="col-sm-6"><Campo label="Variable B — unidad"><input className="form-control" value={f.ficha.unidad_b} onChange={(e) => setFicha("unidad_b", e.target.value)} /></Campo></div>}
        </div>
      </>)}

      {tab === "metas" && habilitado && (<>
        <div className="row">
          <div className="col-sm-3"><Campo label="Año base"><input type="number" className="form-control" value={f.anio_base} onChange={(e) => setF({ ...f, anio_base: e.target.value })} /></Campo></div>
          <div className="col-sm-3"><Campo label="Meta de la administración"><input type="number" step="any" className="form-control" value={f.meta_administracion} onChange={(e) => setF({ ...f, meta_administracion: e.target.value })} /></Campo></div>
        </div>
        {(errores.metas || errores.anio) && <p className="text-danger">{errores.metas || errores.anio}</p>}
        <table className="table table-condensed">
          <thead><tr><th style={{ width: 110 }}>Año</th><th>Variable A (programado)</th>{usaB && <th>Variable B (programado)</th>}<th style={{ width: 130 }}>Ejercicio fiscal</th><th style={{ width: 50 }} /></tr></thead>
          <tbody>
            {f.metas.map((m, idx) => (
              <tr key={idx}>
                <td><input type="number" className="form-control input-sm" value={m.anio} onChange={(e) => setMeta(idx, { anio: e.target.value })} /></td>
                <td><input type="number" step="any" className="form-control input-sm" value={m.a} onChange={(e) => setMeta(idx, { a: e.target.value })} /></td>
                {usaB && <td><input type="number" step="any" className="form-control input-sm" value={m.b} onChange={(e) => setMeta(idx, { b: e.target.value })} /></td>}
                <td><label style={{ margin: 0 }}><input type="checkbox" checked={m.fiscal} onChange={(e) => setMeta(idx, { fiscal: e.target.checked })} /> Año vigente</label></td>
                <td><button className="btn btn-xs btn-danger" title="Quitar año" onClick={() => setF((x) => ({ ...x, metas: x.metas.filter((_, j) => j !== idx) }))}><i className="fa fa-trash" /></button></td>
              </tr>
            ))}
            {!f.metas.length && <tr><td colSpan={5} className="text-center text-muted">Sin metas anuales</td></tr>}
          </tbody>
        </table>
        <button className="btn btn-sm btn-success" onClick={() => setF((x) => ({ ...x, metas: [...x.metas, { anio: String((Math.max(0, ...x.metas.map((m) => Number(m.anio) || 0)) || new Date().getFullYear() - 1) + 1), a: "", b: "", fiscal: false }] }))}>
          <i className="fa fa-plus" /> Agregar año</button>
      </>)}

      {tab === "params" && habilitado && (<>
        <p className="text-muted">Rangos absolutos del semáforo para este indicador (no son porcentajes fijos). No pueden traslaparse; no es necesario cubrir todos los valores posibles.</p>
        {COLORES.map(([c, nombre]) => (
          <div className="row" key={c}>
            <div className="col-sm-2" style={{ paddingTop: 28 }}><span className={`semaforo semaforo-${c}`} /> {nombre}</div>
            <div className="col-sm-3"><Campo label="De" error={errores[`rango_${c}`]}><input type="number" step="any" className="form-control" value={f.rangos[c].desde}
              onChange={(e) => setF({ ...f, rangos: { ...f.rangos, [c]: { ...f.rangos[c], desde: e.target.value } } })} /></Campo></div>
            <div className="col-sm-3"><Campo label="A"><input type="number" step="any" className="form-control" value={f.rangos[c].hasta}
              onChange={(e) => setF({ ...f, rangos: { ...f.rangos, [c]: { ...f.rangos[c], hasta: e.target.value } } })} /></Campo></div>
          </div>
        ))}
      </>)}
    </Modal>
  );
}
