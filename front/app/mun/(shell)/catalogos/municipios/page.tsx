import { CatalogoPadron } from "@/components/padron/CatalogoPadron";

export const metadata = { title: "Municipios - Sistema Indicadores" };

export default function Page() {
  return <CatalogoPadron catalogo="geo/municipios" />;
}
