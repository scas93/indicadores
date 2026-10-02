import { CatalogoCrud } from "@/components/CatalogoCrud";

export const metadata = { title: "Ejes - Sistema Indicadores" };

export default function Page() {
  return <CatalogoCrud titulo="Ejes" ruta="ejes" padre={{ campo: "centro_gestor_id", ruta: "centros-gestores", label: "Centro gestor" }} />;
}
