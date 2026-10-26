/** Módulo Estadísticas (Fase 3). Todo el cálculo (cumplimiento, color, conteos) lo hace la API;
 *  aquí solo se piden y se pintan. */
import { useEffect, useState } from "react";

export type ColorConteo = "verde" | "amarillo" | "rojo" | "gris";
export const COLORES: ColorConteo[] = ["verde", "amarillo", "rojo", "gris"];
export const COLOR_ETIQUETA: Record<ColorConteo, string> = { verde: "Verde", amarillo: "Amarillo", rojo: "Rojo", gris: "Gris" };
/** Mismos colores del semáforo de Inicio (theme.css). */
export const COLOR_HEX: Record<ColorConteo, string> = { verde: "#5cc691", amarillo: "#f1c500", rojo: "#e55957", gris: "#bdbdbd" };

export type TipoCumplimiento = "obtenido" | "co_ce";
export const TIPOS_CUMPLIMIENTO: { valor: TipoCumplimiento; nombre: string }[] = [
  { valor: "obtenido", nombre: "Cumplimiento Obtenido" },
  { valor: "co_ce", nombre: "(C.O / C.E) * 100" },
];

export type Grupo = { id: string | null; nombre: string; verde: number; amarillo: number; rojo: number; gris: number; total: number };
export type Opciones = {
  anios: number[];
  centros_gestores: { id: string; clave: string; nombre: string }[];
  ejes: { id: string; clave: string; nombre: string }[];
  programas: { id: string; clave: string; nombre: string; centro_gestor_id: string }[];
};
export type DetalleIndicador = {
  indicador_id: string; nombre: string; programa: string; dependencia: string; eje: string | null;
  cumplimiento: number | null; color: ColorConteo;
};

export const pct = (n: number, total: number) => (total ? (n * 100) / total : 0);
export const fmtPct = (v: number | null) => (v === null || v === undefined ? "—" : `${v.toFixed(2)} %`);

/** Query string con arreglos estándar (`clave[]=a&clave[]=b`); omite vacíos. */
export function qs(params: Record<string, string | number | string[] | null | undefined>) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === null || v === undefined || v === "") continue;
    if (Array.isArray(v)) v.forEach((x) => p.append(`${k}[]`, x));
    else p.set(k, String(v));
  }
  return p.toString();
}

/** Estado de UI que sobrevive solo mientras dure la sesión de navegación (sessionStorage; nada en backend). */
export function useSesion<T extends string>(clave: string, inicial: T): [T, (v: T) => void] {
  const [v, setV] = useState<T>(inicial);
  useEffect(() => { try { const g = sessionStorage.getItem(`estadisticas:${clave}`); if (g) setV(g as T); } catch { /* sin storage */ } }, [clave]);
  return [v, (n: T) => { setV(n); try { sessionStorage.setItem(`estadisticas:${clave}`, n); } catch { /* sin storage */ } }];
}

/** Descarga un .xlsx respetando errores de la API (403, 422…) en lugar de navegar a su JSON. */
export async function descargar(url: string, nombre: string) {
  const res = await fetch(url);
  if (!res.ok) {
    const d = await res.json().catch(() => null);
    throw new Error(d?.mensaje ?? "No se pudo generar el archivo");
  }
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = res.headers.get("content-disposition")?.match(/filename="([^"]+)"/)?.[1] ?? nombre;
  a.click();
  URL.revokeObjectURL(a.href);
}

/** Año seleccionado; arranca en el año más reciente con datos en el alcance del usuario. */
export function useAnio(op: Opciones): [string, (v: string) => void] {
  return useState(String(op.anios[0] ?? new Date().getFullYear()));
}
