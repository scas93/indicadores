"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Modal } from "@/components/Modal";
import { toast } from "@/components/Toasts";
import { ApiError, api } from "@/lib/api.client";

type Muni = {
  id: string; nombre: string; subdominio: string; estado: "activo" | "suspendido"; estado_republica: string | null;
  estado_republica_id: string | null; logo_url: string | null; imagen_login_url: string | null; color_boton: string;
  mostrar_logos: boolean; duracion_sesion_dias: number; created_at: string;
};
type Estado = { id: string; clave: string; nombre: string };
const COLORES = ["default", "primary", "info", "success", "warning", "danger", "dark"];

const rootDomain = () => (typeof window === "undefined" ? "" : window.location.hostname.split(".").slice(1).join("."));
const fecha = (s: string) => new Date(s).toLocaleDateString("es-MX", { year: "numeric", month: "2-digit", day: "2-digit" });

async function subirImagen(file: File): Promise<string> {
  const fd = new FormData();
  fd.append("archivo", file);
  const res = await fetch("/api/admin/uploads/imagen", { method: "POST", body: fd });
  const data = await res.json();
  if (!res.ok) throw new ApiError(res.status, data.codigo, data.mensaje);
  return data.url;
}

function Campo({ label, error, children }: { label: string; error?: string; children: React.ReactNode }) {
  return (
    <div className={`form-group${error ? " has-error" : ""}`}>
      <label className="control-label">{label}</label>
      {children}
      {error && <span className="help-block">{error}</span>}
    </div>
  );
}

function Imagen({ valor, onChange }: { valor: string | null; onChange: (u: string | null) => void }) {
  const [subiendo, setSubiendo] = useState(false);
  return (
    <div>
      {valor && <div style={{ marginBottom: 8 }}><img src={valor} alt="" style={{ maxHeight: 60, maxWidth: 200, border: "1px solid #eee" }} />{" "}
        <button type="button" className="btn btn-xs btn-default" onClick={() => onChange(null)}>Quitar</button></div>}
      <input type="file" accept="image/png,image/jpeg,image/webp" disabled={subiendo} onChange={async (e) => {
        const f = e.target.files?.[0];
        if (!f) return;
        setSubiendo(true);
        try { onChange(await subirImagen(f)); } catch (err) { toast.error(err instanceof ApiError ? err.message : "No se pudo subir"); }
        setSubiendo(false);
      }} />
    </div>
  );
}

function ModalAlta({ estados, onClose, onCreado }: { estados: Estado[]; onClose: () => void; onCreado: (r: any) => void }) {
  const [f, setF] = useState({ nombre: "", subdominio: "", estado_republica_id: "", logo_url: null as string | null,
    admin_nombre: "", admin_usuario: "", admin_password: "" });
  const [errores, setErrores] = useState<Record<string, string>>({});
  const [disp, setDisp] = useState<{ ok: boolean; msg: string } | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const set = (k: string, v: any) => setF((x) => ({ ...x, [k]: v }));

  useEffect(() => { // disponibilidad en vivo
    if (!f.subdominio.trim()) return void setDisp(null);
    const t = setTimeout(async () => {
      try {
        const r = await api(`/api/admin/municipios/subdominio-disponible?valor=${encodeURIComponent(f.subdominio)}`);
        setDisp(r.disponible ? { ok: true, msg: "Disponible" } : { ok: false, msg: r.mensaje });
      } catch { setDisp(null); }
    }, 350);
    return () => clearTimeout(t);
  }, [f.subdominio]);

  async function guardar() {
    setOcupado(true);
    setErrores({});
    try {
      const r = await api("/api/admin/municipios", { method: "POST", json: {
        ...f, estado_republica_id: f.estado_republica_id || null, admin_password: f.admin_password || null } });
      onCreado(r);
    } catch (e) {
      if (e instanceof ApiError) { setErrores(e.campos); toast.error(e.message); } else toast.error("Error de conexión");
      setOcupado(false);
    }
  }

  return (
    <Modal titulo="Nuevo municipio" onClose={onClose} footer={<>
      <button className="btn btn-default" onClick={onClose}>Cancelar</button>
      <button className="btn btn-success" onClick={guardar} disabled={ocupado}>Guardar</button></>}>
      <div className="row">
        <div className="col-sm-6"><Campo label="Nombre" error={errores.nombre}>
          <input className="form-control" value={f.nombre} onChange={(e) => set("nombre", e.target.value)} autoFocus /></Campo></div>
        <div className="col-sm-6"><Campo label="Subdominio" error={errores.subdominio || (disp && !disp.ok ? disp.msg : undefined)}>
          <div className="input-group">
            <input className="form-control" value={f.subdominio} onChange={(e) => set("subdominio", e.target.value.toLowerCase())} placeholder="demo" />
            <span className="input-group-addon">.{rootDomain() || "dominio"}</span>
          </div>
          {disp?.ok && <span className="help-block" style={{ color: "#3c763d" }}><i className="fa fa-check" /> {disp.msg}</span>}
        </Campo></div>
      </div>
      <div className="row">
        <div className="col-sm-6"><Campo label="Estado de la república" error={errores.estado_republica_id}>
          <select className="form-control" value={f.estado_republica_id} onChange={(e) => set("estado_republica_id", e.target.value)}>
            <option value="">— Seleccione —</option>
            {estados.map((e) => <option key={e.id} value={e.id}>{e.nombre}</option>)}
          </select></Campo></div>
        <div className="col-sm-6"><Campo label="Logo"><Imagen valor={f.logo_url} onChange={(u) => set("logo_url", u)} /></Campo></div>
      </div>
      <h5 style={{ borderBottom: "1px solid #eee", paddingBottom: 8, margin: "10px 0 15px" }}>Primer Administrador</h5>
      <div className="row">
        <div className="col-sm-4"><Campo label="Nombre" error={errores.admin_nombre}>
          <input className="form-control" value={f.admin_nombre} onChange={(e) => set("admin_nombre", e.target.value)} /></Campo></div>
        <div className="col-sm-4"><Campo label="Usuario" error={errores.admin_usuario}>
          <input className="form-control" value={f.admin_usuario} onChange={(e) => set("admin_usuario", e.target.value)} autoComplete="off" /></Campo></div>
        <div className="col-sm-4"><Campo label="Contraseña inicial" error={errores.admin_password}>
          <input className="form-control" value={f.admin_password} onChange={(e) => set("admin_password", e.target.value)}
            placeholder="Vacío = generar" autoComplete="off" /></Campo></div>
      </div>
    </Modal>
  );
}

function ModalEditar({ m, estados, onClose, onGuardado }: { m: Muni; estados: Estado[]; onClose: () => void; onGuardado: () => void }) {
  const [f, setF] = useState({ nombre: m.nombre, estado_republica_id: m.estado_republica_id ?? "", logo_url: m.logo_url,
    imagen_login_url: m.imagen_login_url, color_boton: m.color_boton, mostrar_logos: m.mostrar_logos,
    duracion_sesion_dias: String(m.duracion_sesion_dias) });
  const [errores, setErrores] = useState<Record<string, string>>({});
  const set = (k: string, v: any) => setF((x) => ({ ...x, [k]: v }));

  async function guardar() {
    setErrores({});
    try {
      await api(`/api/admin/municipios/${m.id}`, { method: "PATCH", json: {
        ...f, estado_republica_id: f.estado_republica_id || null, duracion_sesion_dias: Number(f.duracion_sesion_dias) } });
      toast.success("Municipio actualizado");
      onGuardado();
    } catch (e) {
      if (e instanceof ApiError) { setErrores(e.campos); toast.error(e.message); }
    }
  }

  return (
    <Modal titulo={`Editar municipio — ${m.subdominio}`} onClose={onClose} footer={<>
      <button className="btn btn-default" onClick={onClose}>Cancelar</button>
      <button className="btn btn-success" onClick={guardar}>Guardar</button></>}>
      <div className="row">
        <div className="col-sm-6"><Campo label="Nombre" error={errores.nombre}>
          <input className="form-control" value={f.nombre} onChange={(e) => set("nombre", e.target.value)} /></Campo></div>
        <div className="col-sm-6"><Campo label="Estado de la república">
          <select className="form-control" value={f.estado_republica_id} onChange={(e) => set("estado_republica_id", e.target.value)}>
            <option value="">— Seleccione —</option>
            {estados.map((e) => <option key={e.id} value={e.id}>{e.nombre}</option>)}
          </select></Campo></div>
      </div>
      <div className="row">
        <div className="col-sm-6"><Campo label="Logo"><Imagen valor={f.logo_url} onChange={(u) => set("logo_url", u)} /></Campo></div>
        <div className="col-sm-6"><Campo label="Imagen de la pantalla de login"><Imagen valor={f.imagen_login_url} onChange={(u) => set("imagen_login_url", u)} /></Campo></div>
      </div>
      <div className="row">
        <div className="col-sm-4"><Campo label="Color del botón">
          <select className="form-control" value={f.color_boton} onChange={(e) => set("color_boton", e.target.value)}>
            {COLORES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <button type="button" className={`btn btn-${f.color_boton} btn-sm`} style={{ marginTop: 6 }}>Vista previa</button></Campo></div>
        <div className="col-sm-4"><Campo label="Duración de sesión (días)" error={errores.duracion_sesion_dias}>
          <input type="number" min={1} className="form-control" value={f.duracion_sesion_dias} onChange={(e) => set("duracion_sesion_dias", e.target.value)} /></Campo></div>
        <div className="col-sm-4"><Campo label="Logos">
          <div className="checkbox"><label><input type="checkbox" checked={f.mostrar_logos} onChange={(e) => set("mostrar_logos", e.target.checked)} /> Mostrar logos</label></div></Campo></div>
      </div>
    </Modal>
  );
}

export function Municipios() {
  const [lista, setLista] = useState<Muni[] | null>(null);
  const [estados, setEstados] = useState<Estado[]>([]);
  const [q, setQ] = useState("");
  const [modal, setModal] = useState<null | "alta" | Muni>(null);
  const [resultado, setResultado] = useState<any>(null);
  const [confirma, setConfirma] = useState<Muni | null>(null);

  const cargar = useCallback(async () => setLista(await api("/api/admin/municipios")), []);
  useEffect(() => {
    cargar().catch(() => toast.error("No se pudo cargar"));
    api("/api/admin/plantillas/geografia?nivel=estado").then(setEstados).catch(() => {});
  }, [cargar]);

  const filtrada = useMemo(() => (lista ?? []).filter((m) =>
    (m.nombre + m.subdominio).toLowerCase().includes(q.toLowerCase())), [lista, q]);

  async function cambiarEstado(m: Muni) {
    const nuevo = m.estado === "activo" ? "suspendido" : "activo";
    try {
      await api(`/api/admin/municipios/${m.id}`, { method: "PATCH", json: { estado: nuevo } });
      toast.success(nuevo === "suspendido" ? "Municipio suspendido" : "Municipio activado");
      setConfirma(null);
      cargar();
    } catch { toast.error("No se pudo cambiar el estado"); }
  }

  return (
    <>
      <h3 className="page-heading">Municipios</h3>
      <div className="panel"><div className="panel-body">
        <div className="toolbar">
          <input className="form-control" style={{ maxWidth: 300 }} placeholder="Buscar" value={q} onChange={(e) => setQ(e.target.value)} />
          <span className="spacer" />
          <button className="btn btn-success" onClick={() => setModal("alta")}><i className="fa fa-plus" /> Nuevo municipio</button>
        </div>
        <div className="table-responsive">
          <table className="table table-hover">
            <thead><tr><th>Nombre</th><th>Subdominio</th><th>Estado</th><th>Fecha de alta</th><th style={{ width: 160 }}>Acciones</th></tr></thead>
            <tbody>
              {lista === null && <tr><td colSpan={5} className="text-center text-muted">Cargando…</td></tr>}
              {lista && !filtrada.length && <tr><td colSpan={5} className="text-center text-muted">Sin municipios</td></tr>}
              {filtrada.map((m) => (
                <tr key={m.id}>
                  <td>{m.nombre}</td>
                  <td>{m.subdominio}.{rootDomain()}</td>
                  <td><span className={`label label-${m.estado === "activo" ? "success" : "danger"}`}>{m.estado === "activo" ? "Activo" : "Suspendido"}</span></td>
                  <td>{fecha(m.created_at)}</td>
                  <td>
                    <button className="btn btn-xs btn-info" title="Editar" onClick={() => setModal(m)}><i className="fa fa-pencil" /></button>{" "}
                    <a className="btn btn-xs btn-primary" title="Usuarios" href={`/municipios/${m.id}/usuarios`}><i className="fa fa-users" /></a>{" "}
                    <button className={`btn btn-xs ${m.estado === "activo" ? "btn-warning" : "btn-success"}`}
                      title={m.estado === "activo" ? "Suspender" : "Activar"} onClick={() => m.estado === "activo" ? setConfirma(m) : cambiarEstado(m)}>
                      <i className={`fa ${m.estado === "activo" ? "fa-pause" : "fa-play"}`} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div></div>

      {modal === "alta" && <ModalAlta estados={estados} onClose={() => setModal(null)}
        onCreado={(r) => { setModal(null); setResultado(r); cargar(); }} />}
      {modal && modal !== "alta" && <ModalEditar m={modal} estados={estados} onClose={() => setModal(null)}
        onGuardado={() => { setModal(null); cargar(); }} />}

      {confirma && <Modal titulo="Suspender municipio" onClose={() => setConfirma(null)} footer={<>
        <button className="btn btn-default" onClick={() => setConfirma(null)}>Cancelar</button>
        <button className="btn btn-warning" onClick={() => cambiarEstado(confirma)}>Suspender</button></>}>
        <p>Nadie de <strong>{confirma.nombre}</strong> podrá entrar y las sesiones abiertas dejarán de funcionar. Los datos se conservan.</p>
      </Modal>}

      {resultado && <Modal titulo="Municipio creado" onClose={() => setResultado(null)}
        footer={<button className="btn btn-success" onClick={() => setResultado(null)}>Listo</button>}>
        <p><i className="fa fa-check text-success" /> <strong>{resultado.municipio.nombre}</strong> ya responde en{" "}
          <strong>{resultado.municipio.subdominio}.{rootDomain()}</strong>.</p>
        <table className="table table-condensed" style={{ marginBottom: 0 }}><tbody>
          <tr><th>Administrador</th><td>{resultado.administrador.nombre}</td></tr>
          <tr><th>Usuario</th><td>{resultado.administrador.usuario}</td></tr>
          {resultado.password_inicial && <tr><th>Contraseña generada</th><td><code>{resultado.password_inicial}</code></td></tr>}
        </tbody></table>
        {resultado.password_inicial && <p className="help-block">Cópiala ahora: es la única vez que se muestra aquí.</p>}
      </Modal>}
    </>
  );
}
