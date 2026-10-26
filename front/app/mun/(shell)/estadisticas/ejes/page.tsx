import { ReporteConteo } from "@/components/estadisticas/ReporteConteo";
import { cargarOpciones } from "@/lib/estadisticas.server";

export const metadata = { title: "Ejes - Sistema Indicadores" };

export default async function Page() {
  return <ReporteConteo vista="ejes" op={await cargarOpciones()} />;
}
