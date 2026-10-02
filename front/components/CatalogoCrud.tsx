"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Campo, mensajeError } from "./Campo";
import { Modal } from "./Modal";
import { toast } from "./Toasts";
import { useTipo } from "./TipoContext";
import { ApiError, api } from "@/lib/api.client";
import { puede } from "@/lib/permisos";

type Fila = { id: string; clave: string; nombre: string; activo: boolean; [k: string]: any };
export type Padre = { campo: string; ruta: string; label: string };

/** Tabla + modal para un nivel de planeación (centros gestores, ejes, subtemas, estrategias,
 *  frecuencias). Nunca borra: "Deshabilitar" pone activo=false y lo saca de los selectores. */
export function CatalogoCrud({ titulo, ruta, padre }: { titulo: string; ruta: string; padre?: Padre }) {
  const tipo = useTipo();
  const editable = puede.editarPlaneacion(tipo);
  const [lista, setLista] = useState<Fila[] | null>(null);
  const [padres, setPadres] = useState<Fila[]>([]);
  const [q, setQ] = useState("");
  const [filtroPadre, setFiltroPadre] = useState("");
  const [modal, setModal] = useState<null | "alta" | Fila>(null);

  const cargar = useCallback(async () => {
    setLista(await api(`/api/${ruta}`));
    if (padre) setPadres(await api(`/api/${padre.ruta}`));
  }, [ruta, padre]);
  useEffect(() => { cargar().catch((e) => toast.error(mensajeError(e))); }, [cargar]);

  const nombrePadre = useMemo(() => new Map(padres.map((p) => [p.id, `${p.clave} — ${p.nombre}`])), [padres]);
  const filtrada = useMemo(() => (lista ?? []).filter((f) =>
    (!filtroPadre || f[padre!.campo] === filtroPadre) &&
    `${f.clave} ${f.nombre}`.toLowerCase().includes(q.toLowerCase())), [lista, q, filtroPadre, padre]);

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
          {padre && (
            <select className="form-control" style={{ maxWidth: 300 }} value={filtroPadre} onChange={(e) => setFiltroPadre(e.target.value)}>
              <option value="">{padre.label}: todos</option>
              {padres.map((p) => <option key={p.id} value={p.id}>{p.clave} — {p.nombre}</option>)}
            </select>
          )}
          <span className="spacer" />
          {editable && <button className="btn btn-success" onClick={() => setModal("alta")}><i className="fa fa-plus" /> Nuevo</button>}
        </div>
        <div className="table-responsive">
          <table className="table table-hover">
            <thead><tr>
              <th style={{ width: 120 }}>Clave</th><th>Nombre</th>{padre && <th>{padre.label}</th>}
              <th style={{ width: 100 }}>Estado</th>{editable && <th style={{ width: 110 }}>Acciones</th>}
            </tr></thead>
            <tbody>
              {lista === null && <tr><td colSpan={5} className="text-center text-muted">Cargando…</td></tr>}
              {lista && !filtrada.length && <tr><td colSpan={5} className="text-center text-muted">Sin registros</td></tr>}
              {filtrada.map((f) => (
                <tr key={f.id} className={f.activo ? "" : "text-muted"}>
                  <td>{f.clave}</td><td>{f.nombre}</td>
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
      {modal && <ModalCatalogo titulo={titulo} ruta={ruta} padre={padre} padres={padres.filter((p) => p.activo)}
        fila={modal === "alta" ? null : modal} onClose={() => setModal(null)}
        onGuardado={() => { setModal(null); cargar(); }} />}
    </>
  );
}

function ModalCatalogo({ titulo, ruta, padre, padres, fila, onClose, onGuardado }: {
  titulo: string; ruta: string; padre?: Padre; padres: Fila[]; fila: Fila | null; onClose: () => void; onGuardado: () => void;
}) {
  const [f, setF] = useState({ clave: fila?.clave ?? "", nombre: fila?.nombre ?? "", padre: padre ? (fila?.[padre.campo] ?? "") : "" });
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
      {padre && <Campo label={padre.label} error={errores[padre.campo]}>
        <select className="form-control" value={f.padre} onChange={(e) => setF({ ...f, padre: e.target.value })}>
          <option value="">— Seleccione —</option>
          {padres.map((p) => <option key={p.id} value={p.id}>{p.clave} — {p.nombre}</option>)}
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
