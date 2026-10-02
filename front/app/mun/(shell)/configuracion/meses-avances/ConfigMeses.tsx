"use client";
import { useEffect, useState } from "react";
import { Campo, mensajeError } from "@/components/Campo";
import { toast } from "@/components/Toasts";
import { useTipo } from "@/components/TipoContext";
import { ApiError, api } from "@/lib/api.client";
import { MESES, puede } from "@/lib/permisos";

export function ConfigMeses() {
  const tipo = useTipo();
  const editable = puede.editarMeses(tipo);
  const [f, setF] = useState<{ meses_avance_activos: number[]; tolerancia_semaforo: string } | null>(null);
  const [errores, setErrores] = useState<Record<string, string>>({});

  useEffect(() => {
    api("/api/config").then((c) => setF({ meses_avance_activos: c.meses_avance_activos, tolerancia_semaforo: String(c.tolerancia_semaforo) }))
      .catch((e) => toast.error(mensajeError(e)));
  }, []);
  if (!f) return <p className="text-muted">Cargando…</p>;

  async function guardar() {
    setErrores({});
    try {
      await api("/api/config", { method: "PATCH", json: { meses_avance_activos: f!.meses_avance_activos, tolerancia_semaforo: Number(f!.tolerancia_semaforo) } });
      toast.success("Configuración guardada");
    } catch (e) {
      if (e instanceof ApiError) { setErrores(e.campos); toast.error(e.message); } else toast.error("Error de conexión");
    }
  }
  const alternar = (n: number) => setF({ ...f, meses_avance_activos: f.meses_avance_activos.includes(n) ? f.meses_avance_activos.filter((x) => x !== n) : [...f.meses_avance_activos, n].sort((a, b) => a - b) });

  return (
    <>
      <h3 className="page-heading">Configuración</h3>
      <div className="panel">
        <div className="panel-heading"><ul className="nav nav-tabs">
          {tipo === "informes" || tipo === "administrador" ? <li><a href="/configuracion/login">Login</a></li> : null}
          <li className="active"><a href="/configuracion/meses-avances">Meses de avances</a></li>
        </ul></div>
        <div className="panel-body">
          <div style={{ maxWidth: 260 }}><Campo label="Tolerancia (días)" error={errores.tolerancia_semaforo}>
            <input type="number" min={0} className="form-control" value={f.tolerancia_semaforo} disabled={!editable}
              onChange={(e) => setF({ ...f, tolerancia_semaforo: e.target.value })} /></Campo></div>
          <Campo label="Meses del año en curso que aceptan captura de avances" error={errores.meses_avance_activos}>
            <div className="row">{MESES.map((m, i) => (
              <div key={m} className="col-xs-6 col-sm-3"><div className="checkbox"><label><input type="checkbox" disabled={!editable}
                checked={f.meses_avance_activos.includes(i + 1)} onChange={() => alternar(i + 1)} /> {m}</label></div></div>))}</div>
          </Campo>
          {editable ? <button className="btn btn-success" onClick={guardar}><i className="fa fa-save" /> Guardar</button>
            : <p className="text-muted">Solo el Administrador y el Alcalde pueden editar estos valores.</p>}
        </div>
      </div>
    </>
  );
}
