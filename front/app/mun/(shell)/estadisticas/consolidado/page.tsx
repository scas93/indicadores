import { ReporteConteo } from "@/components/estadisticas/ReporteConteo";
import { cargarOpciones } from "@/lib/estadisticas.server";

export const metadata = { title: "Consolidado - Sistema Indicadores" };

export default async function Page() {
  return <ReporteConteo vista="consolidado" op={await cargarOpciones()} />;
}
