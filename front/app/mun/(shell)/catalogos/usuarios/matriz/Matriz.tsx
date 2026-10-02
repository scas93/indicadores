"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { mensajeError } from "@/components/Campo";
import { Modal } from "@/components/Modal";
import { toast } from "@/components/Toasts";
import { useTipo } from "@/components/TipoContext";
import { api } from "@/lib/api.client";
import { TIPOS, nombreTipo, puede } from "@/lib/permisos";

type Datos = {
  centros_gestores: { id: string; clave: string; nombre: string }[];
  programas: { id: string; clave: string; nombre: string; centro_gestor_id: string }[];
  usuarios: { id: string; usuario: string; nombre: string; tipo: string }[];
  asignaciones: [string, string][];
};
const k = (u: string, p: string) => `${u}|${p}`;

export function Matriz() {
  const tipoSesion = useTipo();
  const [ejercicio, setEjercicio] = useState(String(new Date().getFullYear()));
  const [centro, setCentro] = useState("");
  const [tipo, setTipo] = useState("");
  const [q, setQ] = useState("");
  const [datos, setDatos] = useState<Datos | null>(null);
  const [centros, setCentros] = useState<Datos["centros_gestores"]>([]);
  const [original, setOriginal] = useState<Set<string>>(new Set());
  const [marcas, setMarcas] = useState<Set<string>>(new Set());
  const [elegidos, setElegidos] = useState<Set<string>>(new Set()); // usuarios seleccionados para los atajos de grupo
  const [confirmar, setConfirmar] = useState(false);
  const [guardando, setGuardando] = useState(false);

  const pendientes = useMemo(() => {
    const altas = [...marcas].filter((x) => !original.has(x));
    const bajas = [...original].filter((x) => !marcas.has(x));
    return { altas, bajas };
  }, [marcas, original]);
  const sucio = pendientes.altas.length + pendientes.bajas.length > 0;

  const cargar = useCallback(async () => {
    const p = new URLSearchParams({ ejercicio });
    if (centro) p.set("centro_gestor_id", centro);
    if (tipo) p.set("tipo", tipo);
    if (q.trim()) p.set("q", q.trim());
    const d: Datos = await api(`/api/usuarios/matriz?${p}`);
    setDatos(d);
    const s = new Set(d.asignaciones.map(([u, pr]) => k(u, pr)));
    setOriginal(s);
    setMarcas(new Set(s));
    setElegidos(new Set());
  }, [ejercicio, centro, tipo, q]);

  useEffect(() => {
    const t = setTimeout(() => cargar().catch((e) => toast.error(mensajeError(e))), 250);
    return () => clearTimeout(t);
  }, [cargar]);
  useEffect(() => { api(`/api/centros-gestores?activo=true`).then(setCentros).catch(() => {}); }, []);

  /** Cambiar un filtro recarga la matriz y descarta lo no guardado: se confirma antes. */
  const filtro = (set: (v: string) => void) => (v: string) => {
    if (sucio) {
      if (!window.confirm("Hay cambios sin guardar que se perderán. ¿Continuar?")) return;
      setMarcas(new Set(original));
    }
    set(v);
  };

  if (!puede.gestionarUsuarios(tipoSesion)) return <p className="text-muted">Sin acceso a este módulo.</p>;

  const usuarios = datos?.usuarios ?? [];
  const programas = datos?.programas ?? [];
  const grupos = (datos?.centros_gestores ?? []).map((c) => ({ c, ps: programas.filter((p) => p.centro_gestor_id === c.id) }));

  /** Marca o desmarca un conjunto de celdas: si todas ya están marcadas, las quita; si no, las marca. */
  function alternarCeldas(pares: [string, string][]) {
    setMarcas((m) => {
      const n = new Set(m);
      const todas = pares.every(([u, p]) => n.has(k(u, p)));
      pares.forEach(([u, p]) => (todas ? n.delete(k(u, p)) : n.add(k(u, p))));
      return n;
    });
  }
  const celda = (u: string, p: string) => alternarCeldas([[u, p]]);
  const fila = (u: string) => alternarCeldas(programas.map((p) => [u, p.id]));
  const columna = (p: string) => alternarCeldas(usuarios.map((u) => [u.id, p]));
  const grupo = (ps: { id: string }[]) => { // "para usuarios seleccionados" (si no hay, todos los visibles)
    const us = elegidos.size ? usuarios.filter((u) => elegidos.has(u.id)) : usuarios;
    alternarCeldas(us.flatMap((u) => ps.map((p) => [u.id, p.id] as [string, string])));
  };

  async function guardar() {
    setGuardando(true);
    const par = (x: string) => { const [usuario_id, programa_id] = x.split("|"); return { usuario_id, programa_id }; };
    try {
      const r = await api<{ resumen: string }>("/api/usuarios/matriz", { method: "POST", json: { altas: pendientes.altas.map(par), bajas: pendientes.bajas.map(par) } });
      toast.success(`Matriz guardada: ${r.resumen}`);
      setConfirmar(false);
      await cargar();
    } catch (e) { toast.error(mensajeError(e)); }
    setGuardando(false);
  }

  const nombreU = new Map(usuarios.map((u) => [u.id, u.nombre]));
  const nombreP = new Map(programas.map((p) => [p.id, p.clave]));
  const lineas = (xs: string[]) => xs.map((x) => { const [u, p] = x.split("|"); return `${nombreU.get(u) ?? u} — ${nombreP.get(p) ?? p}`; });

  return (
    <>
      <h3 className="page-heading">Matriz de usuarios y programas</h3>
      <div className="panel"><div className="panel-body">
        <div className="toolbar">
          <input type="number" className="form-control" style={{ maxWidth: 110 }} title="Ejercicio fiscal" value={ejercicio} onChange={(e) => filtro(setEjercicio)(e.target.value)} />
          <select className="form-control" style={{ maxWidth: 260 }} value={centro} onChange={(e) => filtro(setCentro)(e.target.value)}>
            <option value="">Centro gestor: todos</option>
            {centros.map((c) => <option key={c.id} value={c.id}>{c.clave} — {c.nombre}</option>)}
          </select>
          <select className="form-control" style={{ maxWidth: 220 }} value={tipo} onChange={(e) => filtro(setTipo)(e.target.value)}>
            <option value="">Tipo: todos</option>
            {TIPOS.map((t) => <option key={t.valor} value={t.valor}>{t.nombre}</option>)}
          </select>
          <input className="form-control" style={{ maxWidth: 220 }} placeholder="Buscar usuario" value={q} onChange={(e) => filtro(setQ)(e.target.value)} />
          <span className="spacer" />
          <a className="btn btn-default" href="/catalogos/usuarios"><i className="fa fa-arrow-left" /> Usuarios</a>
          <button className="btn btn-success" disabled={!sucio} onClick={() => setConfirmar(true)}>
            <i className="fa fa-save" /> Guardar{sucio ? ` (${pendientes.altas.length + pendientes.bajas.length})` : ""}</button>
        </div>
        <p className="help-block" style={{ marginBottom: 12 }}>
          Clic en el nombre de un usuario marca su fila; en la clave de un programa, su columna; en un centro gestor, todo el grupo
          (para los usuarios con la casilla marcada; si no hay ninguno, para todos los visibles).</p>
        <div className="table-responsive" style={{ maxHeight: "65vh" }}>
          <table className="table table-bordered table-condensed" style={{ marginBottom: 0 }}>
            <thead>
              <tr>
                <th rowSpan={2} style={{ minWidth: 40 }} title="Seleccionar usuarios para los atajos de grupo">
                  <input type="checkbox" checked={!!usuarios.length && elegidos.size === usuarios.length}
                    onChange={() => setElegidos(elegidos.size === usuarios.length ? new Set() : new Set(usuarios.map((u) => u.id)))} /></th>
                <th rowSpan={2} style={{ minWidth: 220 }}>Usuario</th>
                {grupos.filter((g) => g.ps.length).map(({ c, ps }) => (
                  <th key={c.id} colSpan={ps.length} className="text-center" style={{ cursor: "pointer" }} onClick={() => grupo(ps)}
                    title="Marcar/desmarcar el grupo">{c.clave} — {c.nombre}</th>))}
              </tr>
              <tr>{grupos.flatMap(({ ps }) => ps).map((p) => (
                <th key={p.id} className="text-center" style={{ cursor: "pointer", minWidth: 60 }} onClick={() => columna(p.id)} title={p.nombre}>{p.clave}</th>))}</tr>
            </thead>
            <tbody>
              {datos === null && <tr><td colSpan={3} className="text-center text-muted">Cargando…</td></tr>}
              {datos && !programas.length && <tr><td colSpan={3} className="text-center text-muted">No hay programas activos en el ejercicio {ejercicio}</td></tr>}
              {programas.length > 0 && usuarios.map((u) => (
                <tr key={u.id}>
                  <td><input type="checkbox" checked={elegidos.has(u.id)} onChange={() => setElegidos((s) => { const n = new Set(s); n.has(u.id) ? n.delete(u.id) : n.add(u.id); return n; })} /></td>
                  <td style={{ cursor: "pointer" }} onClick={() => fila(u.id)}>{u.nombre} <small className="text-muted">({nombreTipo(u.tipo)})</small></td>
                  {grupos.flatMap(({ ps }) => ps).map((p) => {
                    const cambio = marcas.has(k(u.id, p.id)) !== original.has(k(u.id, p.id));
                    return <td key={p.id} className="text-center" style={cambio ? { background: "#fcf8e3" } : undefined}>
                      <input type="checkbox" checked={marcas.has(k(u.id, p.id))} onChange={() => celda(u.id, p.id)} /></td>;
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div></div>

      {confirmar && <Modal titulo="Confirmar cambios en la matriz" size="lg" onClose={() => setConfirmar(false)} footer={<>
        <button className="btn btn-default" onClick={() => setConfirmar(false)}>Seguir editando</button>
        <button className="btn btn-success" onClick={guardar} disabled={guardando}>Aplicar cambios</button></>}>
        <p><strong>{pendientes.altas.length}</strong> asignaciones nuevas, <strong>{pendientes.bajas.length}</strong> retiradas.
          Se aplican todas juntas o ninguna.</p>
        <div className="row">
          <div className="col-sm-6"><h5 className="text-success">Se asignan</h5>
            <ul style={{ maxHeight: 220, overflowY: "auto", paddingLeft: 18 }}>{lineas(pendientes.altas).map((l, i) => <li key={i}>{l}</li>)}</ul></div>
          <div className="col-sm-6"><h5 className="text-danger">Se retiran</h5>
            <ul style={{ maxHeight: 220, overflowY: "auto", paddingLeft: 18 }}>{lineas(pendientes.bajas).map((l, i) => <li key={i}>{l}</li>)}</ul></div>
        </div>
      </Modal>}
    </>
  );
}
