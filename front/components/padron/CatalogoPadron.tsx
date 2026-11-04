"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Autocompleto } from "../Autocompleto";
import { Campo, mensajeError } from "../Campo";
import { Confirmar } from "../Confirmar";
import { Modal } from "../Modal";
import { SelectBuscable } from "../SelectBuscable";
import { toast } from "../Toasts";
import { useTipo } from "../TipoContext";
import { ApiError, api } from "@/lib/api.client";
import { descargar } from "@/lib/estadisticas";
import { puede } from "@/lib/permisos";
import { ModalDocumentos } from "./DocumentosBeneficiario";
import { CATALOGOS_PADRON, type CampoForm, type CatalogoCfg } from "./catalogos";

type Fila = { id: string; [k: string]: any };

const qs = (o: Record<string, string>) => new URLSearchParams(Object.entries(o).filter(([, v]) => v)).toString();

/** Catálogo del Padrón con el patrón de la referencia: búsqueda (Buscar / Nuevo / Exportar), tabla con casillas,
 *  editar y eliminar por fila, eliminar en lote y alta/edición en modal. Los permisos los valida la API. */
export function CatalogoPadron({ catalogo }: { catalogo: string }) {
  const cfg = CATALOGOS_PADRON[catalogo];  // la configuración trae funciones: no puede venir de una página de servidor
  const tipo = useTipo();
  const [filtros, setFiltros] = useState<Record<string, string>>({});
  const [consulta, setConsulta] = useState<Record<string, string>>({});
  const [lista, setLista] = useState<Fila[] | null>(null);
  const [marcadas, setMarcadas] = useState<Set<string>>(new Set());
  const [modal, setModal] = useState<null | "alta" | Fila>(null);
  const [borrar, setBorrar] = useState<null | Fila | "lote">(null);
  const [docs, setDocs] = useState<Fila | null>(null);
  const [ocupado, setOcupado] = useState(false);

  const cargar = useCallback(async () => {
    setLista(await api(`/api/${cfg.ruta}?${qs(consulta)}`));
    setMarcadas(new Set());
  }, [cfg.ruta, consulta]);
  useEffect(() => { cargar().catch((e) => toast.error(mensajeError(e))); }, [cargar]);

  if (!puede.catalogosPadron(tipo)) return <p className="text-muted">Sin acceso a este módulo.</p>;

  const todas = !!lista?.length && lista.every((f) => marcadas.has(f.id));
  const alternar = (id: string) => setMarcadas((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });

  async function exportar() {
    try { await descargar(`/api/${cfg.ruta}/exportar?${qs(consulta)}`, `${cfg.titulo}.xlsx`); } catch (e) { toast.error(mensajeError(e)); }
  }

  async function eliminar() {
    const objetivo = borrar;
    setOcupado(true);
    try {
      if (objetivo === "lote") {
        const r = await api<{ eliminados: number; rechazados: { motivo: string }[] }>(`/api/${cfg.ruta}/eliminar-lote`, { method: "POST", json: { ids: [...marcadas] } });
        if (r.eliminados) toast.success(`${r.eliminados} eliminado(s)`);
        r.rechazados.forEach((x) => toast.error(x.motivo));
      } else if (objetivo) {
        await api(`/api/${cfg.ruta}/${objetivo.id}`, { method: "DELETE" });
        toast.success("Registro eliminado");
      }
      setBorrar(null);
      await cargar();
    } catch (e) { toast.error(mensajeError(e)); setBorrar(null); } finally { setOcupado(false); }
  }

  const acciones = (f: Fila) => (
    <td>
      <button className="btn btn-xs btn-info" title="Editar" onClick={() => setModal(f)}><i className="fa fa-pencil" /></button>{" "}
      {cfg.documentos && <><button className="btn btn-xs btn-primary" title="Documentos" onClick={() => setDocs(f)}><i className="fa fa-file-text-o" /></button>{" "}</>}
      <button className="btn btn-xs btn-danger" title="Eliminar" onClick={() => setBorrar(f)}><i className="fa fa-trash" /></button>
    </td>);

  return (
    <>
      <h3 className="page-heading">{cfg.titulo}</h3>
      <div className="panel"><div className="panel-body">
        <form className="toolbar" onSubmit={(e) => { e.preventDefault(); setConsulta({ ...filtros }); }}>
          {cfg.filtros.map((f) => (
            <input key={f.key} className="form-control" style={{ maxWidth: 240 }} placeholder={f.label} aria-label={f.label}
              value={filtros[f.key] ?? ""} onChange={(e) => setFiltros({ ...filtros, [f.key]: e.target.value })} />
          ))}
          <button type="submit" className="btn btn-primary"><i className="fa fa-search" /> Buscar</button>
          <span className="spacer" />
          <button type="button" className="btn btn-success" onClick={() => setModal("alta")}><i className="fa fa-plus" /> Nuevo</button>
          <button type="button" className="btn btn-default" onClick={exportar}><i className="fa fa-file-excel-o" /> Exportar</button>
        </form>
        {cfg.tituloTabla && <h4 className="tabla-titulo">{cfg.tituloTabla} — se han encontrado {lista?.length ?? 0} elementos</h4>}
        <div className="table-responsive">
          <table className="table table-hover">
            <thead><tr>
              <th style={{ width: 80 }}><label style={{ fontWeight: "normal", margin: 0 }}>
                <input type="checkbox" checked={todas} onChange={() => setMarcadas(todas ? new Set() : new Set((lista ?? []).map((f) => f.id)))} /> Todo</label></th>
              {cfg.accionesPrimero && <th style={{ width: cfg.documentos ? 120 : 100 }}>Acciones</th>}
              {cfg.columnas.map((c) => <th key={c.key}>{c.label}</th>)}
              {!cfg.accionesPrimero && <th style={{ width: 100 }}>Acciones</th>}
            </tr></thead>
            <tbody>
              {lista === null && <tr><td colSpan={cfg.columnas.length + 2} className="text-center text-muted">Cargando…</td></tr>}
              {lista && !lista.length && <tr><td colSpan={cfg.columnas.length + 2} className="text-center text-muted">Sin registros</td></tr>}
              {lista?.map((f) => (
                <tr key={f.id}>
                  <td><input type="checkbox" aria-label="Seleccionar" checked={marcadas.has(f.id)} onChange={() => alternar(f.id)} /></td>
                  {cfg.accionesPrimero && acciones(f)}
                  {cfg.columnas.map((c) => <td key={c.key}>{f[c.key] ?? ""}</td>)}
                  {!cfg.accionesPrimero && acciones(f)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <button className="btn btn-danger" disabled={!marcadas.size} onClick={() => setBorrar("lote")}>
          <i className="fa fa-trash" /> Eliminar seleccionados{marcadas.size ? ` (${marcadas.size})` : ""}</button>
      </div></div>
      {docs && <ModalDocumentos beneficiario={{ id: docs.id, curp: docs.curp, nombre: docs.nombre }} onClose={() => setDocs(null)} />}
      {modal && <ModalCatalogo cfg={cfg} fila={modal === "alta" ? null : modal} onClose={() => setModal(null)}
        onGuardado={() => { setModal(null); cargar(); }} />}
      {borrar && <Confirmar titulo="Eliminar" boton={ocupado ? "Eliminando…" : "Eliminar"} onClose={() => setBorrar(null)} onConfirmar={eliminar}
        mensaje={borrar === "lote" ? `¿Eliminar los ${marcadas.size} registros seleccionados? Los que estén en uso no se eliminarán.` : "¿Eliminar este registro? Solo se elimina si nada lo usa."} />}
    </>
  );
}

function useOpciones(fuente: string | null) {
  const [ops, setOps] = useState<Fila[]>([]);
  useEffect(() => {
    let vivo = true;
    if (!fuente) { setOps([]); return; }
    api<Fila[]>(`/api/${fuente}`).then((r) => vivo && setOps(r)).catch((e) => toast.error(mensajeError(e)));
    return () => { vivo = false; };
  }, [fuente]);
  return ops;
}

function CampoInput({ campo, valores, error, onCambio }: { campo: CampoForm; valores: Record<string, string>; error?: string; onCambio: (k: string, v: string) => void }) {
  const fuente = typeof campo.fuente === "function" ? campo.fuente(valores) : campo.fuente ?? null;
  const fijas = campo.opcionesFijas;
  const ops = useOpciones(fijas ? null : fuente);
  const v = valores[campo.key] ?? "";
  const set = (x: string) => onCambio(campo.key, x);
  const etiqueta = (o: Fila) => (campo.opcion ? campo.opcion(o) : o.nombre);
  const grupos = useMemo(() => [{ etiqueta: campo.label, opciones: ops.map((o) => ({ valor: o.id, etiqueta: etiqueta(o) })) }], [ops]); // eslint-disable-line react-hooks/exhaustive-deps
  let control;
  if (campo.tipo === "area") control = <textarea className="form-control" rows={3} value={v} onChange={(e) => set(e.target.value)} />;
  else if (campo.tipo === "fecha") control = <input className="form-control" type="date" value={v} onChange={(e) => set(e.target.value)} />;
  else if (campo.tipo === "numero") control = <input className="form-control" type="number" min={0} value={v} onChange={(e) => set(e.target.value)} />;
  else if (campo.tipo === "colonia") control = (
    <Autocompleto texto={v} ariaLabel={campo.label} placeholder={campo.placeholder}
      onTexto={(t) => { onCambio(campo.key, t); onCambio("colonia_id", ""); }}
      buscar={async (q) => {
        const p = new URLSearchParams({ nombre: q });
        if (valores.municipio_id) p.set("municipio_id", valores.municipio_id);
        const r = await api<Fila[]>(`/api/geo/colonias?${p}`);
        return r.slice(0, 30).map((c) => ({ valor: c.id, etiqueta: `[${c.clave}]${c.nombre}` }));
      }}
      onElegir={(o) => { onCambio(campo.key, o.etiqueta.replace(/^\[[^\]]*\]/, "")); onCambio("colonia_id", o.valor); }} />);
  else if (campo.tipo === "buscable") control = <SelectBuscable grupos={grupos} valor={v} onChange={set} placeholder={`— ${campo.label} —`} ariaLabel={campo.label} />;
  else if (campo.tipo === "lista") control = (
    <select className="form-control" value={v} onChange={(e) => set(e.target.value)} disabled={!fuente && !fijas}>
      <option value="">{campo.sinOpcion ?? "— Seleccione —"}</option>
      {fijas ? fijas.map((o) => <option key={o.valor} value={o.valor}>{o.etiqueta}</option>)
        : ops.map((o) => <option key={o.id} value={o.id}>{etiqueta(o)}</option>)}
    </select>);
  else control = <input className="form-control" value={v} placeholder={campo.placeholder} onChange={(e) => set(e.target.value)} />;
  return <Campo label={campo.label} error={error}>{control}</Campo>;
}

export function ModalCatalogo({ cfg, fila, onClose, onGuardado }: { cfg: CatalogoCfg; fila: Fila | null; onClose: () => void; onGuardado: (registro: Fila) => void }) {
  const [v, setV] = useState<Record<string, string>>(() => Object.fromEntries([...cfg.campos.map((c) => [c.key, String(fila?.[c.key] ?? "")]),
    ...(cfg.campos.some((c) => c.tipo === "colonia") ? [["colonia_id", String(fila?.colonia_id ?? "")]] : [])]));
  const [errores, setErrores] = useState<Record<string, string>>({});
  const [ocupado, setOcupado] = useState(false);

  // Al dar de alta, el Estado arranca en el de la plataforma (Guanajuato en la referencia)
  useEffect(() => {
    const est = cfg.campos.find((c) => c.estadoPorDefecto);
    if (fila || !est) return;
    api<{ id: string; por_defecto: boolean }[]>("/api/geo/estados")
      .then((l) => { const d = l.find((e) => e.por_defecto); if (d) setV((x) => (x[est.key] ? x : { ...x, [est.key]: d.id })); })
      .catch(() => undefined);
  }, [cfg, fila]);

  function cambio(k: string, valor: string) {
    setV((x) => {
      const n = { ...x, [k]: valor };
      if (k === "municipio_id" && n.colonia_id) n.colonia_id = "";  // la colonia de catálogo es de otro municipio: queda como texto libre
      for (let l = cfg.campos.find((c) => c.key === k)?.limpia; l; l = cfg.campos.find((c) => c.key === l)?.limpia) n[l] = "";  // Estado -> Municipio -> Localidad
      return n;
    });
  }

  async function guardar() {
    setOcupado(true);
    setErrores({});
    const json: Record<string, unknown> = {};
    for (const c of cfg.campos) {
      if (c.virtual) continue;
      const x = v[c.key] ?? "";
      json[c.key] = c.tipo === "numero" ? (x === "" ? null : Number(x)) : (c.tipo === "lista" || c.tipo === "buscable" || c.tipo === "fecha") ? (x || null) : x;
    }
    if (cfg.campos.some((c) => c.tipo === "colonia")) json.colonia_id = v.colonia_id || null;
    try {
      const guardado = await api<Fila>(fila ? `/api/${cfg.ruta}/${fila.id}` : `/api/${cfg.ruta}`, { method: fila ? "PATCH" : "POST", json });
      toast.success(fila ? "Cambios guardados" : "Registro creado");
      onGuardado(guardado);
    } catch (e) {
      if (e instanceof ApiError) { setErrores(e.campos); toast.error(e.message); } else toast.error("Error de conexión");
      setOcupado(false);
    }
  }

  // Los campos con ancho comparten renglón (Clave + Nombre, Estado + Municipio)
  const renglones: CampoForm[][] = [];
  for (const c of cfg.campos) {
    const ult = renglones[renglones.length - 1];
    if (c.ancho && ult && ult[0].ancho && ult.reduce((s, x) => s + (x.ancho ?? 12), 0) + c.ancho <= 12) ult.push(c); else renglones.push([c]);
  }
  return (
    <Modal titulo={`Ingresar / Modificar ${cfg.singular}`} onClose={onClose} footer={<>
      <button className="btn btn-default" onClick={onClose}>Cancelar</button>
      <button className="btn btn-success" onClick={guardar} disabled={ocupado}>Guardar</button></>}>
      {renglones.map((r, i) => (
        <div className="row" key={i}>
          {r.map((c) => (
            <div key={c.key} className={`col-sm-${c.ancho ?? 12}`}>
              <CampoInput campo={c} valores={v} error={errores[c.key]} onCambio={cambio} />
            </div>))}
        </div>))}
    </Modal>
  );
}
