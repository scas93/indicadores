import { apiServer } from "@/lib/api.server";
import { RecuperarForm } from "./RecuperarForm";

export const metadata = { title: "Recuperar contraseña - Sistema Indicadores" };

export default async function Page({ searchParams }: { searchParams: Promise<{ token?: string }> }) {
  const [{ token }, branding] = await Promise.all([searchParams, apiServer("/api/auth/branding")]);
  return <RecuperarForm token={token ?? null} marca={branding.data} />;
}
