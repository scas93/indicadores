"use client";
import { useRef, useState } from "react";
import { BodyClass } from "@/components/BodyClass";
import { toast } from "@/components/Toasts";
import { ApiError, api } from "@/lib/api.client";

type Marca = { nombre: string; imagen_login_url: string | null; color_boton: string; mostrar_logos: boolean };

/** Mismo flujo que el sistema actual: 1) Usuario -> "Verificar"; 2) "Iniciado como X" -> Password -> "Entrar". */
export function LoginForm({ marca }: { marca: Marca }) {
  const [paso, setPaso] = useState<1 | 2>(1);
  const [usuario, setUsuario] = useState("");
  const [nombre, setNombre] = useState("");
  const [password, setPassword] = useState("");
  const [msg, setMsg] = useState({ texto: "Ingrese su Usuario", error: false });
  const [ocupado, setOcupado] = useState(false);
  const passRef = useRef<HTMLInputElement>(null);
  const btn = `btn btn-lg btn-${marca.color_boton} btn-block`;

  async function verificar() {
    if (!usuario.trim()) return void toast.info("El Usuario No puede Quedar vacio");
    setOcupado(true);
    try {
      const r = await api<{ usuario: string; nombre: string }>("/api/auth/verificar-usuario", { method: "POST", json: { usuario } });
      setNombre(r.nombre);
      setUsuario(r.usuario);
      setMsg({ texto: "", error: false });
      setPaso(2);
      setTimeout(() => passRef.current?.focus(), 0);
    } catch (e) {
      setMsg({ texto: e instanceof ApiError ? e.message : "Error de conexión", error: true });
    } finally { setOcupado(false); }
  }

  async function entrar() {
    if (!password) return void toast.error("El Password no puede quedar vacio");
    setOcupado(true);
    try {
      await api("/api/auth/login", { method: "POST", json: { usuario, password } });
      toast.success("Bienvenido");
      setTimeout(() => { window.location.href = "/"; }, 1000);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Error de conexión");
      setOcupado(false);
    }
  }

  return (
    <>
      <BodyClass name="login-body" />
      <div className="login-logo">
        <div className="row"><div className="col-md-12">
          {marca.mostrar_logos && marca.imagen_login_url
            ? <><br /><img src={marca.imagen_login_url} className="login-image" alt={marca.nombre} /></>
            : <span>{marca.nombre}</span>}
        </div></div>
      </div>

      {paso === 1 ? (
        <div>
          <h2 className="form-heading">Iniciar sesión - sistema indicadores</h2>
          <div className="container lock-row">
            <form className="form-signin" autoComplete="off" onSubmit={(e) => { e.preventDefault(); verificar(); }}>
              <div className="login-wrap">
                <input type="text" className="form-control text-center" name="usuario" placeholder="Usuario"
                  value={usuario} onChange={(e) => setUsuario(e.target.value)} autoFocus />
                <button className={btn} disabled={ocupado}>Verificar</button>
                <div className="registration text-center">
                  <a className={msg.error ? "red" : ""}>{msg.texto}</a>
                </div>
              </div>
            </form>
          </div>
        </div>
      ) : (
        <div>
          <h2 className="form-heading lock"><span>Iniciado como</span><span className="u-name">{nombre}</span></h2>
          <div className="container lock-row">
            <form className="form-signin" autoComplete="off" onSubmit={(e) => { e.preventDefault(); entrar(); }}>
              <div className="login-wrap">
                <input ref={passRef} type="password" className="form-control text-center" placeholder="Password para entrar"
                  value={password} onChange={(e) => setPassword(e.target.value)} />
                <button className={btn} disabled={ocupado}>Entrar</button>
                <div className="registration text-center">
                  <a href="/login">Entrar con una cuenta diferente</a>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
