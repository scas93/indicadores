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
    clave: "causas" as const, ca: "texto_causa", ob: "texto_medio", titulo: "Causas y medios", panelA: "Causas", panelB: "Medios",
    nombreA: "Causa", nombreB: "Medio", hijo: "Subcausa",
    crear: (p: string) => `/api/programas/${p}/arbol/causas`, nodo: (id: string) => `/api/arbol-causa-medio/${id}`,
  },
  efecto: {
    clave: "efectos" as const, ca: "texto_efecto", ob: "texto_fin", titulo: "Efectos y fines", panelA: "Efectos", panelB: "Fines",
    nombreA: "Efecto", nombreB: "Fin", hijo: "Subefecto",
    crear: (p: string) => `/api/programas/${p}/arbol/efectos`, nodo: (id: string) => `/api/arbol-efecto-fin/${id}`,
  },
};

export function ArbolTab({ programaId }: { programaId: string }) {
  const [arbol, setArbol] = useState<Arbol | null>(null);
  const [enc, setEnc] = useState({ problema: "", objetivo: "" });
  const [modal, setModal] = useState<null | { lado: Lado; nodo: NodoArbol | null; padre: NodoArbol | null; solo?: "a" | "b" }>(null);
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
      {/* Situación no deseada y Objetivo: uno bajo otro, ancho completo, un solo Guardar centrado */}
      <div className="arbol-bloque">
        <div className="barra-verde">Situación no deseada</div>
        <textarea className="form-control" rows={3} aria-label="Situación no deseada" value={enc.problema}
          onChange={(e) => setEnc({ ...enc, problema: e.target.value })} />
      </div>
      <div className="arbol-bloque">
        <div className="barra-verde">Objetivo</div>
        <textarea className="form-control" rows={3} aria-label="Objetivo" value={enc.objetivo}
          onChange={(e) => setEnc({ ...enc, objetivo: e.target.value })} />
      </div>
      <div className="text-center" style={{ margin: "14px 0 22px" }}>
        <button className="btn btn-success" onClick={guardarEncabezado}><i className="fa fa-save" /> Guardar</button>
      </div>

      {/* Cuadrícula 2×2: Causas | Medios arriba, Efectos | Fines abajo; cada fila de Medios/Fines queda a la altura de su causa/efecto */}
      {(["causa", "efecto"] as Lado[]).map((lado) => (
        <Par key={lado} lado={lado} nodos={arbol[LADOS[lado].clave]}
          onAgregar={(padre) => setModal({ lado, nodo: null, padre })}
          onEditar={(nodo, solo) => setModal({ lado, nodo, padre: null, solo })}
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

/** Dos paneles lado a lado (problema | objetivo) construidos como una sola cuadrícula para que cada
 *  fila de Medios/Fines quede alineada con su causa/efecto. Solo el lado problema agrega y borra. */
function Par({ lado, nodos, onAgregar, onEditar, onEliminar }: {
  lado: Lado; nodos: NodoArbol[]; onAgregar: (padre: NodoArbol | null) => void;
  onEditar: (n: NodoArbol, solo: "a" | "b") => void; onEliminar: (n: NodoArbol) => void;
}) {
  const L = LADOS[lado];
  const filas: { n: NodoArbol; hijo: boolean }[] = nodos.flatMap((n) => [{ n, hijo: false }, ...n.hijos.map((h) => ({ n: h, hijo: true }))]);
  const Nodo = ({ n, hijo }: { n: NodoArbol; hijo: boolean }) => (
    <div className={`arbol-nodo ${hijo ? "hijo" : "padre"}`}>
      <i className={hijo ? "fa fa-file-text-o icono-hijo" : "fa fa-th-large icono-padre"} /> {n.numero}
    </div>
  );
  const Texto = ({ n, lado: l }: { n: NodoArbol; lado: "a" | "b" }) => (
    <div className="arbol-texto">
      <button className="btn btn-xs btn-success" title="Editar" onClick={() => onEditar(n, l)}><i className="fa fa-pencil" /></button>
      <span>{n[l === "a" ? L.ca : L.ob]}</span>
    </div>
  );
  return (
    <div className="arbol-par">
      <div className="barra-verde arbol-celda-a">{L.panelA}</div><div className="arbol-sep" /><div className="barra-verde arbol-celda-b">{L.panelB}</div>
      <div className="arbol-cab arbol-celda-a">
        <div className="acciones"><button className="btn btn-xs btn-default" title={`Agregar ${L.nombreA.toLowerCase()}`} onClick={() => onAgregar(null)}><i className="fa fa-plus" /></button></div>
        <div>Nodo</div><div>{L.nombreA}</div>
      </div>
      <div className="arbol-sep" />
      <div className="arbol-cab arbol-celda-b"><div className="acciones" /><div>Nodo</div><div>{L.nombreB}</div></div>
      {!filas.length && <><div className="arbol-vacio arbol-celda-a">Sin registros</div><div className="arbol-sep" /><div className="arbol-vacio arbol-celda-b">Sin registros</div></>}
      {filas.map(({ n, hijo }) => (
        <div key={n.id} className="arbol-fila">
          <div className="arbol-celda-a arbol-reg">
            <div className="acciones">
              <button className="btn btn-xs btn-danger" title="Eliminar" onClick={() => onEliminar(n)}><i className="fa fa-trash" /></button>
              {!hijo && <button className="btn btn-xs btn-success" title={`Agregar ${L.hijo.toLowerCase()}`} onClick={() => onAgregar(n)}><i className="fa fa-plus" /></button>}
            </div>
            <Nodo n={n} hijo={hijo} /><Texto n={n} lado="a" />
          </div>
          <div className="arbol-sep" />
          <div className="arbol-celda-b arbol-reg">
            <div className="acciones" /><Nodo n={n} hijo={hijo} /><Texto n={n} lado="b" />
          </div>
        </div>
      ))}
    </div>
  );
}

function ModalNodo({ programaId, lado, nodo, padre, solo, onClose, onGuardado }: {
  programaId: string; lado: Lado; nodo: NodoArbol | null; padre: NodoArbol | null; solo?: "a" | "b"; onClose: () => void; onGuardado: () => void;
}) {
  const L = LADOS[lado];
  const [f, setF] = useState({ a: nodo?.[L.ca] ?? "", b: nodo?.[L.ob] ?? "" });
  const [errores, setErrores] = useState<Record<string, string>>({});

  async function guardar() {
    setErrores({});
    const json = { ...(solo !== "b" ? { [L.ca]: f.a } : {}), ...(solo !== "a" ? { [L.ob]: f.b } : {}), ...(padre ? { padre_id: padre.id } : {}) };
    try {
      await api(nodo ? L.nodo(nodo.id) : L.crear(programaId), { method: nodo ? "PATCH" : "POST", json });
      toast.success(nodo ? "Cambios guardados" : "Agregado");
      onGuardado();
    } catch (e) {
      if (e instanceof ApiError) { setErrores(e.campos); toast.error(e.message); } else toast.error("Error de conexión");
    }
  }
  const titulo = nodo ? `Editar ${solo ? (solo === "a" ? L.nombreA : L.nombreB).toLowerCase() : `${L.nombreA.toLowerCase()} / ${L.nombreB.toLowerCase()}`} ${nodo.numero}`
    : padre ? `Agregar ${L.hijo.toLowerCase()} a ${padre.numero}` : `Agregar ${L.nombreA.toLowerCase()}`;
  return (
    <Modal titulo={titulo} onClose={onClose} footer={<>
      <button className="btn btn-default" onClick={onClose}>Cancelar</button>
      <button className="btn btn-success" onClick={guardar}>Guardar</button></>}>
      {!solo && <p className="text-muted">El {L.nombreB.toLowerCase()} es el par espejo: se guarda junto con su {L.nombreA.toLowerCase()} y comparte numeración.</p>}
      {solo !== "b" && <Campo label={L.nombreA} error={errores[L.ca]}>
        <textarea className="form-control" rows={3} autoFocus value={f.a} onChange={(e) => setF({ ...f, a: e.target.value })} /></Campo>}
      {solo !== "a" && <Campo label={L.nombreB} error={errores[L.ob]}>
        <textarea className="form-control" rows={3} autoFocus={solo === "b"} value={f.b} onChange={(e) => setF({ ...f, b: e.target.value })} /></Campo>}
    </Modal>
  );
}
