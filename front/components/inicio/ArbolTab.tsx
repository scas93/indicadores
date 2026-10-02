"use client";
import { useCallback, useEffect, useState } from "react";
import { Campo, mensajeError } from "@/components/Campo";
import { Confirmar } from "@/components/Confirmar";
import { Modal } from "@/components/Modal";
import { toast } from "@/components/Toasts";
import { ApiError, api } from "@/lib/api.client";
import type { Arbol, NodoArbol } from "@/lib/mir";

type Lado = "causa" | "efecto";
/** Cada nodo es un par espejo: lado "problema" (causa/efecto) y lado "objetivo" (medio/fin). */
const LADOS = {
  causa: {
    clave: "causas" as const, ca: "texto_causa", ob: "texto_medio", titulo: "Causas y medios",
    nombreA: "Causa", nombreB: "Medio", hijo: "Subcausa",
    crear: (p: string) => `/api/programas/${p}/arbol/causas`, nodo: (id: string) => `/api/arbol-causa-medio/${id}`,
  },
  efecto: {
    clave: "efectos" as const, ca: "texto_efecto", ob: "texto_fin", titulo: "Efectos y fines",
    nombreA: "Efecto", nombreB: "Fin", hijo: "Subefecto",
    crear: (p: string) => `/api/programas/${p}/arbol/efectos`, nodo: (id: string) => `/api/arbol-efecto-fin/${id}`,
  },
};

export function ArbolTab({ programaId }: { programaId: string }) {
  const [arbol, setArbol] = useState<Arbol | null>(null);
  const [enc, setEnc] = useState({ problema: "", objetivo: "" });
  const [modal, setModal] = useState<null | { lado: Lado; nodo: NodoArbol | null; padre: NodoArbol | null }>(null);
  const [baja, setBaja] = useState<null | { lado: Lado; nodo: NodoArbol }>(null);

  const cargar = useCallback(async () => {
    const a = await api<Arbol>(`/api/programas/${programaId}/arbol`);
    setArbol(a);
    setEnc({ problema: a.encabezado.problema ?? "", objetivo: a.encabezado.objetivo ?? "" });
  }, [programaId]);
  useEffect(() => { cargar().catch((e) => toast.error(mensajeError(e))); }, [cargar]);

  async function guardarEncabezado() {
    try {
      await api(`/api/programas/${programaId}/arbol/encabezado`, { method: "PUT", json: enc });
      toast.success("Encabezado guardado");
    } catch (e) { toast.error(mensajeError(e)); }
  }
  async function eliminar() {
    if (!baja) return;
    try {
      await api(LADOS[baja.lado].nodo(baja.nodo.id), { method: "DELETE" });
      toast.success("Eliminado");
      setBaja(null);
      cargar();
    } catch (e) { toast.error(mensajeError(e)); }
  }

  if (!arbol) return <p className="text-muted">Cargando…</p>;
  return (
    <>
      <div className="row arbol-encabezado">
        <div className="col-sm-6"><Campo label="Situación no deseada (problema)">
          <textarea className="form-control" rows={2} value={enc.problema} onChange={(e) => setEnc({ ...enc, problema: e.target.value })} /></Campo></div>
        <div className="col-sm-6"><Campo label="Objetivo">
          <textarea className="form-control" rows={2} value={enc.objetivo} onChange={(e) => setEnc({ ...enc, objetivo: e.target.value })} /></Campo></div>
      </div>
      <div className="toolbar"><button className="btn btn-success btn-sm" onClick={guardarEncabezado}><i className="fa fa-save" /> Guardar encabezado</button></div>
      {(["efecto", "causa"] as Lado[]).map((lado) => (
        <Seccion key={lado} lado={lado} nodos={arbol[LADOS[lado].clave]}
          onAgregar={(padre) => setModal({ lado, nodo: null, padre })}
          onEditar={(nodo) => setModal({ lado, nodo, padre: null })}
          onEliminar={(nodo) => setBaja({ lado, nodo })} />
      ))}
      {modal && <ModalNodo programaId={programaId} {...modal} onClose={() => setModal(null)}
        onGuardado={() => { setModal(null); cargar(); }} />}
      {baja && <Confirmar titulo="Eliminar" boton="Eliminar" onClose={() => setBaja(null)} onConfirmar={eliminar}
        mensaje={baja.nodo.hijos.length
          ? `El nodo ${baja.nodo.numero} tiene ${baja.nodo.hijos.length} subnivel(es): se eliminarán junto con él (y con sus pares espejo). ¿Continuar?`
          : `¿Eliminar el nodo ${baja.nodo.numero} y su par espejo?`} />}
    </>
  );
}

function Seccion({ lado, nodos, onAgregar, onEditar, onEliminar }: {
  lado: Lado; nodos: NodoArbol[]; onAgregar: (padre: NodoArbol | null) => void;
  onEditar: (n: NodoArbol) => void; onEliminar: (n: NodoArbol) => void;
}) {
  const L = LADOS[lado];
  const fila = (n: NodoArbol, hijo: boolean) => (
    <tr key={n.id} className={hijo ? "nodo-hijo" : "nodo-raiz"}>
      <td style={{ width: 70 }}>{n.numero}</td>
      <td className="texto">{n[L.ca]}</td>
      <td className="texto">{n[L.ob]}</td>
      <td style={{ width: 130 }}>
        {!hijo && <><button className="btn btn-xs btn-success" title={`Agregar ${L.hijo.toLowerCase()}`} onClick={() => onAgregar(n)}><i className="fa fa-plus" /></button>{" "}</>}
        <button className="btn btn-xs btn-info" title="Editar" onClick={() => onEditar(n)}><i className="fa fa-pencil" /></button>{" "}
        <button className="btn btn-xs btn-danger" title="Eliminar" onClick={() => onEliminar(n)}><i className="fa fa-trash" /></button>
      </td>
    </tr>
  );
  return (
    <>
      <div className="toolbar" style={{ marginTop: 20 }}>
        <h4 style={{ margin: 0 }}>{L.titulo}</h4><span className="spacer" style={{ flex: 1 }} />
        <button className="btn btn-success btn-sm" onClick={() => onAgregar(null)}><i className="fa fa-plus" /> Agregar {L.nombreA.toLowerCase()}</button>
      </div>
      <div className="table-responsive">
        <table className="table table-hover arbol-tabla">
          <thead><tr><th>No.</th><th>{L.nombreA}</th><th>{L.nombreB}</th><th>Acciones</th></tr></thead>
          <tbody>
            {!nodos.length && <tr><td colSpan={4} className="text-center text-muted">Sin registros</td></tr>}
            {nodos.map((n) => [fila(n, false), ...n.hijos.map((h) => fila(h, true))])}
          </tbody>
        </table>
      </div>
    </>
  );
}

function ModalNodo({ programaId, lado, nodo, padre, onClose, onGuardado }: {
  programaId: string; lado: Lado; nodo: NodoArbol | null; padre: NodoArbol | null; onClose: () => void; onGuardado: () => void;
}) {
  const L = LADOS[lado];
  const [f, setF] = useState({ a: nodo?.[L.ca] ?? "", b: nodo?.[L.ob] ?? "" });
  const [errores, setErrores] = useState<Record<string, string>>({});

  async function guardar() {
    setErrores({});
    const json = { [L.ca]: f.a, [L.ob]: f.b, ...(padre ? { padre_id: padre.id } : {}) };
    try {
      await api(nodo ? L.nodo(nodo.id) : L.crear(programaId), { method: nodo ? "PATCH" : "POST", json });
      toast.success(nodo ? "Cambios guardados" : "Agregado");
      onGuardado();
    } catch (e) {
      if (e instanceof ApiError) { setErrores(e.campos); toast.error(e.message); } else toast.error("Error de conexión");
    }
  }
  const titulo = nodo ? `Editar ${L.nombreA.toLowerCase()} ${nodo.numero} / ${L.nombreB.toLowerCase()}`
    : padre ? `Agregar ${L.hijo.toLowerCase()} a ${padre.numero}` : `Agregar ${L.nombreA.toLowerCase()}`;
  return (
    <Modal titulo={titulo} onClose={onClose} footer={<>
      <button className="btn btn-default" onClick={onClose}>Cancelar</button>
      <button className="btn btn-success" onClick={guardar}>Guardar</button></>}>
      <p className="text-muted">El {L.nombreB.toLowerCase()} es el par espejo: se guarda junto con su {L.nombreA.toLowerCase()} y comparte numeración.</p>
      <Campo label={L.nombreA} error={errores[L.ca]}>
        <textarea className="form-control" rows={3} autoFocus value={f.a} onChange={(e) => setF({ ...f, a: e.target.value })} /></Campo>
      <Campo label={L.nombreB} error={errores[L.ob]}>
        <textarea className="form-control" rows={3} value={f.b} onChange={(e) => setF({ ...f, b: e.target.value })} /></Campo>
    </Modal>
  );
}
