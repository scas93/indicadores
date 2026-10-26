import { apiServer } from "@/lib/api.server";
import type { Opciones } from "@/lib/estadisticas";

const VACIAS: Opciones = { anios: [], centros_gestores: [], ejes: [], programas: [] };

/** Opciones de los filtros (solo lo que está en el alcance del usuario), traídas en el Server
 *  Component de cada página y pasadas como prop al componente de cliente. */
export async function cargarOpciones(): Promise<Opciones> {
  const r = await apiServer<Opciones>("/api/estadisticas/opciones");
  return r.status === 200 && r.data ? r.data : VACIAS;
}
