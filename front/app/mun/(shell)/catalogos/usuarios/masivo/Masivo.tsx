"use client";
import { useState } from "react";
import { mensajeError } from "@/components/Campo";
import { toast } from "@/components/Toasts";
import { useTipo } from "@/components/TipoContext";
import { api } from "@/lib/api.client";
import { TIPOS, puede } from "@/lib/permisos";

type Fila = { nombre: string; usuario: string; email: string; tipo: string; password: string };
const vacia = (): Fila => ({ nombre: "", usuario: "", email: "", tipo: "informes", password: "" });
const COLS: (keyof Fila)[] = ["nombre", "usuario", "email", "tipo", "password"];

/** "Padrón", "padron", "7.- ADMINISTRADOR" -> clave de tipo (si no se reconoce, se deja tal cual y la API lo marca). */
function tipoDesdeTexto(t: string): string {
  const limpio = t.trim().toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/^\d+\.-\s*/, "");
  return TIPOS.find((x) => limpio === x.valor || limpio === x.nombre.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "")
    || limpio.startsWith(x.valor.split("_")[0]))?.valor ?? limpio;
}

export function Masivo() {
  const tipoSesion = useTipo();
  const [filas, setFilas] = useState<Fila[]>([vacia(), vacia(), vacia()]);
  const [errores, setErrores] = useState<Record<number, Record<string, string>>>({});
  const [creados, setCreados] = useState<{ usuario: string; password_generada: string | null }[]>([]);
  const [ocupado, setOcupado] = useState(false);

  if (!puede.gestionarUsuarios(tipoSesion)) return <p className="text-muted">Sin acceso a este módulo.</p>;

  const set = (i: number, c: keyof Fila, v: string) => setFilas((fs) => fs.map((f, j) => (j === i ? { ...f, [c]: v } : f)));

  /** Pegar desde Excel: texto separado por tabs (una fila por línea) desde la celda donde se pegó. */
  function pegar(e: React.ClipboardEvent, fila: number, col: number) {
    const texto = e.clipboardData.getData("text");
    if (!/[\t\n]/.test(texto)) return; // un solo valor: pegado normal
    e.preventDefault();
    const lineas = texto.replace(/\r/g, "").split("\n").filter((l, i, a) => l.length || i < a.length - 1);
    setFilas((fs) => {
      const n = [...fs];
      lineas.forEach((linea, li) => {
        const celdas = linea.split("\t");
        while (n.length <= fila + li) n.push(vacia());
        celdas.forEach((v, ci) => {
          const c = COLS[col + ci];
          if (c) n[fila + li] = { ...n[fila + li], [c]: c === "tipo" ? tipoDesdeTexto(v) : v.trim() };
        });
      });
      return n;
    });
  }

  async function guardar() {
    const envio = filas.map((f, i) => ({ f, i })).filter(({ f }) => COLS.some((c) => f[c] && c !== "tipo"));
    if (!envio.length) return void toast.info("Captura al menos un usuario");
    setOcupado(true);
    setErrores({});
    try {
      const r = await api<{ creados: { fila: number; usuario: string; password_generada: string | null }[]; errores: { fila: number; campos: Record<string, string> }[] }>(
        "/api/usuarios/bulk", { method: "POST", json: { filas: envio.map(({ f }) => ({ ...f, email: f.email || null, password: f.password || null })) } });
      const ok = new Set(r.creados.map((c) => envio[c.fila].i));
      setCreados((c) => [...c, ...r.creados]);
      // las inválidas se quedan (con su error); las creadas se retiran sin perder las válidas
      const quedan = filas.filter((_, i) => !ok.has(i));
      const mapa: Record<number, Record<string, string>> = {};
      r.errores.forEach((e) => { mapa[quedan.indexOf(filas[envio[e.fila].i])] = e.campos; });
      setFilas(quedan.length ? quedan : [vacia()]);
      setErrores(mapa);
      if (r.creados.length) toast.success(`${r.creados.length} usuario(s) creado(s)`);
      if (r.errores.length) toast.error(`${r.errores.length} fila(s) con error`);
    } catch (e) { toast.error(mensajeError(e)); }
    setOcupado(false);
  }

  return (
    <>
      <h3 className="page-heading">Alta masiva de usuarios</h3>
      <div className="panel"><div className="panel-body">
        <p className="text-muted">Captura una fila por usuario o pega desde Excel (columnas: nombre, usuario, email, tipo, contraseña).
          Contraseña vacía = se genera. Las filas con error se señalan y las válidas se crean igual.</p>
        <div className="table-responsive">
          <table className="table table-condensed">
            <thead><tr><th style={{ width: 30 }}>#</th><th>Nombre</th><th>Usuario</th><th>Email</th><th>Tipo</th><th>Contraseña inicial</th><th style={{ width: 40 }} /></tr></thead>
            <tbody>
              {filas.map((f, i) => (
                <tr key={i}>
                  <td className="text-muted">{i + 1}</td>
                  {COLS.map((c, ci) => (
                    <td key={c} className={errores[i]?.[c] ? "has-error" : ""}>
                      {c === "tipo" ? (
                        <select className="form-control input-sm" value={f.tipo} onChange={(e) => set(i, "tipo", e.target.value)}>
                          {TIPOS.map((t) => <option key={t.valor} value={t.valor}>{t.nombre}</option>)}
                          {!TIPOS.some((t) => t.valor === f.tipo) && <option value={f.tipo}>{f.tipo}</option>}
                        </select>
                      ) : (
                        <input className="form-control input-sm" value={f[c]} autoComplete="off" placeholder={c === "password" ? "Generar" : ""}
                          onChange={(e) => set(i, c, e.target.value)} onPaste={(e) => pegar(e, i, ci)} />
                      )}
                      {errores[i]?.[c] && <span className="help-block">{errores[i][c]}</span>}
                    </td>
                  ))}
                  <td><button className="btn btn-xs btn-default" title="Quitar fila" onClick={() => setFilas((fs) => fs.length > 1 ? fs.filter((_, j) => j !== i) : [vacia()])}><i className="fa fa-times" /></button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="toolbar">
          <button className="btn btn-default" onClick={() => setFilas((fs) => [...fs, vacia()])}><i className="fa fa-plus" /> Agregar fila</button>
          <span className="spacer" />
          <a className="btn btn-default" href="/catalogos/usuarios">Usuarios</a>
          <a className="btn btn-info" href="/catalogos/usuarios/matriz"><i className="fa fa-th" /> Ir a la matriz</a>
          <button className="btn btn-success" onClick={guardar} disabled={ocupado}><i className="fa fa-save" /> Guardar</button>
        </div>
      </div></div>

      {creados.length > 0 && <div className="panel"><div className="panel-body">
        <h5>Usuarios creados</h5>
        <table className="table table-condensed" style={{ maxWidth: 520 }}><thead><tr><th>Usuario</th><th>Contraseña generada</th></tr></thead>
          <tbody>{creados.map((c, i) => <tr key={i}><td>{c.usuario}</td><td>{c.password_generada ? <code>{c.password_generada}</code> : <span className="text-muted">la capturada</span>}</td></tr>)}</tbody></table>
        <p className="help-block">Ya aparecen en la matriz. Las contraseñas también se pueden consultar después desde el listado de Usuarios.</p>
      </div></div>}
    </>
  );
}
