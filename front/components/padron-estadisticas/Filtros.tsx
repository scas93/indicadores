"use client";
import { useCallback, useEffect, useState } from "react";
import { Autocompleto, type OpcionAc } from "../Autocompleto";
import { Campo, mensajeError } from "../Campo";
import { toast } from "../Toasts";
import { api } from "@/lib/api.client";
import { qs } from "@/lib/estadisticas";

type Fila = { id: string; [k: string]: any };
type Sel = { id: string; texto: string };
const VACIO: Sel = { id: "", texto: "" };

/** Filtros que comparten los tres reportes del Padrón. Apoyo, Descripción, Estado, Municipio y Localidad se eligen
 *  con "Escriba y Seleccione…"; al cambiar uno se vacían los que dependen de él. */
export function useFiltrosPadron() {
  const [programas, setProgramas] = useState<string[]>([]);
  const [apoyo, setApoyo] = useState<Sel>(VACIO);
  const [desc, setDesc] = useState<Sel>(VACIO);
  const [estado, setEstado] = useState<Sel>(VACIO);
  const [municipio, setMunicipio] = useState<Sel>(VACIO);
  const [localidad, setLocalidad] = useState<Sel>(VACIO);
  const params = useCallback(() => ({
    "programa_ids": programas, apoyo_id: apoyo.id, descripcion_apoyo_id: desc.id, estado_id: estado.id,
    municipio_id: municipio.id, localidad_id: localidad.id,
  }), [programas, apoyo, desc, estado, municipio, localidad]);
  return { programas, setProgramas, apoyo, setApoyo, desc, setDesc, estado, setEstado, municipio, setMunicipio, localidad, setLocalidad, params };
}
export type FiltrosPadron = ReturnType<typeof useFiltrosPadron>;
/** Query string de los filtros comunes más lo propio de cada reporte (`programa_ids[]=…&apoyo_id=…`). */
export const consulta = (f: FiltrosPadron, extra: Record<string, string | number | null | undefined> = {}) =>
  qs({ ...f.params(), ...extra });

function CampoAc({ label, valor, onCambio, buscar, deshabilitado }: {
  label: string; valor: Sel; onCambio: (s: Sel) => void; buscar: (q: string) => Promise<OpcionAc[]>; deshabilitado?: boolean;
}) {
  return (
    <Campo label={label}>
      <Autocompleto texto={valor.texto} ariaLabel={label} placeholder="Escriba y Seleccione…" deshabilitado={deshabilitado}
        onTexto={(t) => onCambio({ id: "", texto: t })} buscar={buscar} onElegir={(o) => onCambio({ id: o.valor, texto: o.etiqueta })} />
    </Campo>
  );
}

const coincide = (q: string, ...textos: string[]) => textos.join(" ").toLowerCase().includes(q.trim().toLowerCase());

export function FiltrosPadronUI({ f }: { f: FiltrosPadron }) {
  const [programas, setProgramas] = useState<Fila[]>([]);
  const [apoyos, setApoyos] = useState<Fila[]>([]);
  const [descs, setDescs] = useState<Fila[]>([]);
  const [estados, setEstados] = useState<Fila[]>([]);
  const falla = (e: unknown) => toast.error(mensajeError(e));
  useEffect(() => {
    api<Fila[]>("/api/padron/programas").then(setProgramas).catch(falla);
    api<Fila[]>("/api/apoyos").then(setApoyos).catch(falla);
    api<Fila[]>("/api/descripciones-apoyo").then(setDescs).catch(falla);
    api<Fila[]>("/api/geo/estados").then(setEstados).catch(falla);
  }, []);

  const lim = (l: OpcionAc[]) => l.slice(0, 20);
  const apoyosVis = f.programas.length ? apoyos.filter((a) => f.programas.includes(a.programa_id)) : apoyos;
  const descsVis = f.apoyo.id ? descs.filter((d) => d.apoyo_id === f.apoyo.id) : descs;

  return (
    <div className="pe-filtros">
      <Campo label="Programas">
        <select multiple size={4} className="form-control" aria-label="Programas" value={f.programas}
          onChange={(e) => { f.setProgramas(Array.from(e.target.selectedOptions, (o) => o.value)); f.setApoyo(VACIO); f.setDesc(VACIO); }}>
          {programas.map((p) => <option key={p.id} value={p.id}>{p.clave} — {p.nombre}</option>)}
        </select>
        <p className="pe-nota">Mantenga presionado Ctrl/Comando para seleccionar varias opciones</p>
      </Campo>
      <CampoAc label="Apoyo" valor={f.apoyo} onCambio={(s) => { f.setApoyo(s); f.setDesc(VACIO); }}
        buscar={async (q) => lim(apoyosVis.filter((a) => coincide(q, a.clave, a.nombre)).map((a) => ({ valor: a.id, etiqueta: a.nombre })))} />
      <CampoAc label="Descripción Apoyo" valor={f.desc} onCambio={f.setDesc}
        buscar={async (q) => lim(descsVis.filter((d) => coincide(q, d.clave, d.nombre)).map((d) => ({ valor: d.id, etiqueta: d.nombre })))} />
      <CampoAc label="Estado" valor={f.estado} onCambio={(s) => { f.setEstado(s); f.setMunicipio(VACIO); f.setLocalidad(VACIO); }}
        buscar={async (q) => lim(estados.filter((e) => coincide(q, e.nombre)).map((e) => ({ valor: e.id, etiqueta: e.nombre })))} />
      <CampoAc label="Municipio" valor={f.municipio} onCambio={(s) => { f.setMunicipio(s); f.setLocalidad(VACIO); }}
        buscar={async (q) => lim((await api<Fila[]>(`/api/geo/municipios?${qs({ estado_id: f.estado.id, nombre: q.trim() })}`))
          .map((m) => ({ valor: m.id, etiqueta: m.nombre })))} />
      <CampoAc label="Localidad" valor={f.localidad} onCambio={f.setLocalidad}
        buscar={async (q) => (q.trim().length < 2 && !f.municipio.id ? [] : lim((await api<Fila[]>(`/api/geo/localidades?${qs({
          estado_id: f.estado.id, municipio_id: f.municipio.id, nombre: q.trim() })}`)).map((l) => ({ valor: l.id, etiqueta: l.nombre }))))} />
    </div>
  );
}

export function useHoy() {
  const [hoy, setHoy] = useState("");
  useEffect(() => { api<{ hoy: string }>("/api/padron/contexto").then((c) => setHoy(c.hoy)).catch((e) => toast.error(mensajeError(e))); }, []);
  return hoy;
}
