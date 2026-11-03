/** Definición de menú compartida por los dos paneles. El cascarón (AppShell) es único;
 *  lo ÚNICO que cambia entre /sa y /mun, y entre tipos de usuario, es qué items existen. */
export type TipoUsuario = "informes" | "padron" | "administrador";

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
  administrador: "7.- ADMINISTRADOR",
};

const T: Record<string, TipoUsuario[]> = {
  informes: ["informes"], padron: ["padron"],
};
const mir: TipoUsuario[] = T.informes;

/** Menú del municipio. Estructura y orden de las capturas; las secciones que las
 *  capturas no cubren (tipos 1, 2 y fases futuras) se infieren de la tabla de tipos de la Fase 1. */
export const MENU_MUNICIPIO: Menu = [
  { label: "Inicio", icon: "fa-home", href: "/", tipos: T.informes },
  {
    label: "Catálogos", icon: "fa-book", hijos: [
      { label: "Centros gestores", href: "/catalogos/centros-gestores", tipos: mir }, { label: "Ejes", href: "/catalogos/ejes", tipos: mir }, { label: "Subtemas", href: "/catalogos/subtemas", tipos: mir },
      { label: "Estrategias", href: "/catalogos/estrategias", tipos: mir }, { label: "Frecuencias", href: "/catalogos/frecuencias", tipos: mir },
      { label: "Programas", href: "/catalogos/programas", tipos: T.informes },
      { label: "Apoyos", href: "/catalogos/apoyos", tipos: T.padron },
      { label: "Descripción de Apoyo", href: "/catalogos/descripciones-apoyo", tipos: T.padron },
      { label: "Nivel Socioeconómico", href: "/catalogos/niveles-socioeconomicos", tipos: T.padron },
      { label: "Grupo Edad", href: "/catalogos/grupos-edad", tipos: T.padron },
      { label: "Localidades", href: "/catalogos/localidades", tipos: T.padron },
      { label: "Municipios", href: "/catalogos/municipios", tipos: T.padron },
      { label: "Colonias", href: "/catalogos/colonias", tipos: T.padron },
      { label: "Usuarios", href: "/catalogos/usuarios", tipos: ["informes", "padron"] },
    ],
  },
  { label: "Padrón de Beneficiarios", icon: "fa-users", tipos: T.padron },
  {
    label: "Estadísticas", icon: "fa-bar-chart",
    tipos: ["informes", "padron"], hijos: [
      { label: "Dependencias", href: "/estadisticas/dependencias", tipos: mir },
      { label: "Ejes", href: "/estadisticas/ejes", tipos: mir },
      { label: "Cumplimiento de Metas", href: "/estadisticas/cumplimiento-metas", tipos: mir },
      { label: "Consolidado", href: "/estadisticas/consolidado", tipos: mir },
      { label: "Cuenta Pública", href: "/estadisticas/cuenta-publica", tipos: mir },
      { label: "Transparencia", href: "/estadisticas/transparencia", tipos: mir },
      { label: "Estadísticas del padrón", tipos: T.padron },
    ],
  },
  {
    label: "Configuración", icon: "fa-cog", tipos: mir, hijos: [
      { label: "Login", href: "/configuracion/login", tipos: T.informes }, { label: "Meses de avances", href: "/configuracion/meses-avances", tipos: mir },
    ],
  },
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
