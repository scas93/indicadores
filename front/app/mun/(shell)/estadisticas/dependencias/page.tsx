import { ReporteConteo } from "@/components/estadisticas/ReporteConteo";
import { cargarOpciones } from "@/lib/estadisticas.server";

export const metadata = { title: "Dependencias - Sistema Indicadores" };

export default async function Page() {
  return <ReporteConteo vista="dependencias" op={await cargarOpciones()} />;
}
