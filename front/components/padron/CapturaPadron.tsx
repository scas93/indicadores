"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Autocompleto } from "../Autocompleto";
import { Campo, mensajeError } from "../Campo";
import { Confirmar } from "../Confirmar";
import { SelectBuscable } from "../SelectBuscable";
import { toast } from "../Toasts";
import { useTipo } from "../TipoContext";
import { ApiError, api } from "@/lib/api.client";
import { puede } from "@/lib/permisos";
import { CATALOGOS_PADRON } from "./catalogos";
import { ModalCatalogo } from "./CatalogoPadron";

type Fila = { id: string; [k: string]: any };
type Programa = { id: string; ejercicio_fiscal: number; clave: string; nombre: string; centro_gestor: string | null };
type Calculo = { edad: number | null; grupo_edad: string | null; tiene_fecha_nacimiento: boolean };

const fechaCorta = (iso: string) => (iso ? iso.split("-").reverse().join("/") : "");

/** Pantalla "Padron de Beneficiarios": captura de apoyos entregados. Programas asignados, beneficiario con
 *  autocompletado (CURP o nombre), edad y grupo calculados, apoyo -> descripción en cascada y las capturas del día. */
export function CapturaPadron() {
  const tipo = useTipo();
  const [programas, setProgramas] = useState<Programa[]>([]);
  const [programaId, setProgramaId] = useState("");
  const [hoy, setHoy] = useState("");
  const [ben, setBen] = useState<Fila | null>(null);
  const [curp, setCurp] = useState("");
  const [nombre, setNombre] = useState("");
  const [calculo, setCalculo] = useState<Calculo | null>(null);
  const [niveles, setNiveles] = useState<Fila[]>([]);
  const [nivelId, setNivelId] = useState("");
  const [apoyos, setApoyos] = useState<Fila[]>([]);
  const [apoyo, setApoyo] = useState<Fila | null>(null);
  const [apoyoTexto, setApoyoTexto] = useState("");
  const [descripciones, setDescripciones] = useState<Fila[]>([]);
  const [descId, setDescId] = useState("");
  const [cantidad, setCantidad] = useState("1");
  const [entrega, setEntrega] = useState("");
  const [obs, setObs] = useState("");
  const [errores, setErrores] = useState<Record<string, string>>({});
  const [ocupado, setOcupado] = useState(false);
  const [modal, setModal] = useState<null | "alta" | Fila>(null);
  const [dia, setDia] = useState<Fila[] | null>(null);
  const [borrar, setBorrar] = useState<Fila | null>(null);

  const programa = programas.find((p) => p.id === programaId);
  const falla = (e: unknown) => toast.error(mensajeError(e));

  const cargarDia = useCallback(() => api<Fila[]>("/api/padron/capturas").then(setDia).catch(falla), []);
  useEffect(() => {
    api<Programa[]>("/api/padron/programas").then((l) => { setProgramas(l); if (l.length === 1) setProgramaId(l[0].id); }).catch(falla);
    api<{ hoy: string }>("/api/padron/contexto").then((c) => { setHoy(c.hoy); setEntrega(c.hoy); }).catch(falla);
    api<Fila[]>("/api/niveles-socioeconomicos").then(setNiveles).catch(falla);
    cargarDia();
  }, [cargarDia]);

  // Apoyos del programa elegido; al cambiar de programa se limpian apoyo y descripción
  useEffect(() => {
    setApoyo(null); setApoyoTexto(""); setDescId(""); setDescripciones([]);
    if (!programaId) { setApoyos([]); return; }
    api<Fila[]>(`/api/apoyos?programa_id=${programaId}`).then(setApoyos).catch(falla);
  }, [programaId]);
  useEffect(() => {
    setDescId("");
    if (!apoyo) { setDescripciones([]); return; }
    api<Fila[]>(`/api/descripciones-apoyo?apoyo_id=${apoyo.id}`).then(setDescripciones).catch(falla);
  }, [apoyo]);
  // Edad y grupo salen de la fecha de nacimiento (a la fecha de entrega)
  useEffect(() => {
    if (!ben || !entrega) { setCalculo(null); return; }
    api<Calculo>(`/api/padron/capturas/calculo?beneficiario_id=${ben.id}&fecha_entrega=${entrega}`).then(setCalculo).catch(falla);
  }, [ben, entrega]);

  const elegirBen = useCallback((b: Fila | null) => { setBen(b); setCurp(b?.curp ?? ""); setNombre(b?.nombre ?? ""); }, []);
  const buscarBen = useCallback(async (q: string, campo: "curp" | "nombre") => {
    const r = await api<Fila[]>(`/api/beneficiarios-buscar?q=${encodeURIComponent(q)}`);
    return r.map((b) => ({ valor: b.id, etiqueta: campo === "curp" ? `${b.curp} — ${b.nombre}` : `${b.nombre} (${b.curp})`, b }));
  }, []);
  const apoyoOps = useMemo(() => apoyos, [apoyos]);

  if (!puede.catalogosPadron(tipo)) return <p className="text-muted">Sin acceso a este módulo.</p>;

  async function guardar() {
    setOcupado(true); setErrores({});
    try {
      await api("/api/padron/capturas", { method: "POST", json: {
        beneficiario_id: ben?.id ?? null, programa_id: programaId || null, apoyo_id: apoyo?.id ?? null,
        descripcion_apoyo_id: descId || null, nivel_socioeconomico_id: nivelId || null,
        cantidad: cantidad === "" ? null : Number(cantidad), fecha_entrega: entrega || null, observaciones: obs } });
      toast.success("Captura guardada");
      elegirBen(null); setNivelId(""); setApoyo(null); setApoyoTexto(""); setDescId(""); setCantidad("1"); setEntrega(hoy); setObs("");
      await cargarDia();
    } catch (e) {
      if (e instanceof ApiError) { setErrores(e.campos); toast.error(e.message); } else falla(e);
    } finally { setOcupado(false); }
  }

  async function eliminar() {
    const f = borrar; setBorrar(null);
    if (!f) return;
    try { await api(`/api/padron/capturas/${f.id}`, { method: "DELETE" }); toast.success("Captura eliminada"); await cargarDia(); } catch (e) { falla(e); }
  }

  const grupos = [{ etiqueta: "Programas", opciones: programas.map((p) => ({ valor: p.id, etiqueta: `${p.clave} — ${p.nombre}` })) }];
  return (
    <>
      <h3 className="page-heading">Padron de Beneficiarios</h3>
      <div className="panel"><div className="panel-body">
        <div className="captura-bloque">
          <h4>Datos del programa</h4>
          <div className="row">
            <div className="col-sm-6"><Campo label="Programa" error={errores.programa_id}>
              <SelectBuscable grupos={grupos} valor={programaId} onChange={setProgramaId} placeholder="--Selecciona el programa--" ariaLabel="Programa" /></Campo></div>
            <div className="col-sm-4"><Campo label="Centro Gestor"><input className="form-control" readOnly value={programa?.centro_gestor ?? ""} /></Campo></div>
            <div className="col-sm-2"><Campo label="Fecha Registro"><input className="form-control" readOnly value={fechaCorta(hoy)} /></Campo></div>
          </div>
        </div>

        <div className="captura-bloque">
          <h4>Datos del beneficiario</h4>
          <div className="row">
            <div className="col-sm-4"><Campo label="CURP" error={errores.beneficiario_id}>
              <div className="captura-curp">
                <Autocompleto texto={curp} onTexto={(t) => { setCurp(t); if (ben) { setBen(null); setNombre(""); } }} ariaLabel="CURP" placeholder="Escriba y Seleccione"
                  buscar={(q) => buscarBen(q, "curp")} onElegir={(o: any) => elegirBen(o.b)} />
                <button type="button" className="btn btn-info" title={ben ? "Modificar beneficiario" : "Nuevo beneficiario"}
                  onClick={() => setModal(ben ?? "alta")}><i className="fa fa-pencil" /></button>
              </div></Campo></div>
            <div className="col-sm-8"><Campo label="Nombre">
              <Autocompleto texto={nombre} onTexto={(t) => { setNombre(t); if (ben) { setBen(null); setCurp(""); } }} ariaLabel="Nombre" placeholder="Escriba y Seleccione"
                buscar={(q) => buscarBen(q, "nombre")} onElegir={(o: any) => elegirBen(o.b)} /></Campo></div>
          </div>
          <div className="row">
            <div className="col-sm-2"><Campo label="Edad"><input className="form-control" readOnly value={calculo?.edad ?? ""} /></Campo></div>
            <div className="col-sm-3"><Campo label="Grupo de Edad"><input className="form-control" readOnly
              value={calculo ? (calculo.grupo_edad ?? (calculo.tiene_fecha_nacimiento ? "Sin grupo de edad" : "Sin fecha de nacimiento")) : ""} /></Campo></div>
            <div className="col-sm-3"><Campo label="Nivel Socioeconómico" error={errores.nivel_socioeconomico_id}>
              <select className="form-control" value={nivelId} onChange={(e) => setNivelId(e.target.value)}>
                <option value="">— Seleccione —</option>{niveles.map((n) => <option key={n.id} value={n.id}>{n.nombre}</option>)}</select></Campo></div>
          </div>
          <div className="row">
            <div className="col-sm-6"><Campo label="Apoyo" error={errores.apoyo_id}>
              <Autocompleto texto={apoyoTexto} onTexto={(t) => { setApoyoTexto(t); if (apoyo) setApoyo(null); }} ariaLabel="Apoyo" placeholder="Escriba y Seleccione"
                deshabilitado={!programaId}
                buscar={async (q) => apoyoOps.filter((a) => `${a.clave} ${a.nombre}`.toLowerCase().includes(q.trim().toLowerCase()))
                  .slice(0, 20).map((a) => ({ valor: a.id, etiqueta: a.nombre, a }) as any)}
                onElegir={(o: any) => { setApoyo(o.a); setApoyoTexto(o.a.nombre); }} /></Campo></div>
            <div className="col-sm-6"><Campo label="Descripción de Apoyo" error={errores.descripcion_apoyo_id}>
              <select className="form-control" value={descId} disabled={!apoyo} onChange={(e) => setDescId(e.target.value)}>
                <option value="">— Seleccione —</option>{descripciones.map((d) => <option key={d.id} value={d.id}>{d.nombre}</option>)}</select></Campo></div>
          </div>
          <div className="row">
            <div className="col-sm-2"><Campo label="Cantidad" error={errores.cantidad}>
              <input className="form-control" type="number" min={1} value={cantidad} onChange={(e) => setCantidad(e.target.value)} /></Campo></div>
            <div className="col-sm-3"><Campo label="Fecha de Entrega" error={errores.fecha_entrega}>
              <input className="form-control" type="date" value={entrega} onChange={(e) => setEntrega(e.target.value)} /></Campo></div>
            <div className="col-sm-7"><Campo label="Observaciones">
              <input className="form-control" value={obs} onChange={(e) => setObs(e.target.value)} /></Campo></div>
          </div>
          <button className="btn btn-success" onClick={guardar} disabled={ocupado}><i className="fa fa-save" /> Guardar</button>
        </div>

        <div className="captura-bloque">
          <h4>Capturas del día</h4>
          <div className="table-responsive">
            <table className="table table-hover">
              <thead><tr><th>CURP</th><th>Nombre</th><th>Edad</th><th>Grupo Edad</th><th>Niv. Socioeconómico</th><th>Apoyo</th><th>Cantidad</th>
                <th>Descrip. Apoyo</th><th>Observaciones</th><th style={{ width: 70 }}>Acciones</th></tr></thead>
              <tbody>
                {dia === null && <tr><td colSpan={10} className="text-center text-muted">Cargando…</td></tr>}
                {dia && !dia.length && <tr><td colSpan={10} className="text-center text-muted">Sin capturas hoy</td></tr>}
                {dia?.map((f) => (
                  <tr key={f.id}>
                    <td>{f.curp}</td><td>{f.nombre}</td><td>{f.edad ?? ""}</td><td>{f.grupo_edad ?? ""}</td><td>{f.nivel_socioeconomico ?? ""}</td>
                    <td>{f.apoyo}</td><td>{f.cantidad}</td><td>{f.descripcion_apoyo ?? ""}</td><td>{f.observaciones ?? ""}</td>
                    <td><button className="btn btn-xs btn-danger" title="Eliminar" onClick={() => setBorrar(f)}><i className="fa fa-trash" /></button></td>
                  </tr>))}
              </tbody>
            </table>
          </div>
        </div>
      </div></div>

      {modal && <ModalCatalogo cfg={CATALOGOS_PADRON.beneficiarios} fila={modal === "alta" ? null : modal} onClose={() => setModal(null)}
        onGuardado={(b) => { setModal(null); elegirBen(b); }} />}
      {borrar && <Confirmar titulo="Eliminar captura" mensaje="¿Eliminar esta captura?" onClose={() => setBorrar(null)} onConfirmar={eliminar} />}
    </>
  );
}
