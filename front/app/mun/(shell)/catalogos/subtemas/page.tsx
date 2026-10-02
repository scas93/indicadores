import { CatalogoCrud } from "@/components/CatalogoCrud";

export const metadata = { title: "Subtemas - Sistema Indicadores" };

export default function Page() {
  return <CatalogoCrud titulo="Subtemas" ruta="subtemas" padre={{ campo: "eje_id", ruta: "ejes", label: "Eje" }} />;
}
