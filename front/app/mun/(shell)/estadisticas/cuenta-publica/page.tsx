import { Exportacion } from "@/components/estadisticas/Exportacion";
import { cargarOpciones } from "@/lib/estadisticas.server";

export const metadata = { title: "Cuenta Pública - Sistema Indicadores" };

export default async function Page() {
  return <Exportacion tipo="cuenta-publica" op={await cargarOpciones()} />;
}
