"use client";
import { useCallback, useEffect, useState } from "react";
import { Campo, mensajeError } from "@/components/Campo";
import { Confirmar } from "@/components/Confirmar";
import { Modal } from "@/components/Modal";
import { toast } from "@/components/Toasts";
import { ApiError, api } from "@/lib/api.client";
import { NIVEL_NOMBRE, type Elemento, type Indicador, type Matriz } from "@/lib/mir";
import { IndicadorModal } from "./IndicadorModal";

type Fila = Elemento & { nivelVisual: string };

export function MatrizTab({ programaId }: { programaId: string }) {
  const [matriz, setMatriz] = useState<Matriz | null>(null);
  const [indicador, setIndicador] = useState<null | { elemento: Elemento; indicador: Indicador | null }>(null);
  const [fila, setFila] = useState<null | { modo: "editar"; e: Elemento } | { modo: "componente" } | { modo: "actividad"; padre: Elemento }>(null);
  const [baja, setBaja] = useState<Elemento | null>(null);

  const cargar = useCallback(async () => setMatriz(await api<Matriz>(`/api/programas/${programaId}/matriz`)), [programaId]);
  useEffect(() => { cargar().catch((e) => toast.error(mensajeError(e))); }, [cargar]);

  async function eliminar() {
    if (!baja) return;
    try {
      await api(`/api/elementos-matriz/${baja.id}`, { method: "DELETE" });
      toast.success("Eliminado");
      setBaja(null);
      cargar();
    } catch (e) { toast.error(mensajeError(e)); }
  }

  if (!matriz) return <p className="text-muted">Cargando…</p>;
  const filas: Fila[] = [{ ...matriz.fin, nivelVisual: "fin" }, { ...matriz.proposito, nivelVisual: "proposito" }];
  for (const c of matriz.componentes) {
    filas.push({ ...c, nivelVisual: "componente" });
    for (const a of c.actividades ?? []) filas.push({ ...a, nivelVisual: "actividad" });
  }
  const etiqueta = (e: Elemento) => `${NIVEL_NOMBRE[e.nivel]}${e.numero ? ` ${e.numero}` : ""}`;

  return (
    <>
      <div className="toolbar">
        <span className="text-muted">{matriz.programa.clave} — {matriz.programa.nombre}</span><span className="spacer" style={{ flex: 1 }} />
        <button className="btn btn-success" onClick={() => setFila({ modo: "componente" })}><i className="fa fa-plus" /> Agregar componente</button>
      </div>
      <div className="table-responsive">
        <table className="table matriz-tabla">
          <thead><tr><th style={{ width: 140 }}>Tipo</th><th>Resumen narrativo</th><th>Indicador</th>
            <th>Medios de verificación</th><th>Supuestos</th><th style={{ width: 150 }}>Acciones</th></tr></thead>
          <tbody>
            {filas.map((e) => (
              <tr key={e.id} className={`nivel-${e.nivel}`}>
                <td><strong>{etiqueta(e)}</strong></td>
                <td>{e.resumen_narrativo}</td>
                <td>
                  {e.indicadores.map((i) => (
                    <div key={i.id}>
                      <a href="#" onClick={(ev) => { ev.preventDefault(); setIndicador({ elemento: e, indicador: i }); }}>
                        <i className="fa fa-pencil" /> {i.ficha.nombre || "(sin nombre)"}</a>
                    </div>
                  ))}
                  {!e.indicadores.length && <span className="text-muted">—</span>}
                </td>
                <td>{e.medios_verificacion}</td>
                <td>{e.supuestos}</td>
                <td>
                  <button className="btn btn-xs btn-success" title="Agregar indicador" onClick={() => setIndicador({ elemento: e, indicador: null })}><i className="fa fa-line-chart" /></button>{" "}
                  <button className="btn btn-xs btn-info" title="Editar fila" onClick={() => setFila({ modo: "editar", e })}><i className="fa fa-pencil" /></button>{" "}
                  {e.nivel === "componente" && <><button className="btn btn-xs btn-primary" title="Agregar actividad" onClick={() => setFila({ modo: "actividad", padre: e })}><i className="fa fa-plus" /></button>{" "}</>}
                  {(e.nivel === "componente" || e.nivel === "actividad") &&
                    <button className="btn btn-xs btn-danger" title="Eliminar" onClick={() => setBaja(e)}><i className="fa fa-trash" /></button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {indicador && <IndicadorModal programa={matriz.programa} elemento={indicador.elemento} indicador={indicador.indicador}
        onClose={() => setIndicador(null)} onGuardado={() => { setIndicador(null); cargar(); }} />}
      {fila && <ModalFila programaId={programaId} accion={fila} onClose={() => setFila(null)}
        onGuardado={() => { setFila(null); cargar(); }} />}
      {baja && <Confirmar titulo="Eliminar" onClose={() => setBaja(null)} onConfirmar={eliminar}
        mensaje={baja.nivel === "componente"
          ? `Se eliminará el componente ${baja.numero} con sus actividades e indicadores (incluidas sus metas y avances capturados). Esta acción no se puede deshacer. ¿Continuar?`
          : `Se eliminará la actividad ${baja.numero} con sus indicadores (incluidas sus metas y avances capturados). ¿Continuar?`} />}
    </>
  );
}

function ModalFila({ programaId, accion, onClose, onGuardado }: {
  programaId: string; accion: { modo: "editar"; e: Elemento } | { modo: "componente" } | { modo: "actividad"; padre: Elemento };
  onClose: () => void; onGuardado: () => void;
}) {
  const e = accion.modo === "editar" ? accion.e : null;
  const [f, setF] = useState({ resumen_narrativo: e?.resumen_narrativo ?? "", medios_verificacion: e?.medios_verificacion ?? "",
    supuestos: e?.supuestos ?? "", evidencia: e?.evidencia ?? "" });
  const [errores, setErrores] = useState<Record<string, string>>({});
  async function guardar() {
    try {
      if (accion.modo === "editar") await api(`/api/elementos-matriz/${accion.e.id}`, { method: "PATCH", json: f });
      else if (accion.modo === "componente") await api(`/api/programas/${programaId}/matriz/componentes`, { method: "POST", json: f });
      else await api(`/api/elementos-matriz/${accion.padre.id}/actividades`, { method: "POST", json: f });
      toast.success("Guardado");
      onGuardado();
    } catch (er) {
      if (er instanceof ApiError) { setErrores(er.campos); toast.error(er.message); } else toast.error("Error de conexión");
    }
  }
  const titulo = accion.modo === "editar" ? `Editar ${NIVEL_NOMBRE[accion.e.nivel].toLowerCase()} ${accion.e.numero}`.trim()
    : accion.modo === "componente" ? "Agregar componente" : `Agregar actividad al componente ${accion.padre.numero}`;
  return (
    <Modal titulo={titulo} size="lg" onClose={onClose} footer={<>
      <button className="btn btn-default" onClick={onClose}>Cancelar</button>
      <button className="btn btn-success" onClick={guardar}>Guardar</button></>}>
      {(["resumen_narrativo", "medios_verificacion", "supuestos", "evidencia"] as const).map((k) => (
        <Campo key={k} label={{ resumen_narrativo: "Resumen narrativo", medios_verificacion: "Medios de verificación", supuestos: "Supuestos", evidencia: "Evidencia" }[k]} error={errores[k]}>
          <textarea className="form-control" rows={3} value={f[k]} onChange={(ev) => setF({ ...f, [k]: ev.target.value })} /></Campo>
      ))}
    </Modal>
  );
}
