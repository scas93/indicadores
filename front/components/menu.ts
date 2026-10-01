/** Menú lateral con TODAS las secciones del sistema final (spec Fase 0 / Fase 6).
 *  `fase` indica cuándo se construye; mientras no exista queda deshabilitado ("próximamente"),
 *  nunca oculto. Cuando una fase se construya, basta poner `href`. */
export type Item = { label: string; icon?: string; href?: string; fase: number; hijos?: Item[]; titulo?: string };

export const MENU: Item[] = [
  { label: "Inicio", icon: "fa-home", fase: 1 },
  {
    label: "Catálogos", icon: "fa-list-alt", fase: 1, hijos: [
      { label: "Centros gestores", fase: 1 }, { label: "Ejes", fase: 1 }, { label: "Subtemas", fase: 1 },
      { label: "Estrategias", fase: 1 }, { label: "Frecuencias", fase: 1 }, { label: "Programas", fase: 1 },
      { label: "Capítulos", fase: 4 }, { label: "Partidas", fase: 4 },
      { label: "Partidas específicas", fase: 4 }, { label: "Artículos", fase: 4 },
      { label: "Apoyos", fase: 5 }, { label: "Descripciones de apoyo", fase: 5 },
      { label: "Grupos de edad", fase: 5 }, { label: "Niveles socioeconómicos", fase: 5 },
      { label: "Municipios", fase: 5 }, { label: "Localidades", fase: 5 }, { label: "Colonias", fase: 5 },
    ],
  },
  { label: "Padrón de Beneficiarios", icon: "fa-users", fase: 5 },
  {
    label: "Presupuesto", icon: "fa-money", fase: 4, hijos: [
      { label: "Techo Presupuestal", fase: 4 }, { label: "Dependencias y PbR", fase: 4 },
      { label: "Formato PbR", fase: 6 }, { label: "Alta de Presupuestación", fase: 6 },
      { label: "Físico Financiero", fase: 6 }, { label: "Clasificación Funcional", fase: 6 },
    ],
  },
  {
    label: "Estadísticas", icon: "fa-bar-chart", fase: 3, hijos: [
      { label: "Dependencias", fase: 3 }, { label: "Ejes", fase: 3 }, { label: "Cumplimiento de Metas", fase: 3 },
      { label: "Consolidado", fase: 3 }, { label: "Cuenta Pública", fase: 3 }, { label: "Transparencia", fase: 3 },
      { label: "Estadísticas del padrón", fase: 5 },
    ],
  },
  { label: "Cancelación de Padrón", icon: "fa-ban", fase: 6 },
  { label: "Usuarios", icon: "fa-user", fase: 1, hijos: [
      { label: "Listado de usuarios", fase: 1 }, { label: "Matriz de usuarios y programas", fase: 1 } ] },
  {
    label: "Configuración", icon: "fa-cog", fase: 1, hijos: [
      { label: "Login", fase: 1 }, { label: "Meses de avances", fase: 1 },
    ],
  },
];
