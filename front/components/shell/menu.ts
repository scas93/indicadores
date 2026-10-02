/** Definición de menú compartida por los dos paneles. El cascarón (AppShell) es único;
 *  lo ÚNICO que cambia entre /sa y /mun, y entre tipos de usuario, es qué items existen. */
export type TipoUsuario =
  | "informes" | "padron" | "presupuestacion" | "control_presupuestal"
  | "indicadores" | "alcalde" | "administrador";

export type Item = {
  label: string;
  icon?: string;          // clase FontAwesome 4 (solo primer nivel)
  href?: string;          // sin href = deshabilitado ("próximamente"), nunca oculto
  tipos?: TipoUsuario[];  // quién lo ve; omitido = todos. administrador siempre ve todo.
  hijos?: Item[];
};

export type Menu = Item[];

/** "N.- NOMBRE" tal como lo muestra el header del sistema de referencia. */
export const TIPO_ETIQUETA: Record<TipoUsuario, string> = {
  informes: "1.- INFORMES",
  padron: "2.- PADRON DE BENEFICIARIOS",
  presupuestacion: "3.- PRESUPUESTACION",
  control_presupuestal: "4.- CONTROL PRESUPUESTAL",
  indicadores: "5.- INDICADORES",
  alcalde: "6.- ALCALDE",
  administrador: "7.- ADMINISTRADOR",
};

const T: Record<string, TipoUsuario[]> = {
  informes: ["informes"], padron: ["padron"], presup: ["presupuestacion"], ctrl: ["control_presupuestal"],
  ind: ["indicadores"], alc: ["alcalde"],
};
const mir: TipoUsuario[] = [...T.informes, ...T.alc];

/** Menú del municipio. Estructura y orden de las capturas (usuarios 3 y 4); las secciones que las
 *  capturas no cubren (tipos 1, 2, 5, 6 y fases futuras) se infieren de la tabla de tipos de la Fase 1. */
export const MENU_MUNICIPIO: Menu = [
  { label: "Inicio", icon: "fa-home" },
  {
    label: "Catálogos", icon: "fa-book", hijos: [
      { label: "Centros gestores", tipos: mir }, { label: "Ejes", tipos: mir }, { label: "Subtemas", tipos: mir },
      { label: "Estrategias", tipos: mir }, { label: "Frecuencias", tipos: mir },
      { label: "Programas", tipos: [...T.informes, ...T.presup, ...T.alc] },
      { label: "Capitulos", tipos: T.presup }, { label: "Partidas", tipos: T.presup },
      { label: "Partidas Especificas", tipos: T.presup }, { label: "Articulos", tipos: T.presup },
      { label: "Apoyos", tipos: T.padron }, { label: "Descripciones de apoyo", tipos: T.padron },
      { label: "Grupos de edad", tipos: T.padron }, { label: "Niveles socioeconómicos", tipos: T.padron },
      { label: "Municipios", tipos: T.padron }, { label: "Localidades", tipos: T.padron },
      { label: "Colonias", tipos: T.padron },
      { label: "Usuarios", tipos: ["informes", "padron", "presupuestacion", "indicadores", "alcalde"] },
    ],
  },
  { label: "Padrón de Beneficiarios", icon: "fa-users", tipos: T.padron },
  {
    label: "Estadísticas", icon: "fa-bar-chart",
    tipos: ["informes", "padron", "presupuestacion", "control_presupuestal", "alcalde"], hijos: [
      { label: "Dependencias", tipos: [...mir, ...T.presup, ...T.ctrl] },
      { label: "Ejes", tipos: mir }, { label: "Cumplimiento de Metas", tipos: mir },
      { label: "Consolidado", tipos: mir }, { label: "Cuenta Pública", tipos: mir },
      { label: "Transparencia", tipos: mir },
      { label: "PbR", tipos: [...T.presup, ...T.ctrl, ...T.alc] },
      { label: "Estadísticas del padrón", tipos: T.padron },
    ],
  },
  { label: "Techo Presupuestal", icon: "fa-money", tipos: T.presup },
  {
    label: "Configuración", icon: "fa-cog", tipos: mir, hijos: [
      { label: "Login", tipos: T.informes }, { label: "Meses de avances", tipos: mir },
    ],
  },
  // Fase 6 (por inferencia): módulos que solo ve el administrador. Visibles pero deshabilitados
  // desde la Fase 0 ("nunca ocultos"); las capturas de usuarios 3 y 4 confirman que los demás tipos no los ven.
  { label: "Físico Financiero", icon: "fa-calculator", tipos: [] },
  { label: "Alta de Presupuestación", icon: "fa-plus-square-o", tipos: [] },
  { label: "Clasificación Funcional", icon: "fa-sitemap", tipos: [] },
  { label: "Cancelación de Padrón", icon: "fa-ban", tipos: [] },
];

/** Super admin: mismo lenguaje visual, solo cambian las opciones. */
export const MENU_SUPER_ADMIN: Menu = [
  { label: "Municipios", icon: "fa-building", href: "/" },
  { label: "Plantillas globales", icon: "fa-clone", href: "/plantillas" },
];

/** Filtra por tipo. `administrador` ve todo ("Todo", tabla de tipos). */
export function menuPara(menu: Menu, tipo: TipoUsuario): Menu {
  const ve = (i: Item) => tipo === "administrador" || !i.tipos || i.tipos.includes(tipo);
  return menu.filter(ve).map((i) => (i.hijos ? { ...i, hijos: i.hijos.filter(ve) } : i))
    .filter((i) => !i.hijos || i.hijos.length > 0);
}
