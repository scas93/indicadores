import { CumplimientoMetas } from "@/components/estadisticas/CumplimientoMetas";
import { cargarOpciones } from "@/lib/estadisticas.server";

export const metadata = { title: "Cumplimiento de Metas - Sistema Indicadores" };

export default async function Page() {
  return <CumplimientoMetas op={await cargarOpciones()} />;
}
