import { CatalogoPadron } from "@/components/padron/CatalogoPadron";

export const metadata = { title: "Localidades - Sistema Indicadores" };

export default function Page() {
  return <CatalogoPadron catalogo="geo/localidades" />;
}
