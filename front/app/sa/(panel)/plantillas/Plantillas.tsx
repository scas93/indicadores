"use client";
import { useCallback, useEffect, useState } from "react";
import { Modal } from "@/components/Modal";
import { toast } from "@/components/Toasts";
import { ApiError, api } from "@/lib/api.client";

type Row = Record<string, any>;
type Cfg = {
  tipo: string; label: string;
  extras?: { key: string; label: string; type?: "number" }[];
  niveles?: { value: string; label: string; padre?: string }[];
};

const TABS: Cfg[] = [
  { tipo: "conac", label: "CONAC", niveles: [
    { value: "capitulo", label: "Capítulos" },
    { value: "partida", label: "Partidas", padre: "capitulo" },
    { value: "partida_especifica", label: "Partidas específicas", padre: "partida" },
    { value: "articulo", label: "Artículos", padre: "partida_especifica" }] },
  { tipo: "geografia", label: "Geografía", niveles: [
    { value: "estado", label: "Estados" },
    { value: "municipio", label: "Municipios", padre: "estado" },
    { value: "localidad", label: "Localidades", padre: "municipio" }] },
  { tipo: "frecuencia", label: "Frecuencias" },
  { tipo: "dimension", label: "Dimensiones" },
  { tipo: "algoritmo", label: "Algoritmos" },
  { tipo: "grupo_edad", label: "Grupos de edad", extras: [
    { key: "edad_min", label: "Edad mín.", type: "number" }, { key: "edad_max", label: "Edad máx.", type: "number" }] },
  { tipo: "nivel_socioeconomico", label: "Niveles socioeconómicos" },
];

// Columna del padre en cada nivel (para crear) y filtro del listado
const PADRE_KEY: Record<string, string> = { "conac": "padre_id", "geografia:municipio": "estado_id", "geografia:localidad": "municipio_geo_id" };

function Tabla({ cfg }: { cfg: Cfg }) {
  const [nivel, setNivel] = useState(cfg.niveles?.[0].value ?? "");
  const [filas, setFilas] = useState<Row[] | null>(null);
  const [q, setQ] = useState("");
  const [estados, setEstados] = useState<Row[]>([]);       // geografía: filtro/selector de estado
  const [estadoSel, setEstadoSel] = useState("");
  const [munis, setMunis] = useState<Row[]>([]);           // geografía: localidad -> municipio
  const [muniSel, setMuniSel] = useState("");
  const [modal, setModal] = useState<null | { fila?: Row }>(null);
  const [borrar, setBorrar] = useState<Row | null>(null);

  const nv = cfg.niveles?.find((n) => n.value === nivel);
  const esGeo = cfg.tipo === "geografia";
  const padreFiltro = esGeo ? (nivel === "municipio" ? estadoSel : nivel === "localidad" ? muniSel : "") : "";
  const bloqueado = esGeo && nivel !== "estado" && !padreFiltro; // evita listar el catálogo nacional entero

  const url = useCallback((n: string, extra = "") =>
    `/api/admin/plantillas/${cfg.tipo}?${new URLSearchParams({ ...(n ? { nivel: n } : {}) })}${extra}`, [cfg.tipo]);

  const cargar = useCallback(async () => {
    if (bloqueado) return void setFilas([]);
    const p = new URLSearchParams();
    if (nivel) p.set("nivel", nivel);
    if (q) p.set("q", q);
    if (padreFiltro) p.set("padre_id", padreFiltro);
    setFilas(null);
    setFilas(await api(`/api/admin/plantillas/${cfg.tipo}?${p}`));
  }, [cfg.tipo, nivel, q, padreFiltro, bloqueado]);

  useEffect(() => { const t = setTimeout(() => cargar().catch(() => toast.error("No se pudo cargar")), q ? 300 : 0); return () => clearTimeout(t); }, [cargar, q]);
  useEffect(() => { if (esGeo) api(`/api/admin/plantillas/geografia?nivel=estado`).then(setEstados); }, [esGeo]);
  useEffect(() => {
    setMuniSel("");
    if (esGeo && nivel === "localidad" && estadoSel)
      api(`/api/admin/plantillas/geografia?nivel=municipio&padre_id=${estadoSel}`).then(setMunis);
  }, [esGeo, nivel, estadoSel]);

  async function eliminar(f: Row) {
    try {
      await api(`/api/admin/plantillas/${cfg.tipo}/${f.id}${nivel ? `?nivel=${nivel}` : ""}`, { method: "DELETE" });
      toast.success("Eliminado");
      setBorrar(null);
      cargar();
    } catch (e) { toast.error(e instanceof ApiError ? e.message : "No se pudo eliminar"); setBorrar(null); }
  }

  const extras = cfg.extras ?? [];
  return (
    <>
      <div className="toolbar">
        {cfg.niveles && (
          <select className="form-control" style={{ width: "auto" }} value={nivel} onChange={(e) => setNivel(e.target.value)}>
            {cfg.niveles.map((n) => <option key={n.value} value={n.value}>{n.label}</option>)}
          </select>
        )}
        {esGeo && nivel !== "estado" && (
          <select className="form-control" style={{ width: "auto" }} value={estadoSel} onChange={(e) => setEstadoSel(e.target.value)}>
            <option value="">Estado…</option>
            {estados.map((e) => <option key={e.id} value={e.id}>{e.nombre}</option>)}
          </select>
        )}
        {esGeo && nivel === "localidad" && (
          <select className="form-control" style={{ width: "auto" }} value={muniSel} onChange={(e) => setMuniSel(e.target.value)} disabled={!estadoSel}>
            <option value="">Municipio…</option>
            {munis.map((e) => <option key={e.id} value={e.id}>{e.nombre}</option>)}
          </select>
        )}
        <input className="form-control" style={{ maxWidth: 260 }} placeholder="Buscar" value={q} onChange={(e) => setQ(e.target.value)} />
        <span className="spacer" />
        <button className="btn btn-success" onClick={() => setModal({})} disabled={bloqueado}><i className="fa fa-plus" /> Nuevo</button>
      </div>
      <div className="table-responsive">
        <table className="table table-hover">
          <thead><tr><th style={{ width: 120 }}>Clave</th><th>Nombre</th>{extras.map((e) => <th key={e.key}>{e.label}</th>)}<th style={{ width: 100 }}>Acciones</th></tr></thead>
          <tbody>
            {bloqueado && <tr><td colSpan={3 + extras.length} className="text-center text-muted">Elige {nivel === "localidad" ? "estado y municipio" : "un estado"} para ver el catálogo</td></tr>}
            {!bloqueado && filas === null && <tr><td colSpan={3 + extras.length} className="text-center text-muted">Cargando…</td></tr>}
            {!bloqueado && filas && !filas.length && <tr><td colSpan={3 + extras.length} className="text-center text-muted">Sin registros</td></tr>}
            {filas?.map((f) => (
              <tr key={f.id}>
                <td>{f.clave}</td><td>{f.nombre}</td>{extras.map((e) => <td key={e.key}>{f[e.key] ?? ""}</td>)}
                <td>
                  <button className="btn btn-xs btn-info" title="Editar" onClick={() => setModal({ fila: f })}><i className="fa fa-pencil" /></button>{" "}
                  <button className="btn btn-xs btn-danger" title="Eliminar" onClick={() => setBorrar(f)}><i className="fa fa-trash" /></button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {filas && filas.length >= 500 && <p className="help-block">Se muestran los primeros 500; usa el buscador para acotar.</p>}

      {modal && <FormModal cfg={cfg} nivel={nivel} nv={nv} fila={modal.fila} padreInicial={padreFiltro}
        onClose={() => setModal(null)} onGuardado={() => { setModal(null); cargar(); }} />}
      {borrar && <Modal titulo="Eliminar" onClose={() => setBorrar(null)} footer={<>
        <button className="btn btn-default" onClick={() => setBorrar(null)}>Cancelar</button>
        <button className="btn btn-danger" onClick={() => eliminar(borrar)}>Eliminar</button></>}>
        <p>¿Eliminar <strong>{borrar.clave} — {borrar.nombre}</strong>? Solo se puede si nada lo referencia. Las copias ya hechas en municipios no se afectan.</p>
      </Modal>}
    </>
  );
}

function FormModal({ cfg, nivel, nv, fila, padreInicial, onClose, onGuardado }: {
  cfg: Cfg; nivel: string; nv?: { padre?: string }; fila?: Row; padreInicial: string; onClose: () => void; onGuardado: () => void;
}) {
  const padreCol = PADRE_KEY[cfg.tipo === "conac" ? "conac" : `${cfg.tipo}:${nivel}`];
  const [v, setV] = useState<Row>({ clave: fila?.clave ?? "", nombre: fila?.nombre ?? "",
    ...Object.fromEntries((cfg.extras ?? []).map((e) => [e.key, fila?.[e.key] ?? ""])),
    ...(padreCol ? { [padreCol]: fila?.[padreCol] ?? padreInicial } : {}) });
  const [padres, setPadres] = useState<Row[]>([]);
  const [errores, setErrores] = useState<Record<string, string>>({});

  useEffect(() => { // opciones del padre (conac: nivel anterior; geografía municipio: estados)
    if (cfg.tipo === "conac" && nv?.padre) api(`/api/admin/plantillas/conac?nivel=${nv.padre}`).then(setPadres);
    if (cfg.tipo === "geografia" && nivel === "municipio") api(`/api/admin/plantillas/geografia?nivel=estado`).then(setPadres);
  }, [cfg.tipo, nivel, nv?.padre]);

  async function guardar() {
    setErrores({});
    const body: Row = { ...v };
    for (const e of cfg.extras ?? []) body[e.key] = v[e.key] === "" ? null : Number(v[e.key]);
    if (cfg.tipo === "conac") body.nivel = nivel;
    for (const k of Object.keys(body)) if (body[k] === "") body[k] = null;
    body.clave = v.clave; body.nombre = v.nombre;
    const q = nivel ? `?nivel=${nivel}` : "";
    try {
      if (fila) await api(`/api/admin/plantillas/${cfg.tipo}/${fila.id}${q}`, { method: "PATCH", json: body });
      else await api(`/api/admin/plantillas/${cfg.tipo}${q}`, { method: "POST", json: body });
      toast.success("Guardado");
      onGuardado();
    } catch (e) {
      if (e instanceof ApiError) { setErrores(e.campos); toast.error(e.message); }
    }
  }

  const campo = (k: string, label: string, type = "text") => (
    <div className={`form-group${errores[k] ? " has-error" : ""}`}>
      <label className="control-label">{label}</label>
      <input type={type} className="form-control" value={v[k] ?? ""} onChange={(e) => setV({ ...v, [k]: e.target.value })} />
      {errores[k] && <span className="help-block">{errores[k]}</span>}
    </div>
  );
  const mostrarPadre = padreCol && (cfg.tipo === "conac" ? !!nv?.padre : nivel === "municipio");
  return (
    <Modal titulo={`${fila ? "Editar" : "Nuevo"} — ${cfg.label}`} onClose={onClose} footer={<>
      <button className="btn btn-default" onClick={onClose}>Cancelar</button>
      <button className="btn btn-success" onClick={guardar}>Guardar</button></>}>
      {campo("clave", "Clave")}
      {campo("nombre", "Nombre")}
      {(cfg.extras ?? []).map((e) => <div key={e.key}>{campo(e.key, e.label, e.type)}</div>)}
      {mostrarPadre && (
        <div className="form-group">
          <label className="control-label">{cfg.tipo === "conac" ? "Pertenece a" : "Estado"}</label>
          <select className="form-control" value={v[padreCol!] ?? ""} onChange={(e) => setV({ ...v, [padreCol!]: e.target.value })}>
            <option value="">— Seleccione —</option>
            {padres.map((p) => <option key={p.id} value={p.id}>{p.clave} — {p.nombre}</option>)}
          </select>
        </div>
      )}
      {cfg.tipo === "geografia" && nivel === "localidad" && <p className="help-block">La localidad se crea en el municipio seleccionado en el filtro.</p>}
    </Modal>
  );
}

export function Plantillas() {
  const [tab, setTab] = useState(0);
  return (
    <>
      <h3 className="page-heading">Plantillas globales</h3>
      <div className="panel">
        <div className="panel-heading tab-dark" style={{ padding: "12px 20px 0" }}>
          <ul className="nav nav-tabs" style={{ margin: "0 -20px", padding: "0 20px" }}>
            {TABS.map((t, i) => (
              <li key={t.tipo} className={i === tab ? "active" : ""}>
                <a href="#" onClick={(e) => { e.preventDefault(); setTab(i); }}>{t.label}</a>
              </li>
            ))}
          </ul>
        </div>
        <div className="panel-body">
          <p className="help-block" style={{ marginTop: 0 }}>Editar una plantilla global no afecta las copias que ya tienen los municipios existentes.</p>
          <Tabla key={TABS[tab].tipo} cfg={TABS[tab]} />
        </div>
      </div>
    </>
  );
}
