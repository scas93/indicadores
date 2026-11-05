"use client";
import { useCallback, useEffect, useState } from "react";
import { Campo, mensajeError } from "../Campo";
import { Confirmar } from "../Confirmar";
import { Modal } from "../Modal";
import { toast } from "../Toasts";
import { ApiError, api } from "@/lib/api.client";

export type DocumentoBen = { id: string; beneficiario_id: string; tipo: string; titulo: string; observaciones: string | null;
  nombre_archivo: string; tamano: number; fecha_alta: string };

export const TIPOS_DOCUMENTO = [
  { valor: "ine", titulo: "INE/IFE" }, { valor: "curp", titulo: "CURP" },
  { valor: "comprobante_domicilio", titulo: "COMPROBANTE DE DOMICILIO" }];
const MAX_MB = 5;  // el servidor lo vuelve a validar; aquí solo se evita mandar un archivo que de todos modos se rechaza

const url = (d: DocumentoBen) => `/api/beneficiarios/${d.beneficiario_id}/documentos/${d.id}/archivo`;

/** Lista de documentos con Ver (abre en otra pestaña) y Descargar; con `onBorrar` agrega el botón de borrar.
 *  El archivo siempre se pide a la API con la sesión: no hay enlace público. */
export function ListaDocumentos({ docs, onBorrar }: { docs: DocumentoBen[]; onBorrar?: (d: DocumentoBen) => void }) {
  return (
    <div className="table-responsive">
      <table className="table table-bordered table-hover">
        <thead><tr><th>Tipo</th><th>Título</th><th>Observaciones</th><th>Fecha de alta</th><th style={{ width: 110 }}>Archivo</th></tr></thead>
        <tbody>
          {!docs.length && <tr><td colSpan={5} className="text-center text-muted">Sin documentos</td></tr>}
          {docs.map((d) => (
            <tr key={d.id}>
              <td>{d.tipo === "ine" ? "INE/IFE" : d.tipo === "curp" ? "CURP" : "COMPROBANTE DE DOMICILIO"}</td>
              <td>{d.titulo}</td><td>{d.observaciones}</td><td>{d.fecha_alta}</td>
              <td>
                <a className="btn btn-xs btn-info" title="Ver" href={url(d)} target="_blank" rel="noopener noreferrer"><i className="fa fa-eye" /></a>{" "}
                <a className="btn btn-xs btn-default" title="Descargar" href={`${url(d)}?descargar=true`}><i className="fa fa-download" /></a>
                {onBorrar && <>{" "}<button className="btn btn-xs btn-danger" title="Borrar" onClick={() => onBorrar(d)}><i className="fa fa-trash" /></button></>}
              </td>
            </tr>))}
        </tbody>
      </table>
    </div>
  );
}

/** "Alta y Visualización de Documentos" de un beneficiario (Catálogos → Beneficiarios, botón morado). */
export function ModalDocumentos({ beneficiario, onClose }: { beneficiario: { id: string; curp: string; nombre: string }; onClose: () => void }) {
  const [docs, setDocs] = useState<DocumentoBen[] | null>(null);
  const [tipo, setTipo] = useState("");
  const [obs, setObs] = useState("");
  const [archivo, setArchivo] = useState<File | null>(null);
  const [claveInput, setClaveInput] = useState(0);  // reinicia el selector de archivo después de guardar
  const [errores, setErrores] = useState<Record<string, string>>({});
  const [ocupado, setOcupado] = useState(false);
  const [borrar, setBorrar] = useState<DocumentoBen | null>(null);
  const base = `/api/beneficiarios/${beneficiario.id}/documentos`;

  const cargar = useCallback(() => api<DocumentoBen[]>(base).then(setDocs).catch((e) => toast.error(mensajeError(e))), [base]);
  useEffect(() => { cargar(); }, [cargar]);

  const titulo = TIPOS_DOCUMENTO.find((t) => t.valor === tipo)?.titulo ?? "";

  function elegir(f: File | null) {
    setErrores({});
    if (f && f.size > MAX_MB * 1024 * 1024) { setErrores({ archivo: `El archivo excede el máximo de ${MAX_MB} MB` }); setArchivo(null); setClaveInput((k) => k + 1); return; }
    setArchivo(f);
  }

  async function guardar() {
    const e: Record<string, string> = {};
    if (!tipo) e.tipo = "Seleccione el tipo de documento";
    if (!archivo) e.archivo = "Seleccione un archivo";
    setErrores(e);
    if (Object.keys(e).length || !archivo) return;
    setOcupado(true);
    try {
      const fd = new FormData();
      fd.append("tipo", tipo); fd.append("observaciones", obs); fd.append("archivo", archivo);
      const res = await fetch(base, { method: "POST", body: fd });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new ApiError(res.status, data?.codigo ?? "ERROR", data?.mensaje ?? "No se pudo subir el archivo", data?.campos ?? {});
      toast.success("Documento guardado");
      setTipo(""); setObs(""); setArchivo(null); setClaveInput((k) => k + 1);
      await cargar();
    } catch (err) {
      if (err instanceof ApiError) { setErrores(err.campos); toast.error(err.message); } else toast.error("Error de conexión");
    } finally { setOcupado(false); }
  }

  async function eliminar() {
    if (!borrar) return;
    setOcupado(true);
    try { await api(`${base}/${borrar.id}`, { method: "DELETE" }); toast.success("Documento eliminado"); setBorrar(null); await cargar(); }
    catch (err) { toast.error(mensajeError(err)); setBorrar(null); } finally { setOcupado(false); }
  }

  return (
    <>
      <Modal titulo="Alta y Visualización de Documentos" size="lg" onClose={onClose}
        footer={<button className="btn btn-default" onClick={onClose}>Cerrar</button>}>
        <p className="text-muted">{beneficiario.curp} — {beneficiario.nombre}</p>
        <Campo label="Tipo Documento" error={errores.tipo}>
          <select className="form-control" value={tipo} onChange={(e) => setTipo(e.target.value)}>
            <option value="">— Seleccione —</option>
            {TIPOS_DOCUMENTO.map((t) => <option key={t.valor} value={t.valor}>{t.titulo}</option>)}
          </select>
        </Campo>
        <Campo label="Título"><input className="form-control" value={titulo} readOnly /></Campo>
        <Campo label="Observaciones" error={errores.observaciones}>
          <textarea className="form-control" rows={2} value={obs} onChange={(e) => setObs(e.target.value)} /></Campo>
        <Campo label="Adjunto" error={errores.archivo}>
          <input key={claveInput} type="file" className="form-control" accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
            onChange={(e) => elegir(e.target.files?.[0] ?? null)} />
          <span className="help-block">PDF, JPG o PNG, máximo {MAX_MB} MB.</span>
        </Campo>
        <button className="btn btn-success" disabled={ocupado} onClick={guardar}>{ocupado ? "Guardando…" : "Guardar"}</button>
        <h4 style={{ marginTop: 24 }}>Documentos del Beneficiario</h4>
        {docs ? <ListaDocumentos docs={docs} onBorrar={setBorrar} /> : <p className="text-muted">Cargando…</p>}
      </Modal>
      {borrar && <Confirmar titulo="Eliminar documento" boton={ocupado ? "Eliminando…" : "Eliminar"} onClose={() => setBorrar(null)} onConfirmar={eliminar}
        mensaje={`¿Eliminar el documento "${borrar.titulo}"? También se borra el archivo.`} />}
    </>
  );
}
