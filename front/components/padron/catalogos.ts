/** Los 7 catálogos del Padrón (Fase 5, parte 1): qué buscar, qué columnas mostrar y qué pide el formulario.
 *  Etiquetas, columnas y campos tal como los muestra la referencia. */
export type CampoForm = {
  key: string;
  label: string;
  tipo?: "texto" | "area" | "numero" | "lista" | "buscable";
  /** Ruta de la API que da las opciones (puede depender de otros campos; null = aún sin opciones). */
  fuente?: string | ((f: Record<string, string>) => string | null);
  opcion?: (o: any) => string;
  /** Solo ayuda a elegir (p. ej. el Estado de una localidad): no se envía a la API. */
  virtual?: boolean;
  /** Al cambiar este campo se limpia el campo indicado (Estado -> Municipio). */
  limpia?: string;
  sinOpcion?: string;
  ancho?: number;
  opcional?: boolean;
};

export type CatalogoCfg = {
  ruta: string;                      // /api/<ruta>
  titulo: string;                    // encabezado de la pantalla
  singular: string;                  // "Ingresar / Modificar <singular>"
  filtros: { key: string; label: string }[];
  columnas: { key: string; label: string }[];
  campos: CampoForm[];
};

const clave = (o: any) => `${o.clave} — ${o.nombre}`;
const nombre = (o: any) => o.nombre;
const CLAVE: CampoForm = { key: "clave", label: "Clave", ancho: 4 };
const OBS: CampoForm = { key: "observaciones", label: "Observaciones", tipo: "area", opcional: true };
const ESTADO = (extra: Partial<CampoForm> = {}): CampoForm => ({
  key: "estado_id", label: "Estado", tipo: "lista", fuente: "geo/estados", opcion: nombre, ...extra,
});

export const CATALOGOS_PADRON: Record<string, CatalogoCfg> = {
  apoyos: {
    ruta: "apoyos", titulo: "Apoyos", singular: "Apoyo",
    filtros: [{ key: "clave", label: "Clave" }, { key: "nombre", label: "Apoyo" }],
    columnas: [{ key: "clave", label: "Clave" }, { key: "nombre", label: "Apoyo" }, { key: "observaciones", label: "Observaciones" }],
    campos: [CLAVE, { key: "nombre", label: "Nombre", ancho: 8 },
      { key: "programa_id", label: "Programa", tipo: "buscable", fuente: "padron/programas", opcion: clave }, OBS],
  },
  "descripciones-apoyo": {
    ruta: "descripciones-apoyo", titulo: "Descripción de Apoyo", singular: "Descripción de Apoyo",
    filtros: [{ key: "clave", label: "Clave" }, { key: "nombre", label: "Descripción de Apoyo" }],
    columnas: [{ key: "clave", label: "Clave" }, { key: "nombre", label: "Descripción de Apoyo" }, { key: "observaciones", label: "Observaciones" }],
    campos: [CLAVE, { key: "nombre", label: "Nombre", ancho: 8 },
      { key: "apoyo_id", label: "Apoyo", tipo: "buscable", fuente: "apoyos", opcion: clave }, OBS],
  },
  "niveles-socioeconomicos": {
    ruta: "niveles-socioeconomicos", titulo: "Nivel Socioeconómico", singular: "Nivel Socioeconómico",
    filtros: [{ key: "nombre", label: "Nivel" }],
    columnas: [{ key: "nombre", label: "Nivel" }],
    campos: [{ key: "nombre", label: "Nivel" }],
  },
  "grupos-edad": {
    ruta: "grupos-edad", titulo: "Grupo Edad", singular: "Grupo Edad",
    filtros: [{ key: "nombre", label: "Edad" }],
    columnas: [{ key: "nombre", label: "Edad" }, { key: "rango", label: "Rango min-max" }],
    campos: [{ key: "nombre", label: "Edad" },
      { key: "edad_min", label: "Edad mínima", tipo: "numero", ancho: 6 },
      { key: "edad_max", label: "Edad máxima (vacío = sin tope)", tipo: "numero", ancho: 6, opcional: true }],
  },
  "geo/localidades": {
    ruta: "geo/localidades", titulo: "Localidades", singular: "Localidad",
    filtros: [{ key: "clave", label: "Clave" }, { key: "nombre", label: "Localidad" }],
    columnas: [{ key: "clave", label: "Clave" }, { key: "nombre", label: "Localidad" }, { key: "municipio", label: "Municipio" }, { key: "estado", label: "Estado" }],
    campos: [CLAVE, { key: "nombre", label: "Nombre", ancho: 8 },
      ESTADO({ virtual: true, limpia: "municipio_id", ancho: 6 }),
      { key: "municipio_id", label: "Municipio", tipo: "lista", opcion: nombre, ancho: 6,
        fuente: (f) => (f.estado_id ? `geo/municipios?estado_id=${f.estado_id}` : null) }],
  },
  "geo/municipios": {
    ruta: "geo/municipios", titulo: "Municipios", singular: "Municipio",
    filtros: [{ key: "clave", label: "Clave" }, { key: "nombre", label: "Municipio" }],
    columnas: [{ key: "clave", label: "Clave" }, { key: "nombre", label: "Municipio" }, { key: "estado", label: "Estado" }],
    campos: [CLAVE, { key: "nombre", label: "Nombre", ancho: 8 }, ESTADO({ sinOpcion: "— Estado del municipio —", opcional: true })],
  },
  "geo/colonias": {
    ruta: "geo/colonias", titulo: "Colonias", singular: "Colonia",
    filtros: [{ key: "clave", label: "Clave" }, { key: "nombre", label: "Colonia" }],
    columnas: [{ key: "clave", label: "Clave" }, { key: "nombre", label: "Colonia" }, { key: "estado", label: "Estado" }, { key: "municipio", label: "Municipio" }],
    campos: [CLAVE, { key: "nombre", label: "Nombre", ancho: 8 },
      ESTADO({ limpia: "municipio_id", ancho: 6 }),
      { key: "municipio_id", label: "Municipio", tipo: "lista", opcion: nombre, ancho: 6,
        fuente: (f) => (f.estado_id ? `geo/municipios?estado_id=${f.estado_id}` : null) }],
  },
};
