"use client";
import { useState } from "react";
import { BodyClass } from "@/components/BodyClass";
import { toast } from "@/components/Toasts";
import { ApiError, api } from "@/lib/api.client";

/** Login del super admin: formulario simple, sin branding de municipio. */
export function AdminLoginForm() {
  const [usuario, setUsuario] = useState("");
  const [password, setPassword] = useState("");
  const [ocupado, setOcupado] = useState(false);

  async function entrar() {
    if (!usuario.trim() || !password) return void toast.info("Escribe usuario y contraseña");
    setOcupado(true);
    try {
      await api("/api/admin/auth/login", { method: "POST", json: { usuario, password } });
      window.location.href = "/";
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Error de conexión");
      setOcupado(false);
    }
  }

  return (
    <>
      <BodyClass name="login-body" />
      <div className="login-logo"><span><i className="fa fa-line-chart" /> Indicadores</span></div>
      <h2 className="form-heading">Administración de la plataforma</h2>
      <div className="container lock-row">
        <form className="form-signin" autoComplete="off" onSubmit={(e) => { e.preventDefault(); entrar(); }}>
          <div className="login-wrap">
            <input type="text" className="form-control text-center" placeholder="Usuario" value={usuario}
              onChange={(e) => setUsuario(e.target.value)} autoFocus />
            <input type="password" className="form-control text-center" placeholder="Password" value={password}
              onChange={(e) => setPassword(e.target.value)} />
            <button className="btn btn-lg btn-info btn-block" disabled={ocupado}>Entrar</button>
          </div>
        </form>
      </div>
    </>
  );
}
