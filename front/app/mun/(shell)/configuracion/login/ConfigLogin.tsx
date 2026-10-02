"use client";
import { useEffect, useState } from "react";
import { Campo, mensajeError } from "@/components/Campo";
import { toast } from "@/components/Toasts";
import { useTipo } from "@/components/TipoContext";
import { ApiError, api } from "@/lib/api.client";
import { puede } from "@/lib/permisos";

const COLORES = ["default", "primary", "info", "success", "warning", "danger", "dark"];

async function subirImagen(file: File): Promise<string> {
  const fd = new FormData();
  fd.append("archivo", file);
  const res = await fetch("/api/uploads/imagen", { method: "POST", body: fd });
  const data = await res.json();
  if (!res.ok) throw new ApiError(res.status, data.codigo, data.mensaje);
  return data.url;
}

export function ConfigLogin() {
  const editable = puede.editarLogin(useTipo());
  const [f, setF] = useState<{ imagen_login_url: string | null; color_boton: string; mostrar_logos: boolean } | null>(null);
  const [subiendo, setSubiendo] = useState(false);

  useEffect(() => { api("/api/config").then(setF).catch((e) => toast.error(mensajeError(e))); }, []);
  if (!f) return <p className="text-muted">Cargando…</p>;

  async function guardar() {
    try {
      await api("/api/config", { method: "PATCH", json: { imagen_login_url: f!.imagen_login_url, color_boton: f!.color_boton, mostrar_logos: f!.mostrar_logos } });
      toast.success("Configuración guardada");
    } catch (e) { toast.error(mensajeError(e)); }
  }

  return (
    <>
      <h3 className="page-heading">Configuración</h3>
      <div className="panel">
        <div className="panel-heading"><ul className="nav nav-tabs">
          <li className="active"><a href="/configuracion/login">Login</a></li>
          <li><a href="/configuracion/meses-avances">Meses de avances</a></li>
        </ul></div>
        <div className="panel-body">
          <div className="row">
            <div className="col-sm-6"><Campo label="Imagen de la pantalla de login">
              {f.imagen_login_url && <div style={{ marginBottom: 8 }}><img src={f.imagen_login_url} alt="" style={{ maxHeight: 80, maxWidth: 260, border: "1px solid #eee" }} />{" "}
                {editable && <button className="btn btn-xs btn-default" onClick={() => setF({ ...f, imagen_login_url: null })}>Quitar</button>}</div>}
              {editable && <input type="file" accept="image/png,image/jpeg,image/webp" disabled={subiendo} onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                setSubiendo(true);
                try { setF({ ...f, imagen_login_url: await subirImagen(file) }); } catch (err) { toast.error(mensajeError(err)); }
                setSubiendo(false);
              }} />}
            </Campo></div>
            <div className="col-sm-3"><Campo label="Color del botón">
              <select className="form-control" value={f.color_boton} disabled={!editable} onChange={(e) => setF({ ...f, color_boton: e.target.value })}>
                {COLORES.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
              <button type="button" className={`btn btn-${f.color_boton} btn-sm`} style={{ marginTop: 6 }}>Vista previa</button></Campo></div>
            <div className="col-sm-3"><Campo label="Logos">
              <div className="checkbox"><label><input type="checkbox" checked={f.mostrar_logos} disabled={!editable}
                onChange={(e) => setF({ ...f, mostrar_logos: e.target.checked })} /> Mostrar logos</label></div></Campo></div>
          </div>
          {editable && <button className="btn btn-success" onClick={guardar}><i className="fa fa-save" /> Guardar</button>}
        </div>
      </div>
    </>
  );
}
