import { CatalogoPadron } from "@/components/padron/CatalogoPadron";

export const metadata = { title: "Colonias - Sistema Indicadores" };

export default function Page() {
  return <CatalogoPadron catalogo="geo/colonias" />;
}
