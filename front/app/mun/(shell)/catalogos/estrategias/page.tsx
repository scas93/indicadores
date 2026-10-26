import { CatalogoCrud } from "@/components/CatalogoCrud";

export const metadata = { title: "Estrategias - Sistema Indicadores" };

export default function Page() {
  return <CatalogoCrud titulo="Estrategias" ruta="estrategias" padre={{ campo: "subtema_id", ruta: "subtemas", label: "Subtema", abuelo: { campo: "eje_id", ruta: "ejes", label: "Eje" } }} />;
}
