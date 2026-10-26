import { Exportacion } from "@/components/estadisticas/Exportacion";
import { cargarOpciones } from "@/lib/estadisticas.server";

export const metadata = { title: "Transparencia - Sistema Indicadores" };

export default async function Page() {
  return <Exportacion tipo="transparencia" op={await cargarOpciones()} />;
}
