import { apiServer } from "@/lib/api.server";
import { ErrorSubdominio } from "@/components/ErrorSubdominio";
import { Toasts } from "@/components/Toasts";

/** Todo lo de ámbito municipio pasa primero por aquí: si el subdominio no existe o está
 *  suspendido (o no hay subdominio) se muestra la página de error, nunca el login. */
export default async function MunLayout({ children }: { children: React.ReactNode }) {
  const r = await apiServer("/api/auth/branding");
  if (r.status !== 200) return <ErrorSubdominio />;
  return <>{children}<Toasts /></>;
}
