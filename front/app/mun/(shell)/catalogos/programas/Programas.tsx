"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Campo, mensajeError } from "@/components/Campo";
import { Modal } from "@/components/Modal";
import { toast } from "@/components/Toasts";
import { useTipo } from "@/components/TipoContext";
import { ApiError, api } from "@/lib/api.client";
import { puede } from "@/lib/permisos";

type Cat = { id: string; clave: string; nombre: string; activo: boolean; centro_gestor_id?: string; eje_id?: string; subtema_id?: string };
type Programa = {
  id: string; ejercicio_fiscal: number; clave: string; nombre: string; centro_gestor_id: string; subtema_id: string | null;
  estrategia_id: string | null; clasificacion_programatica_id: string | null; activo: boolean;
};
type Catalogos = { centros: Cat[]; ejes: Cat[]; subtemas: Cat[]; estrategias: Cat[]; clasif: { id: string; clave: string; nombre: string }[] };
const etiqueta = (c: { clave: string; nombre: string }) => `${c.clave} — ${c.nombre}`;

export function Programas() {
  const tipo = useTipo();
  const editable = puede.editarProgramas(tipo);
  const [ejercicio, setEjercicio] = useState(String(new Date().getFullYear()));
  const [centro, setCentro] = useState("");
  const [q, setQ] = useState("");
  const [lista, setLista] = useState<Programa[] | null>(null);
  const [cat, setCat] = useState<Catalogos | null>(null);
  const [modal, setModal] = useState<null | "alta" | Programa>(null);
  const [duplicando, setDuplicando] = useState<Programa | null>(null);

  const cargar = useCallback(async () => {
    const p = new URLSearchParams();
    if (ejercicio) p.set("ejercicio", ejercicio);
    if (centro) p.set("centro_gestor_id", centro);
    setLista(await api(`/api/programas?${p}`));
  }, [ejercicio, centro]);
  useEffect(() => { cargar().catch((e) => toast.error(mensajeError(e))); }, [cargar]);
  useEffect(() => {
    Promise.all([api("/api/centros-gestores"), api("/api/ejes"), api("/api/subtemas"), api("/api/estrategias"),
      api("/api/clasificaciones-programaticas")])
      .then(([centros, ejes, subtemas, estrategias, clasif]) => setCat({ centros, ejes, subtemas, estrategias, clasif }))
      .catch((e) => toast.error(mensajeError(e)));
  }, []);

  const centros = useMemo(() => new Map((cat?.centros ?? []).map((c) => [c.id, etiqueta(c)])), [cat]);
  const filtrada = useMemo(() => (lista ?? []).filter((p) => `${p.clave} ${p.nombre}`.toLowerCase().includes(q.toLowerCase())), [lista, q]);

  async function alternar(p: Programa) {
    try {
      await api(`/api/programas/${p.id}`, { method: "PATCH", json: { activo: !p.activo } });
      toast.success(p.activo ? "Programa deshabilitado" : "Programa habilitado");
      cargar();
    } catch (e) { toast.error(mensajeError(e)); }
  }

  return (
    <>
      <h3 className="page-heading">Programas</h3>
      <div className="panel"><div className="panel-body">
        <div className="toolbar">
          <input type="number" className="form-control" style={{ maxWidth: 110 }} title="Ejercicio fiscal" value={ejercicio} onChange={(e) => setEjercicio(e.target.value)} />
          <select className="form-control" style={{ maxWidth: 300 }} value={centro} onChange={(e) => setCentro(e.target.value)}>
            <option value="">Centro gestor: todos</option>
            {(cat?.centros ?? []).map((c) => <option key={c.id} value={c.id}>{etiqueta(c)}</option>)}
          </select>
          <input className="form-control" style={{ maxWidth: 240 }} placeholder="Buscar" value={q} onChange={(e) => setQ(e.target.value)} />
          <span className="spacer" />
          {editable && <button className="btn btn-success" onClick={() => setModal("alta")}><i className="fa fa-plus" /> Nuevo programa</button>}
        </div>
        <div className="table-responsive">
          <table className="table table-hover">
            <thead><tr><th style={{ width: 110 }}>Clave</th><th>Nombre</th><th>Centro gestor</th><th style={{ width: 90 }}>Ejercicio</th>
              <th style={{ width: 110 }}>Estado</th>{editable && <th style={{ width: 130 }}>Acciones</th>}</tr></thead>
            <tbody>
              {lista === null && <tr><td colSpan={6} className="text-center text-muted">Cargando…</td></tr>}
              {lista && !filtrada.length && <tr><td colSpan={6} className="text-center text-muted">Sin programas</td></tr>}
              {filtrada.map((p) => (
                <tr key={p.id} className={p.activo ? "" : "text-muted"}>
                  <td>{p.clave}</td><td>{p.nombre}</td><td>{centros.get(p.centro_gestor_id) ?? "—"}</td><td>{p.ejercicio_fiscal}</td>
                  <td><span className={`label label-${p.activo ? "success" : "default"}`}>{p.activo ? "Activo" : "Deshabilitado"}</span></td>
                  {editable && <td>
                    <button className="btn btn-xs btn-info" title="Editar" onClick={() => setModal(p)}><i className="fa fa-pencil" /></button>{" "}
                    <button className="btn btn-xs btn-primary" title="Duplicar a otro ejercicio" onClick={() => setDuplicando(p)}><i className="fa fa-files-o" /></button>{" "}
                    <button className={`btn btn-xs ${p.activo ? "btn-warning" : "btn-success"}`} title={p.activo ? "Deshabilitar" : "Habilitar"}
                      onClick={() => alternar(p)}><i className={`fa ${p.activo ? "fa-ban" : "fa-check"}`} /></button>
                  </td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div></div>
      {modal && cat && <ModalPrograma cat={cat} programa={modal === "alta" ? null : modal} ejercicioInicial={ejercicio}
        onClose={() => setModal(null)} onGuardado={() => { setModal(null); cargar(); }} />}
      {duplicando && <ModalDuplicar origen={duplicando} onClose={() => setDuplicando(null)}
        onHecho={() => { setDuplicando(null); cargar(); }} />}
    </>
  );
}

function ModalPrograma({ cat, programa, ejercicioInicial, onClose, onGuardado }: {
  cat: Catalogos; programa: Programa | null; ejercicioInicial: string; onClose: () => void; onGuardado: () => void;
}) {
  const [f, setF] = useState({
    ejercicio_fiscal: String(programa?.ejercicio_fiscal ?? ejercicioInicial), clave: programa?.clave ?? "", nombre: programa?.nombre ?? "",
    centro_gestor_id: programa?.centro_gestor_id ?? "", subtema_id: programa?.subtema_id ?? "", estrategia_id: programa?.estrategia_id ?? "",
    clasificacion_programatica_id: programa?.clasificacion_programatica_id ?? "",
  });
  const [errores, setErrores] = useState<Record<string, string>>({});
  const [ocupado, setOcupado] = useState(false);
  const set = (k: keyof typeof f, v: string) => setF((x) => ({ ...x, [k]: v }));

  // centro gestor -> eje -> subtema -> estrategia: cada selector solo ofrece hijos activos del anterior
  const ejesDelCentro = new Set(cat.ejes.filter((e) => e.centro_gestor_id === f.centro_gestor_id).map((e) => e.id));
  const subtemas = cat.subtemas.filter((s) => s.activo && ejesDelCentro.has(s.eje_id!));
  const estrategias = cat.estrategias.filter((e) => e.activo && e.subtema_id === f.subtema_id);

  async function guardar() {
    setOcupado(true);
    setErrores({});
    const json = {
      ejercicio_fiscal: Number(f.ejercicio_fiscal), clave: f.clave, nombre: f.nombre, centro_gestor_id: f.centro_gestor_id || null,
      subtema_id: f.subtema_id || null, estrategia_id: f.estrategia_id || null,
      clasificacion_programatica_id: f.clasificacion_programatica_id || null,
    };
    try {
      await api(programa ? `/api/programas/${programa.id}` : "/api/programas", { method: programa ? "PATCH" : "POST", json });
      toast.success(programa ? "Cambios guardados" : "Programa creado");
      onGuardado();
    } catch (e) {
      if (e instanceof ApiError) { setErrores(e.campos); toast.error(e.message); } else toast.error("Error de conexión");
      setOcupado(false);
    }
  }

  return (
    <Modal titulo={programa ? "Editar programa" : "Nuevo programa"} size="lg" onClose={onClose} footer={<>
      <button className="btn btn-default" onClick={onClose}>Cancelar</button>
      <button className="btn btn-success" onClick={guardar} disabled={ocupado}>Guardar</button></>}>
      <div className="row">
        <div className="col-sm-3"><Campo label="Ejercicio fiscal" error={errores.ejercicio_fiscal}>
          <input type="number" className="form-control" value={f.ejercicio_fiscal} onChange={(e) => set("ejercicio_fiscal", e.target.value)} /></Campo></div>
        <div className="col-sm-3"><Campo label="Clave" error={errores.clave}>
          <input className="form-control" value={f.clave} onChange={(e) => set("clave", e.target.value)} autoFocus /></Campo></div>
        <div className="col-sm-6"><Campo label="Nombre" error={errores.nombre}>
          <input className="form-control" value={f.nombre} onChange={(e) => set("nombre", e.target.value)} /></Campo></div>
      </div>
      <div className="row">
        <div className="col-sm-6"><Campo label="Centro gestor" error={errores.centro_gestor_id}>
          <select className="form-control" value={f.centro_gestor_id}
            onChange={(e) => setF((x) => ({ ...x, centro_gestor_id: e.target.value, subtema_id: "", estrategia_id: "" }))}>
            <option value="">— Seleccione —</option>
            {cat.centros.filter((c) => c.activo || c.id === programa?.centro_gestor_id).map((c) => <option key={c.id} value={c.id}>{etiqueta(c)}</option>)}
          </select></Campo></div>
        <div className="col-sm-6"><Campo label="Clasificación programática" error={errores.clasificacion_programatica_id}>
          <select className="form-control" value={f.clasificacion_programatica_id} onChange={(e) => set("clasificacion_programatica_id", e.target.value)}>
            <option value="">— Seleccione —</option>
            {cat.clasif.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
          </select></Campo></div>
      </div>
      <div className="row">
        <div className="col-sm-6"><Campo label="Subtema" error={errores.subtema_id}>
          <select className="form-control" value={f.subtema_id} disabled={!f.centro_gestor_id}
            onChange={(e) => setF((x) => ({ ...x, subtema_id: e.target.value, estrategia_id: "" }))}>
            <option value="">— Sin subtema —</option>
            {subtemas.map((s) => <option key={s.id} value={s.id}>{etiqueta(s)}</option>)}
          </select></Campo></div>
        <div className="col-sm-6"><Campo label="Estrategia" error={errores.estrategia_id}>
          <select className="form-control" value={f.estrategia_id} disabled={!f.subtema_id} onChange={(e) => set("estrategia_id", e.target.value)}>
            <option value="">— Sin estrategia —</option>
            {estrategias.map((s) => <option key={s.id} value={s.id}>{etiqueta(s)}</option>)}
          </select></Campo></div>
      </div>
    </Modal>
  );
}

function ModalDuplicar({ origen, onClose, onHecho }: { origen: Programa; onClose: () => void; onHecho: () => void }) {
  const [f, setF] = useState({ ejercicio_fiscal: String(origen.ejercicio_fiscal + 1), clave: "", nombre: origen.nombre });
  const [errores, setErrores] = useState<Record<string, string>>({});

  async function duplicar() {
    setErrores({});
    try {
      await api(`/api/programas/${origen.id}/duplicar`, { method: "POST", json: { ...f, ejercicio_fiscal: Number(f.ejercicio_fiscal) } });
      toast.success(`Programa duplicado al ejercicio ${f.ejercicio_fiscal}`);
      onHecho();
    } catch (e) {
      if (e instanceof ApiError) { setErrores(e.campos); toast.error(e.message); } else toast.error("Error de conexión");
    }
  }

  return (
    <Modal titulo={`Duplicar a otro ejercicio — ${origen.clave}`} onClose={onClose} footer={<>
      <button className="btn btn-default" onClick={onClose}>Cancelar</button>
      <button className="btn btn-success" onClick={duplicar}>Duplicar</button></>}>
      <p className="text-muted">Se copia con clave nueva; el centro gestor, subtema y estrategia se reutilizan. El programa original no cambia.</p>
      <div className="row">
        <div className="col-sm-4"><Campo label="Ejercicio destino" error={errores.ejercicio_fiscal}>
          <input type="number" className="form-control" value={f.ejercicio_fiscal} onChange={(e) => setF({ ...f, ejercicio_fiscal: e.target.value })} /></Campo></div>
        <div className="col-sm-3"><Campo label="Clave nueva" error={errores.clave}>
          <input className="form-control" value={f.clave} onChange={(e) => setF({ ...f, clave: e.target.value })} autoFocus /></Campo></div>
        <div className="col-sm-5"><Campo label="Nombre" error={errores.nombre}>
          <input className="form-control" value={f.nombre} onChange={(e) => setF({ ...f, nombre: e.target.value })} /></Campo></div>
      </div>
    </Modal>
  );
}
