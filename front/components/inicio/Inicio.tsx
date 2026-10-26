"use client";
import { useEffect, useState } from "react";
import { mensajeError } from "@/components/Campo";
import { SelectBuscable, type GrupoSelect } from "@/components/SelectBuscable";
import { toast } from "@/components/Toasts";
import { useTipo } from "@/components/TipoContext";
import { api } from "@/lib/api.client";
import type { Programa } from "@/lib/mir";
import { useDescargas } from "@/components/shell/Descargas";
import { ArbolTab } from "./ArbolTab";
import { CapturaTab } from "./CapturaTab";
import { MatrizTab } from "./MatrizTab";

type Pestana = "arbol" | "matriz" | "captura";
const PESTANAS: { id: Pestana; nombre: string }[] = [
  { id: "arbol", nombre: "Árbol de problemas y objetivos" },
  { id: "matriz", nombre: "Matriz de indicadores" },
  { id: "captura", nombre: "Captura de avances" },
];

/** Módulo Inicio: selector de programa (solo los asignados al usuario) + 3 pestañas.
 *  La 4a pestaña (Presupuestación) llega en Fase 4. */
export function Inicio() {
  const tipo = useTipo();
  const [programas, setProgramas] = useState<(Programa & { centro_gestor_id?: string })[] | null>(null);
  const [centros, setCentros] = useState<{ id: string; clave: string; nombre: string }[]>([]);
  const [pid, setPid] = useState("");
  const [tab, setTab] = useState<Pestana>("arbol");
  const { setItems } = useDescargas();

  useEffect(() => {
    if (tipo === "padron") return;
    // /api/programas ya filtra por usuario_programa (administrador y alcalde ven todos). Al entrar no se
    // elige ningún programa: no se carga ninguna pestaña hasta que la persona elija uno.
    Promise.all([api<Programa[]>("/api/programas?activo=true"), api<typeof centros>("/api/centros-gestores")])
      .then(([l, c]) => { setProgramas(l); setCentros(c); })
      .catch((e) => { setProgramas([]); toast.error(mensajeError(e)); });
  }, [tipo]);

  // Las descargas viven en el ícono de nube del encabezado; dependen del programa elegido
  useEffect(() => {
    if (!pid) { setItems([]); return; }
    const g = (ruta: string) => `/api/programas/${pid}/${ruta}`;
    setItems([
      { label: "Árbol de problemas y objetivos", href: g("arbol/descarga?tipo=completo") },
      { label: "Árbol de problemas", href: g("arbol/descarga?tipo=problemas") },
      { label: "Árbol de objetivos", href: g("arbol/descarga?tipo=objetivos") },
      { label: "Matriz de Indicadores de Resultados", href: g("matriz/descarga?tipo=resultados") },
      { label: "Matriz de Cumplimiento de Indicadores", href: g("matriz/descarga?tipo=cumplimiento") },
    ]);
    return () => setItems([]);
  }, [pid, setItems]);

  if (tipo === "padron") return <p className="text-muted">Tu tipo de usuario no tiene acceso al módulo Inicio.</p>;
  // Solo el nombre; si dos programas se llaman igual (mismo programa en varios ejercicios) se desambigua
  // agregando ejercicio y clave solo a esos, para no dejar opciones indistinguibles.
  const repetidos = new Set((programas ?? []).map((p) => p.nombre).filter((n, i, a) => a.indexOf(n) !== i));
  const etiqueta = (p: Programa) => (repetidos.has(p.nombre) ? `${p.nombre} (${p.ejercicio_fiscal} · ${p.clave})` : p.nombre);
  // agrupados por centro gestor: grupos por clave del centro gestor y programas por clave
  const grupos: GrupoSelect[] = centros.slice().sort((a, b) => a.clave.localeCompare(b.clave, "es", { numeric: true }))
    .map((c) => ({
      etiqueta: c.nombre,
      opciones: (programas ?? []).filter((p) => p.centro_gestor_id === c.id)
        .sort((a, b) => a.clave.localeCompare(b.clave, "es", { numeric: true }) || b.ejercicio_fiscal - a.ejercicio_fiscal)
        .map((p) => ({ valor: p.id, etiqueta: etiqueta(p) })),
    })).filter((g) => g.opciones.length > 0);

  return (
    <>
      <div className="inicio-selector">
        <SelectBuscable grupos={grupos} valor={pid} onChange={setPid} placeholder="--Selecciona el programa--" ariaLabel="Programa" />
        {programas?.length === 0 && <p className="text-muted" style={{ marginTop: 8 }}>No tienes programas asignados.</p>}
      </div>
      {pid && (
        <div className="inicio-panel">
          <ul className="nav nav-tabs inicio-tabs">
            {PESTANAS.map((p) => (
              <li key={p.id} className={tab === p.id ? "active" : ""}>
                <a href="#" onClick={(e) => { e.preventDefault(); setTab(p.id); }}>{p.nombre}</a>
              </li>
            ))}
          </ul>
          <div className="inicio-panel-cuerpo">
            {tab === "arbol" && <ArbolTab key={pid} programaId={pid} />}
            {tab === "matriz" && <MatrizTab key={pid} programaId={pid} />}
            {tab === "captura" && <CapturaTab key={pid} programaId={pid} />}
          </div>
        </div>
      )}
    </>
  );
}
