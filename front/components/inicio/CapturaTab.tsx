"use client";
import { useCallback, useEffect, useState } from "react";
import { mensajeError } from "@/components/Campo";
import { Modal } from "@/components/Modal";
import { toast } from "@/components/Toasts";
import { ApiError, api } from "@/lib/api.client";
import { MESES } from "@/lib/permisos";
import { NIVEL_NOMBRE, fmt, nombreAlgoritmo, num, str, type ColorSemaforo, type ProgramaInfo, type Resultado } from "@/lib/mir";
import { Semaforo } from "./Semaforo";

type General = {
  id: string; nombre: string; interpretacion: string; tipo: string; dimension: string | null; unidad_medida: string;
  algoritmo: string | null; usa_b: boolean; unidad_a: string; unidad_b: string | null; nivel: string; numero: string;
  anio_base: number | null; meta_administracion: number | null;
};
type FilaLista = General & Resultado & { anio: number };
type Rejilla = Resultado & {
  indicador: General; anio: number; anios: number[];
  meta: { valor_a_programado: number | null; valor_b_programado: number | null; es_ejercicio_fiscal: boolean } | null;
  meses: { mes: number; valor_a: number | null; valor_b: number | null; capturable: boolean }[];
};

export function CapturaTab({ programaId }: { programaId: string }) {
  const [datos, setDatos] = useState<{ programa: ProgramaInfo; indicadores: FilaLista[] } | null>(null);
  const [abierto, setAbierto] = useState<string | null>(null);
  const cargar = useCallback(async () => setDatos(await api(`/api/programas/${programaId}/captura-avances`)), [programaId]);
  useEffect(() => { cargar().catch((e) => toast.error(mensajeError(e))); }, [cargar]);
  if (!datos) return <p className="text-muted">Cargando…</p>;
  return (
    <>
      <div className="table-responsive">
        <table className="table table-hover">
          <thead><tr><th style={{ width: 130 }}>Nivel</th><th>Indicador</th><th>Algoritmo</th><th style={{ width: 70 }}>Año</th>
            <th style={{ width: 120 }}>Cumplimiento</th><th style={{ width: 90 }}>Semáforo</th><th style={{ width: 100 }}>Acciones</th></tr></thead>
          <tbody>
            {!datos.indicadores.length && <tr><td colSpan={7} className="text-center text-muted">Este programa aún no tiene indicadores. Créalos en la Matriz de indicadores.</td></tr>}
            {datos.indicadores.map((i) => (
              <tr key={i.id}>
                <td>{NIVEL_NOMBRE[i.nivel]}{i.numero ? ` ${i.numero}` : ""}</td><td>{i.nombre || "(sin nombre)"}</td>
                <td>{nombreAlgoritmo(i.algoritmo)}</td><td>{i.anio}</td><td>{fmt(i.cumplimiento)}</td>
                <td><Semaforo color={i.color} /></td>
                <td><button className="btn btn-xs btn-info" onClick={() => setAbierto(i.id)}><i className="fa fa-pencil-square-o" /> Capturar</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {abierto && <AvanceModal indicadorId={abierto} onClose={() => { setAbierto(null); cargar(); }} />}
    </>
  );
}

type Celda = { a: string; b: string };

function AvanceModal({ indicadorId, onClose }: { indicadorId: string; onClose: () => void }) {
  const [anio, setAnio] = useState<number | null>(null);
  const [rej, setRej] = useState<Rejilla | null>(null);
  const [celdas, setCeldas] = useState<Celda[]>([]);
  const [calc, setCalc] = useState<Resultado | null>(null);
  const [nuevoAnio, setNuevoAnio] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const cargar = useCallback(async (a: number | null) => {
    const r = await api<Rejilla>(`/api/indicadores/${indicadorId}/avances${a ? `?anio=${a}` : ""}`);
    setRej(r); setAnio(r.anio); setCalc(null);
    setCeldas(r.meses.map((m) => ({ a: str(m.valor_a), b: str(m.valor_b) })));
  }, [indicadorId]);
  useEffect(() => { cargar(null).catch((e) => toast.error(mensajeError(e))); }, [cargar]);

  // Recalcula en vivo en el servidor (mismo motor que al leer): sumatoria, cumplimiento y semáforo.
  const cuerpo = (cs: Celda[]) => ({ meses: cs.map((c, i) => ({ mes: i + 1, valor_a: num(c.a), valor_b: rej?.indicador.usa_b ? num(c.b) : null })) });
  useEffect(() => {
    if (!rej || !celdas.length) return;
    const t = setTimeout(() => {
      api<Resultado>(`/api/indicadores/${indicadorId}/avances/calcular`, { method: "POST", json: cuerpo(celdas) })
        .then(setCalc).catch(() => undefined);
    }, 250);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [celdas]);

  async function guardar() {
    if (!rej) return;
    setOcupado(true);
    try {
      const r = await api<{ guardados: number[]; rechazados: { mes: number; mensaje: string }[]; rejilla: Rejilla }>(
        `/api/indicadores/${indicadorId}/avances?anio=${rej.anio}`, { method: "PUT", json: cuerpo(celdas) });
      setRej(r.rejilla); setCeldas(r.rejilla.meses.map((m) => ({ a: str(m.valor_a), b: str(m.valor_b) }))); setCalc(null);
      if (r.rechazados.length) toast.warning(`No se guardaron: ${r.rechazados.map((x) => MESES[x.mes - 1]).join(", ")} (fuera de los meses activos y de la tolerancia). Se guardó el resto.`);
      else toast.success("Avances guardados");
    } catch (e) {
      if (e instanceof ApiError && e.codigo === "MESES_NO_CAPTURABLES") toast.error(`${e.message}: ${Object.keys(e.campos).map((k) => MESES[Number(k.replace("mes_", "")) - 1]).join(", ")}`);
      else toast.error(mensajeError(e));
    } finally { setOcupado(false); }
  }

  if (!rej) return <Modal titulo="Captura de avances" size="xl" onClose={onClose}><p className="text-muted">Cargando…</p></Modal>;
  const i = rej.indicador;
  const res: Resultado = calc ?? rej;
  const set = (idx: number, k: "a" | "b", v: string) => setCeldas((cs) => cs.map((c, j) => (j === idx ? { ...c, [k]: v } : c)));
  const dato = (t: string, v: React.ReactNode) => <div className="col-sm-3"><label>{t}</label><div className="dato-solo-lectura">{v || "—"}</div></div>;
  const ex = (f: "fn" | "fa") => `/api/indicadores/${i.id}/exportar?formato=${f}&anio=${rej.anio}`;

  return (
    <Modal titulo={`Captura de avances — ${NIVEL_NOMBRE[i.nivel]}${i.numero ? ` ${i.numero}` : ""}`} size="xl" onClose={onClose} footer={<>
      <a className="btn btn-default" href={ex("fn")} title="Ficha Narrativa"><i className="fa fa-file-pdf-o" /> Exportar FN</a>
      <a className="btn btn-default" href={ex("fa")} title="Ficha de Avance"><i className="fa fa-file-pdf-o" /> Exportar FA</a>
      <button className="btn btn-default" onClick={onClose}>Cerrar</button>
      <button className="btn btn-success" onClick={guardar} disabled={ocupado}>Guardar</button></>}>
      <div className="row">
        <div className="col-sm-12"><label>Indicador</label><div className="dato-solo-lectura">{i.nombre}</div></div>
      </div>
      <div className="row" style={{ marginTop: 8 }}>
        {dato("Interpretación", i.interpretacion)}{dato("Algoritmo", nombreAlgoritmo(i.algoritmo))}
        {dato("Unidad de medida", i.unidad_medida)}{dato("Variable A", i.unidad_a)}
      </div>
      <div className="row" style={{ marginTop: 8 }}>
        {i.usa_b && dato("Variable B", i.unidad_b)}
        {dato("Línea base (año)", i.anio_base)}{dato("Meta de la administración", fmt(i.meta_administracion))}
        {dato(`Meta ${rej.anio}`, rej.meta ? `A: ${fmt(rej.meta.valor_a_programado)}${i.usa_b ? `   B: ${fmt(rej.meta.valor_b_programado)}` : ""}` : "Sin meta")}
      </div>
      <div className="toolbar" style={{ marginTop: 16 }}>
        <label style={{ margin: 0 }}>Año</label>
        <select className="form-control" style={{ width: 110 }} value={rej.anio} onChange={(e) => cargar(Number(e.target.value))}>
          {rej.anios.map((a) => <option key={a} value={a}>{a}</option>)}</select>
        <input type="number" className="form-control" style={{ width: 100 }} placeholder="Otro año" value={nuevoAnio} onChange={(e) => setNuevoAnio(e.target.value)} />
        <button className="btn btn-default btn-sm" disabled={!nuevoAnio} onClick={() => { cargar(Number(nuevoAnio)); setNuevoAnio(""); }}>Ver año</button>
      </div>
      <div className="rejilla-wrap">
        <table className="table table-bordered table-condensed rejilla">
          <thead><tr><th />{MESES.map((m) => <th key={m}>{m}</th>)}<th>Sumatoria</th><th>Cumplimiento</th></tr></thead>
          <tbody>
            {(["a", ...(i.usa_b ? ["b"] : [])] as ("a" | "b")[]).map((v) => (
              <tr key={v}>
                <th>Var {v.toUpperCase()}</th>
                {rej.meses.map((m, idx) => (
                  <td key={m.mes} style={m.capturable ? undefined : { background: "#f1f1f1" }}>
                    <input type="number" step="any" disabled={!m.capturable} value={celdas[idx]?.[v] ?? ""}
                      title={m.capturable ? undefined : "Mes fuera de los meses activos y de la tolerancia"}
                      onChange={(e) => set(idx, v, e.target.value)} /></td>
                ))}
                <td>{fmt(v === "a" ? res.sumatoria_a : res.sumatoria_b)}</td>
                {v === "a" && <td rowSpan={i.usa_b ? 2 : 1}><strong>{fmt(res.cumplimiento)}</strong>{" "}<Semaforo color={res.color as ColorSemaforo} conTexto /></td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Modal>
  );
}
