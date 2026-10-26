"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Campo, mensajeError } from "./Campo";
import { Modal } from "./Modal";
import { toast } from "./Toasts";
import { useTipo } from "./TipoContext";
import { ApiError, api } from "@/lib/api.client";
import { puede } from "@/lib/permisos";

type Fila = { id: string; clave: string; nombre: string; activo: boolean; [k: string]: any };
/** `abuelo`: nivel previo en dos desplegables (p. ej. Estrategias: primero Eje, luego Subtema), tanto en el filtro
 *  como en el alta; `campo` es el campo del padre que apunta al abuelo (subtema.eje_id). */
export type Padre = { campo: string; ruta: string; label: string; abuelo?: { campo: string; ruta: string; label: string } };

/** Tabla + modal para un nivel de planeación (centros gestores, ejes, subtemas, estrategias,
 *  frecuencias). Nunca borra: "Deshabilitar" pone activo=false y lo saca de los selectores. */
export function CatalogoCrud({ titulo, ruta, padre }: { titulo: string; ruta: string; padre?: Padre }) {
  const tipo = useTipo();
  const editable = puede.editarPlaneacion(tipo);
  const [lista, setLista] = useState<Fila[] | null>(null);
  const [padres, setPadres] = useState<Fila[]>([]);
  const [abuelos, setAbuelos] = useState<Fila[]>([]);
  const [q, setQ] = useState("");
  const [filtroAbuelo, setFiltroAbuelo] = useState("");
  const [filtroPadre, setFiltroPadre] = useState("");
  const [modal, setModal] = useState<null | "alta" | Fila>(null);

  const cargar = useCallback(async () => {
    setLista(await api(`/api/${ruta}`));
    if (padre) setPadres(await api(`/api/${padre.ruta}`));
    if (padre?.abuelo) setAbuelos(await api(`/api/${padre.abuelo.ruta}`));
  }, [ruta, padre]);
  useEffect(() => { cargar().catch((e) => toast.error(mensajeError(e))); }, [cargar]);

  const nombrePadre = useMemo(() => new Map(padres.map((p) => [p.id, `${p.clave} — ${p.nombre}`])), [padres]);
  const nombreAbuelo = useMemo(() => new Map(abuelos.map((a) => [a.id, `${a.clave} — ${a.nombre}`])), [abuelos]);
  // Estrategias: la columna Eje sale del subtema (padre) de cada fila
  const abueloDe = (f: Fila) => padre?.abuelo ? nombreAbuelo.get(padres.find((p) => p.id === f[padre.campo])?.[padre.abuelo.campo]) : undefined;
  // opciones del segundo desplegable: solo los padres del abuelo elegido (Subtemas del Eje)
  const padresFiltro = useMemo(() => !padre?.abuelo ? padres
    : padres.filter((p) => !!filtroAbuelo && p[padre.abuelo!.campo] === filtroAbuelo), [padres, padre, filtroAbuelo]);
  const filtrada = useMemo(() => (lista ?? []).filter((f) => {
    if (padre && filtroPadre && f[padre.campo] !== filtroPadre) return false;
    if (padre?.abuelo && filtroAbuelo && !filtroPadre && !padresFiltro.some((p) => p.id === f[padre.campo])) return false;
    return `${f.clave} ${f.nombre}`.toLowerCase().includes(q.toLowerCase());
  }), [lista, q, filtroPadre, filtroAbuelo, padre, padresFiltro]);

  async function alternar(f: Fila) {
    try {
      await api(`/api/${ruta}/${f.id}`, { method: "PATCH", json: { activo: !f.activo } });
      toast.success(f.activo ? "Deshabilitado" : "Habilitado");
      cargar();
    } catch (e) { toast.error(mensajeError(e)); }
  }

  return (
    <>
      <h3 className="page-heading">{titulo}</h3>
      <div className="panel"><div className="panel-body">
        <div className="toolbar">
          <input className="form-control" style={{ maxWidth: 260 }} placeholder="Buscar" value={q} onChange={(e) => setQ(e.target.value)} />
          {padre?.abuelo && (
            <select className="form-control" style={{ maxWidth: 260 }} value={filtroAbuelo}
              onChange={(e) => { setFiltroAbuelo(e.target.value); setFiltroPadre(""); }}>
              <option value="">{padre.abuelo.label}: todos</option>
              {abuelos.map((a) => <option key={a.id} value={a.id}>{a.clave} — {a.nombre}</option>)}
            </select>
          )}
          {padre && (
            <select className="form-control" style={{ maxWidth: 300 }} value={filtroPadre} disabled={!!padre.abuelo && !filtroAbuelo}
              title={padre.abuelo && !filtroAbuelo ? `Elige primero ${padre.abuelo.label.toLowerCase()}` : undefined}
              onChange={(e) => setFiltroPadre(e.target.value)}>
              <option value="">{padre.label}: todos</option>
              {padresFiltro.map((p) => <option key={p.id} value={p.id}>{p.clave} — {p.nombre}</option>)}
            </select>
          )}
          <span className="spacer" />
          {editable && <button className="btn btn-success" onClick={() => setModal("alta")}><i className="fa fa-plus" /> Nuevo</button>}
        </div>
        <div className="table-responsive">
          <table className="table table-hover">
            <thead><tr>
              <th style={{ width: 120 }}>Clave</th><th>Nombre</th>{padre?.abuelo && <th>{padre.abuelo.label}</th>}{padre && <th>{padre.label}</th>}
              <th style={{ width: 100 }}>Estado</th>{editable && <th style={{ width: 110 }}>Acciones</th>}
            </tr></thead>
            <tbody>
              {lista === null && <tr><td colSpan={6} className="text-center text-muted">Cargando…</td></tr>}
              {lista && !filtrada.length && <tr><td colSpan={6} className="text-center text-muted">Sin registros</td></tr>}
              {filtrada.map((f) => (
                <tr key={f.id} className={f.activo ? "" : "text-muted"}>
                  <td>{f.clave}</td><td>{f.nombre}</td>
                  {padre?.abuelo && <td>{abueloDe(f) ?? "—"}</td>}
                  {padre && <td>{nombrePadre.get(f[padre.campo]) ?? "—"}</td>}
                  <td><span className={`label label-${f.activo ? "success" : "default"}`}>{f.activo ? "Activo" : "Deshabilitado"}</span></td>
                  {editable && <td>
                    <button className="btn btn-xs btn-info" title="Editar" onClick={() => setModal(f)}><i className="fa fa-pencil" /></button>{" "}
                    <button className={`btn btn-xs ${f.activo ? "btn-warning" : "btn-success"}`}
                      title={f.activo ? "Deshabilitar" : "Habilitar"} onClick={() => alternar(f)}>
                      <i className={`fa ${f.activo ? "fa-ban" : "fa-check"}`} /></button>
                  </td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div></div>
      {modal && <ModalCatalogo titulo={titulo} ruta={ruta} padre={padre} padres={padres.filter((p) => p.activo)} abuelos={abuelos.filter((a) => a.activo)}
        fila={modal === "alta" ? null : modal} onClose={() => setModal(null)}
        onGuardado={() => { setModal(null); cargar(); }} />}
    </>
  );
}

function ModalCatalogo({ titulo, ruta, padre, padres, abuelos, fila, onClose, onGuardado }: {
  titulo: string; ruta: string; padre?: Padre; padres: Fila[]; abuelos: Fila[]; fila: Fila | null; onClose: () => void; onGuardado: () => void;
}) {
  const padreInicial = padre ? (fila?.[padre.campo] ?? "") : "";
  // Estrategias: Eje (abuelo) -> Subtema (padre); al editar, el eje sale del subtema actual
  const abueloInicial = padre?.abuelo ? (padres.find((p) => p.id === padreInicial)?.[padre.abuelo.campo] ?? "") : "";
  const [f, setF] = useState({ clave: fila?.clave ?? "", nombre: fila?.nombre ?? "", padre: padreInicial, abuelo: abueloInicial });
  const [errores, setErrores] = useState<Record<string, string>>({});
  const [ocupado, setOcupado] = useState(false);

  async function guardar() {
    setOcupado(true);
    setErrores({});
    const json: Record<string, unknown> = { clave: f.clave, nombre: f.nombre };
    if (padre) json[padre.campo] = f.padre || null;
    try {
      await api(fila ? `/api/${ruta}/${fila.id}` : `/api/${ruta}`, { method: fila ? "PATCH" : "POST", json });
      toast.success(fila ? "Cambios guardados" : "Registro creado");
      onGuardado();
    } catch (e) {
      if (e instanceof ApiError) { setErrores(e.campos); toast.error(e.message); } else toast.error("Error de conexión");
      setOcupado(false);
    }
  }

  return (
    <Modal titulo={`${fila ? "Editar" : "Nuevo"} — ${titulo}`} onClose={onClose} footer={<>
      <button className="btn btn-default" onClick={onClose}>Cancelar</button>
      <button className="btn btn-success" onClick={guardar} disabled={ocupado}>Guardar</button></>}>
      {padre?.abuelo && <Campo label={padre.abuelo.label}>
        <select className="form-control" value={f.abuelo} onChange={(e) => setF({ ...f, abuelo: e.target.value, padre: "" })}>
          <option value="">— Seleccione —</option>
          {abuelos.map((a) => <option key={a.id} value={a.id}>{a.clave} — {a.nombre}</option>)}
        </select></Campo>}
      {padre && <Campo label={padre.label} error={errores[padre.campo]}>
        <select className="form-control" value={f.padre} disabled={!!padre.abuelo && !f.abuelo} onChange={(e) => setF({ ...f, padre: e.target.value })}>
          <option value="">— Seleccione —</option>
          {padres.filter((p) => !padre.abuelo || p[padre.abuelo.campo] === f.abuelo).map((p) => <option key={p.id} value={p.id}>{p.clave} — {p.nombre}</option>)}
        </select></Campo>}
      <div className="row">
        <div className="col-sm-4"><Campo label="Clave" error={errores.clave}>
          <input className="form-control" value={f.clave} onChange={(e) => setF({ ...f, clave: e.target.value })} autoFocus /></Campo></div>
        <div className="col-sm-8"><Campo label="Nombre" error={errores.nombre}>
          <input className="form-control" value={f.nombre} onChange={(e) => setF({ ...f, nombre: e.target.value })} /></Campo></div>
      </div>
    </Modal>
  );
}
