"use client";
import { useState } from "react";
import { BodyClass } from "@/components/BodyClass";
import { toast } from "@/components/Toasts";
import { ApiError, api } from "@/lib/api.client";

type Marca = { nombre: string; imagen_login_url: string | null; color_boton: string; mostrar_logos: boolean };
const AVISO: Record<string, string> = {
  TOKEN_VENCIDO: "Este enlace venció. Solicita uno nuevo.",
  TOKEN_USADO: "Este enlace ya se utilizó. Si lo necesitas, solicita uno nuevo.",
  TOKEN_INVALIDO: "El enlace no es válido. Solicita uno nuevo.",
};

/** Sin token: pide el usuario y envía el correo. Con token (link del correo): captura la contraseña nueva. */
export function RecuperarForm({ token, marca }: { token: string | null; marca: Marca }) {
  const [usuario, setUsuario] = useState("");
  const [pass, setPass] = useState("");
  const [repetir, setRepetir] = useState("");
  const [fase, setFase] = useState<"form" | "enviado" | "listo">("form");
  const [aviso, setAviso] = useState<{ texto: string; solicitar: boolean } | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const btn = `btn btn-lg btn-${marca?.color_boton ?? "info"} btn-block`;

  async function solicitar() {
    if (!usuario.trim()) return void toast.info("Captura tu usuario");
    setOcupado(true);
    try {
      await api("/api/auth/recuperar", { method: "POST", json: { usuario } });
      setFase("enviado"); // respuesta idéntica exista o no el usuario
    } catch (e) { toast.error(e instanceof ApiError ? e.message : "Error de conexión"); }
    setOcupado(false);
  }

  async function confirmar() {
    if (!pass) return void toast.error("Captura la contraseña nueva");
    if (pass !== repetir) return void toast.error("Las contraseñas no coinciden");
    setOcupado(true);
    try {
      await api("/api/auth/recuperar/confirmar", { method: "POST", json: { token, password_nueva: pass } });
      setFase("listo");
    } catch (e) {
      if (e instanceof ApiError && AVISO[e.codigo]) setAviso({ texto: AVISO[e.codigo], solicitar: true });
      else toast.error(e instanceof ApiError ? e.message : "Error de conexión");
    }
    setOcupado(false);
  }

  return (
    <>
      <BodyClass name="login-body" />
      <div className="login-logo"><div className="row"><div className="col-md-12">
        {marca?.mostrar_logos && marca.imagen_login_url ? <><br /><img src={marca.imagen_login_url} className="login-image" alt={marca.nombre} /></> : <span>{marca?.nombre}</span>}
      </div></div></div>
      <h2 className="form-heading">Recuperar contraseña</h2>
      <div className="container lock-row"><div className="form-signin"><div className="login-wrap">
        {fase === "listo" && <>
          <p className="text-center">Tu contraseña se actualizó. Ya puedes iniciar sesión.</p>
          <a className={btn} href="/login">Ir a iniciar sesión</a></>}

        {fase === "enviado" && <>
          <p className="text-center">Si el usuario existe y tiene un correo registrado, te enviamos las instrucciones. El enlace dura 1 hora.</p>
          <a className={btn} href="/login">Volver</a></>}

        {fase === "form" && token && !aviso && <form autoComplete="off" onSubmit={(e) => { e.preventDefault(); confirmar(); }}>
          <input type="password" className="form-control text-center" placeholder="Contraseña nueva" value={pass} onChange={(e) => setPass(e.target.value)} autoFocus />
          <input type="password" className="form-control text-center" placeholder="Repetir contraseña" value={repetir} onChange={(e) => setRepetir(e.target.value)} />
          <button className={btn} disabled={ocupado}>Guardar contraseña</button></form>}

        {fase === "form" && token && aviso && <>
          <p className="text-center red">{aviso.texto}</p>
          <a className={btn} href="/recuperar">Solicitar un enlace nuevo</a></>}

        {fase === "form" && !token && <form autoComplete="off" onSubmit={(e) => { e.preventDefault(); solicitar(); }}>
          <input type="text" className="form-control text-center" placeholder="Usuario" value={usuario} onChange={(e) => setUsuario(e.target.value)} autoFocus />
          <button className={btn} disabled={ocupado}>Enviar instrucciones</button>
          <div className="registration text-center"><a href="/login">Volver a iniciar sesión</a></div></form>}
      </div></div></div>
    </>
  );
}
