import type { TipoUsuario } from "@/components/shell/menu";

/** Espejo FIJO de los permisos de edición de la API (api/app/validators_usuarios.py::PERMISOS).
 *  Solo decide qué botones se muestran: la API es la que realmente niega (403). */
const en = (...t: TipoUsuario[]) => (tipo: TipoUsuario | null) => !!tipo && t.includes(tipo);

export const puede = {
  gestionarUsuarios: en("administrador"),
  editarPlaneacion: en("alcalde", "administrador"),
  editarProgramas: en("alcalde", "presupuestacion", "administrador"),
  editarLogin: en("informes", "administrador"),
  editarMeses: en("alcalde", "administrador"),
};

export const TIPOS: { valor: TipoUsuario; nombre: string }[] = [
  { valor: "informes", nombre: "Informes" },
  { valor: "padron", nombre: "Padrón de beneficiarios" },
  { valor: "presupuestacion", nombre: "Presupuestación" },
  { valor: "control_presupuestal", nombre: "Control presupuestal" },
  { valor: "indicadores", nombre: "Indicadores" },
  { valor: "alcalde", nombre: "Alcalde" },
  { valor: "administrador", nombre: "Administrador" },
];
export const nombreTipo = (t: string) => TIPOS.find((x) => x.valor === t)?.nombre ?? t;
export const MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];
