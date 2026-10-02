/** Tipos y catálogos fijos del módulo Inicio (MIR). El cálculo de cumplimiento y semáforo NO vive
 *  aquí: lo hace siempre la API (app/calculo.py) y el front solo lo pinta. */
export type Algoritmo = "a_sobre_b_pct" | "a_sobre_b_menos1_pct" | "a_sobre_b" | "a";
export type ColorSemaforo = "verde" | "amarillo" | "rojo" | "gris" | "sin_color";

export const ALGORITMOS: { valor: Algoritmo; nombre: string }[] = [
  { valor: "a_sobre_b_pct", nombre: "(A / B) × 100" },
  { valor: "a_sobre_b_menos1_pct", nombre: "((A / B) − 1) × 100" },
  { valor: "a_sobre_b", nombre: "A / B" },
  { valor: "a", nombre: "Solo A" },
];
export const nombreAlgoritmo = (a: string | null) => ALGORITMOS.find((x) => x.valor === a)?.nombre ?? "—";
export const DIMENSIONES = [
  { valor: "eficacia", nombre: "Eficacia" }, { valor: "eficiencia", nombre: "Eficiencia" },
  { valor: "calidad", nombre: "Calidad" }, { valor: "economia", nombre: "Economía" },
];
export const TIPOS_INDICADOR = [{ valor: "gestion", nombre: "Gestión" }, { valor: "estrategico", nombre: "Estratégico" }];
export const NIVEL_NOMBRE: Record<string, string> = { fin: "Fin", proposito: "Propósito", componente: "Componente", actividad: "Actividad" };
export const COLOR_NOMBRE: Record<ColorSemaforo, string> = {
  verde: "Verde", amarillo: "Amarillo", rojo: "Rojo", gris: "Sin datos", sin_color: "Fuera de los rangos",
};

export type ProgramaInfo = {
  id: string; ejercicio_fiscal: number; clave: string; nombre: string; centro_gestor: string | null;
  eje: string | null; subtema: string | null; estrategia: string | null; nivel: string | null;
};
export type Programa = { id: string; ejercicio_fiscal: number; clave: string; nombre: string };

export type NodoArbol = { id: string; numero: string; padre_id: string | null; hijos: NodoArbol[]; [k: string]: any };
export type Arbol = {
  programa: ProgramaInfo; encabezado: { problema: string | null; objetivo: string | null };
  causas: NodoArbol[]; efectos: NodoArbol[];
};

export type Rango = { desde: number | null; hasta: number | null };
export type MetaAnual = { anio: number; valor_a_programado: number | null; valor_b_programado: number | null; es_ejercicio_fiscal: boolean };
export type Indicador = {
  id: string; elemento_matriz_id: string;
  ficha: {
    tipo: string; prioritario: boolean; nombre: string; interpretacion: string; dimension: string | null;
    frecuencia_id: string | null; unidad_medida: string; algoritmo: Algoritmo | null; unidad_a: string; unidad_b: string | null;
  };
  metas: { anio_base: number | null; meta_administracion: number | null; anuales: MetaAnual[] };
  rangos: { verde: Rango; amarillo: Rango; rojo: Rango };
};
export type Elemento = {
  id: string; nivel: string; numero: string; resumen_narrativo: string; medios_verificacion: string;
  supuestos: string; evidencia: string | null; indicadores: Indicador[]; actividades?: Elemento[];
};
export type Matriz = { programa: ProgramaInfo; fin: Elemento; proposito: Elemento; componentes: Elemento[] };

export type Resultado = { sumatoria_a: number | null; sumatoria_b: number | null; cumplimiento: number | null; color: ColorSemaforo };

export const fmt = (n: number | null | undefined) =>
  n === null || n === undefined ? "—" : n.toLocaleString("es-MX", { maximumFractionDigits: 2 });
/** "" → null; texto numérico → número. Los campos de captura son strings en el estado. */
export const num = (s: string | number | null | undefined): number | null => {
  if (s === null || s === undefined || String(s).trim() === "") return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
};
export const str = (n: number | null | undefined) => (n === null || n === undefined ? "" : String(n));
