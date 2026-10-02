"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Campo, mensajeError } from "../Campo";
import { Modal } from "../Modal";
import { toast } from "../Toasts";
import { ApiError, api } from "@/lib/api.client";
import { MESES, TIPOS, nombreTipo } from "@/lib/permisos";

export type Usuario = {
  id: string; usuario: string; nombre: string; tipo: string; activo: boolean; debe_cambiar_password: boolean;
  direccion: string | null; telefono: string | null; email: string | null; anios_acceso: number[]; meses_acceso: number[];
  ultimo_acceso: string | null; programa_ids?: string[];
};

const fechaHora = (s: string | null) => s ? new Date(s).toLocaleString("es-MX", { dateStyle: "short", timeStyle: "short" }) : "Nunca";

/** Listado de usuarios. `base` es `/api/usuarios` (municipio) o `/api/admin/municipios/{id}/usuarios`
 *  (super admin): misma pantalla, misma lógica de negocio en la API. `gestion` = puede crear/editar/ver
 *  contraseñas; los demás tipos con el módulo solo consultan. `conProgramas` = selector de programas. */
export function UsuariosAdmin({ base, gestion, conProgramas, enlaces }: {
  base: string; gestion: boolean; conProgramas: boolean; enlaces?: boolean;
}) {
  const [lista, setLista] = useState<Usuario[] | null>(null);
  const [q, setQ] = useState("");
  const [tipo, setTipo] = useState("");
  const [activo, setActivo] = useState("");
  const [modal, setModal] = useState<null | "alta" | Usuario>(null);
  const [claves, setClaves] = useState<Record<string, string>>({}); // contraseñas reveladas (por id)
  const [forzar, setForzar] = useState<Usuario | null>(null);
  const [resultado, setResultado] = useState<{ titulo: string; usuario: string; password: string } | null>(null);

  const cargar = useCallback(async () => {
    const p = new URLSearchParams();
    if (tipo) p.set("tipo", tipo);
    if (activo) p.set("activo", activo);
    if (q.trim()) p.set("q", q.trim());
    setLista(await api(`${base}?${p}`));
  }, [base, tipo, activo, q]);
  useEffect(() => {
    const t = setTimeout(() => cargar().catch((e) => toast.error(mensajeError(e))), 250);
    return () => clearTimeout(t);
  }, [cargar]);

  async function verPassword(u: Usuario) {
    if (claves[u.id] !== undefined) { // ocultar
      setClaves(({ [u.id]: _, ...resto }) => resto);
      return;
    }
    try { // cada consulta queda en bitácora
      const d = await api<{ password: string }>(`${base}/${u.id}`);
      setClaves((c) => ({ ...c, [u.id]: d.password }));
    } catch (e) { toast.error(mensajeError(e)); }
  }

  async function alternar(u: Usuario) {
    try {
      await api(`${base}/${u.id}`, { method: "PATCH", json: { activo: !u.activo } });
      toast.success(u.activo ? "Usuario deshabilitado" : "Usuario habilitado");
      cargar();
    } catch (e) { toast.error(mensajeError(e)); }
  }

  async function confirmarForzar(u: Usuario) {
    try {
      const r = await api<{ password: string }>(`${base}/${u.id}/forzar-password`, { method: "POST" });
      setForzar(null);
      setClaves(({ [u.id]: _, ...resto }) => resto);
      setResultado({ titulo: "Contraseña nueva", usuario: u.usuario, password: r.password });
    } catch (e) { toast.error(mensajeError(e)); }
  }

  const cols = gestion ? 7 : 5;
  return (
    <>
      <h3 className="page-heading">Usuarios</h3>
      <div className="panel"><div className="panel-body">
        <div className="toolbar">
          <input className="form-control" style={{ maxWidth: 240 }} placeholder="Buscar por nombre o usuario" value={q} onChange={(e) => setQ(e.target.value)} />
          <select className="form-control" style={{ maxWidth: 220 }} value={tipo} onChange={(e) => setTipo(e.target.value)}>
            <option value="">Tipo: todos</option>
            {TIPOS.map((t) => <option key={t.valor} value={t.valor}>{t.nombre}</option>)}
          </select>
          <select className="form-control" style={{ maxWidth: 160 }} value={activo} onChange={(e) => setActivo(e.target.value)}>
            <option value="">Estado: todos</option><option value="true">Activos</option><option value="false">Deshabilitados</option>
          </select>
          <span className="spacer" />
          {gestion && enlaces && <>
            <a className="btn btn-info" href="/catalogos/usuarios/matriz"><i className="fa fa-th" /> Matriz de programas</a>
            <a className="btn btn-primary" href="/catalogos/usuarios/masivo"><i className="fa fa-users" /> Alta masiva</a></>}
          {gestion && <button className="btn btn-success" onClick={() => setModal("alta")}><i className="fa fa-plus" /> Nuevo usuario</button>}
        </div>
        <div className="table-responsive">
          <table className="table table-hover">
            <thead><tr><th>Nombre</th><th>Usuario</th><th>Tipo</th>{gestion && <th>Contraseña</th>}<th style={{ width: 100 }}>Estado</th>
              <th style={{ width: 150 }}>Último acceso</th>{gestion && <th style={{ width: 130 }}>Acciones</th>}</tr></thead>
            <tbody>
              {lista === null && <tr><td colSpan={cols} className="text-center text-muted">Cargando…</td></tr>}
              {lista && !lista.length && <tr><td colSpan={cols} className="text-center text-muted">Sin usuarios</td></tr>}
              {(lista ?? []).map((u) => (
                <tr key={u.id} className={u.activo ? "" : "text-muted"}>
                  <td>{u.nombre}</td><td>{u.usuario}</td><td>{nombreTipo(u.tipo)}</td>
                  {gestion && <td>
                    <button className="btn btn-xs btn-default" title={claves[u.id] === undefined ? "Ver contraseña" : "Ocultar"} onClick={() => verPassword(u)}>
                      <i className={`fa ${claves[u.id] === undefined ? "fa-eye" : "fa-eye-slash"}`} /></button>{" "}
                    {claves[u.id] === undefined ? <span className="text-muted">••••••••</span> : <code>{claves[u.id]}</code>}
                  </td>}
                  <td><span className={`label label-${u.activo ? "success" : "default"}`}>{u.activo ? "Activo" : "Deshabilitado"}</span></td>
                  <td>{fechaHora(u.ultimo_acceso)}</td>
                  {gestion && <td>
                    <button className="btn btn-xs btn-info" title="Editar" onClick={() => setModal(u)}><i className="fa fa-pencil" /></button>{" "}
                    <button className="btn btn-xs btn-primary" title="Forzar contraseña nueva" onClick={() => setForzar(u)}><i className="fa fa-key" /></button>{" "}
                    <button className={`btn btn-xs ${u.activo ? "btn-warning" : "btn-success"}`} title={u.activo ? "Deshabilitar" : "Habilitar"}
                      onClick={() => alternar(u)}><i className={`fa ${u.activo ? "fa-ban" : "fa-check"}`} /></button>
                  </td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div></div>

      {modal && <ModalUsuario base={base} conProgramas={conProgramas} usuario={modal === "alta" ? null : modal}
        onClose={() => setModal(null)}
        onGuardado={(generada, u) => {
          setModal(null);
          setClaves({});
          cargar();
          if (generada) setResultado({ titulo: "Usuario creado", usuario: u.usuario, password: generada });
        }} />}

      {forzar && <Modal titulo="Forzar contraseña nueva" onClose={() => setForzar(null)} footer={<>
        <button className="btn btn-default" onClick={() => setForzar(null)}>Cancelar</button>
        <button className="btn btn-primary" onClick={() => confirmarForzar(forzar)}>Generar contraseña</button></>}>
        <p>Se generará una contraseña nueva para <strong>{forzar.nombre}</strong> y se cerrarán sus sesiones abiertas.</p>
      </Modal>}

      {resultado && <Modal titulo={resultado.titulo} onClose={() => setResultado(null)}
        footer={<button className="btn btn-success" onClick={() => setResultado(null)}>Listo</button>}>
        <table className="table table-condensed" style={{ marginBottom: 0 }}><tbody>
          <tr><th>Usuario</th><td>{resultado.usuario}</td></tr>
          <tr><th>Contraseña</th><td><code>{resultado.password}</code></td></tr>
        </tbody></table>
        <p className="help-block">Cópiala ahora: es la única vez que se muestra automáticamente (después puedes consultarla desde el listado).</p>
      </Modal>}
    </>
  );
}

type Prog = { id: string; clave: string; nombre: string; centro_gestor_id: string };

function ModalUsuario({ base, conProgramas, usuario, onClose, onGuardado }: {
  base: string; conProgramas: boolean; usuario: Usuario | null; onClose: () => void;
  onGuardado: (passwordGenerada: string | null, u: Usuario) => void;
}) {
  const anioActual = new Date().getFullYear();
  const [f, setF] = useState({
    nombre: usuario?.nombre ?? "", usuario: usuario?.usuario ?? "", password: "", tipo: usuario?.tipo ?? "informes",
    direccion: usuario?.direccion ?? "", telefono: usuario?.telefono ?? "", email: usuario?.email ?? "",
    anios_acceso: usuario?.anios_acceso ?? [anioActual], meses_acceso: usuario?.meses_acceso ?? [], activo: usuario?.activo ?? true,
  });
  const [errores, setErrores] = useState<Record<string, string>>({});
  const [ocupado, setOcupado] = useState(false);
  const [seleccion, setSeleccion] = useState<Set<string>>(new Set(usuario?.programa_ids ?? []));
  const [ejercicio, setEjercicio] = useState(String(anioActual));
  const [progs, setProgs] = useState<Prog[]>([]);
  const [centros, setCentros] = useState<{ id: string; clave: string; nombre: string }[]>([]);
  const [cargado, setCargado] = useState<Usuario | null>(usuario);

  useEffect(() => { // el listado no trae programa_ids: se consulta el detalle al editar
    if (usuario && conProgramas) {
      api<Usuario>(`${base}/${usuario.id}`).then((d) => { setCargado(d); setSeleccion(new Set(d.programa_ids ?? [])); }).catch(() => {});
    }
  }, [base, usuario, conProgramas]);
  useEffect(() => {
    if (!conProgramas) return;
    api("/api/centros-gestores").then(setCentros).catch(() => {});
  }, [conProgramas]);
  useEffect(() => {
    if (!conProgramas) return;
    api(`/api/programas?ejercicio=${ejercicio}&activo=true`).then(setProgs).catch(() => {});
  }, [conProgramas, ejercicio]);

  const set = (k: string, v: any) => setF((x) => ({ ...x, [k]: v }));
  const alternarLista = (k: "anios_acceso" | "meses_acceso", n: number) =>
    set(k, f[k].includes(n) ? f[k].filter((x) => x !== n) : [...f[k], n].sort((a, b) => a - b));
  const porCentro = useMemo(() => centros.map((c) => ({ c, ps: progs.filter((p) => p.centro_gestor_id === c.id) })).filter((g) => g.ps.length), [centros, progs]);
  const marcar = (ids: string[], on: boolean) => setSeleccion((s) => { const n = new Set(s); ids.forEach((i) => on ? n.add(i) : n.delete(i)); return n; });

  async function guardar() {
    setOcupado(true);
    setErrores({});
    const json: Record<string, unknown> = { ...f, direccion: f.direccion || null, telefono: f.telefono || null, email: f.email || null };
    if (!usuario || f.password) json.password = f.password || null; else delete json.password;
    if (conProgramas) json.programa_ids = [...seleccion]; // incluye los de otros ejercicios (se conservan)
    try {
      const r = await api<Usuario & { password_generada?: string | null }>(usuario ? `${base}/${usuario.id}` : base,
        { method: usuario ? "PATCH" : "POST", json });
      toast.success(usuario ? "Cambios guardados" : "Usuario creado");
      onGuardado(r.password_generada ?? null, r);
    } catch (e) {
      if (e instanceof ApiError) { setErrores(e.campos); toast.error(e.message); } else toast.error("Error de conexión");
      setOcupado(false);
    }
  }

  return (
    <Modal titulo={usuario ? `Editar usuario — ${usuario.usuario}` : "Nuevo usuario"} size="lg" onClose={onClose} footer={<>
      <button className="btn btn-default" onClick={onClose}>Cancelar</button>
      <button className="btn btn-success" onClick={guardar} disabled={ocupado}>Guardar</button></>}>
      <div className="row">
        <div className="col-sm-6"><Campo label="Nombre" error={errores.nombre}>
          <input className="form-control" value={f.nombre} onChange={(e) => set("nombre", e.target.value)} autoFocus /></Campo></div>
        <div className="col-sm-3"><Campo label="Usuario" error={errores.usuario}>
          <input className="form-control" value={f.usuario} onChange={(e) => set("usuario", e.target.value)} autoComplete="off" /></Campo></div>
        <div className="col-sm-3"><Campo label="Contraseña" error={errores.password}>
          <input className="form-control" value={f.password} onChange={(e) => set("password", e.target.value)} autoComplete="off"
            placeholder={usuario ? "Vacío = no cambiar" : "Vacío = generar"} /></Campo></div>
      </div>
      <div className="row">
        <div className="col-sm-4"><Campo label="Tipo" error={errores.tipo}>
          <select className="form-control" value={f.tipo} onChange={(e) => set("tipo", e.target.value)}>
            {TIPOS.map((t) => <option key={t.valor} value={t.valor}>{t.nombre}</option>)}
          </select></Campo></div>
        <div className="col-sm-4"><Campo label="Email" error={errores.email}>
          <input className="form-control" value={f.email} onChange={(e) => set("email", e.target.value)} /></Campo></div>
        <div className="col-sm-4"><Campo label="Teléfono">
          <input className="form-control" value={f.telefono} onChange={(e) => set("telefono", e.target.value)} /></Campo></div>
      </div>
      <Campo label="Dirección"><input className="form-control" value={f.direccion} onChange={(e) => set("direccion", e.target.value)} /></Campo>
      <div className="row">
        <div className="col-sm-4"><Campo label="Años con acceso" error={errores.anios_acceso}>
          <div>{[anioActual - 1, anioActual, anioActual + 1, anioActual + 2].map((a) => (
            <label key={a} className="checkbox-inline"><input type="checkbox" checked={f.anios_acceso.includes(a)} onChange={() => alternarLista("anios_acceso", a)} /> {a}</label>))}</div>
        </Campo></div>
        <div className="col-sm-8"><Campo label="Meses con acceso" error={errores.meses_acceso}>
          <div>{MESES.map((m, i) => (
            <label key={m} className="checkbox-inline" style={{ minWidth: 95 }}><input type="checkbox" checked={f.meses_acceso.includes(i + 1)} onChange={() => alternarLista("meses_acceso", i + 1)} /> {m}</label>))}</div>
        </Campo></div>
      </div>
      {usuario && <div className="checkbox"><label><input type="checkbox" checked={f.activo} onChange={(e) => set("activo", e.target.checked)} /> Usuario activo</label></div>}

      {conProgramas && <>
        <h5 style={{ borderBottom: "1px solid #eee", paddingBottom: 8, margin: "15px 0" }}>
          Programas asignados <small>({seleccion.size}; alternativa a la matriz)</small></h5>
        <div className="toolbar"><label className="control-label">Ejercicio</label>
          <input type="number" className="form-control" style={{ maxWidth: 110 }} value={ejercicio} onChange={(e) => setEjercicio(e.target.value)} /></div>
        <div style={{ maxHeight: 220, overflowY: "auto", border: "1px solid #eee", padding: "8px 12px" }}>
          {!porCentro.length && <span className="text-muted">Sin programas en este ejercicio</span>}
          {porCentro.map(({ c, ps }) => {
            const todos = ps.every((p) => seleccion.has(p.id));
            return (
              <div key={c.id} style={{ marginBottom: 8 }}>
                <label><input type="checkbox" checked={todos} onChange={() => marcar(ps.map((p) => p.id), !todos)} /> <strong>{c.clave} — {c.nombre}</strong></label>
                {ps.map((p) => <div key={p.id} style={{ marginLeft: 22 }}><label className="text-muted" style={{ fontWeight: 400 }}>
                  <input type="checkbox" checked={seleccion.has(p.id)} onChange={() => marcar([p.id], !seleccion.has(p.id))} /> {p.clave} — {p.nombre}</label></div>)}
              </div>
            );
          })}
        </div>
      </>}
    </Modal>
  );
}
