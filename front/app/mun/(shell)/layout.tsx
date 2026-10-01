import { redirect } from "next/navigation";
import { apiServer } from "@/lib/api.server";
import { Shell } from "@/components/Shell";
import { BodyClass } from "@/components/BodyClass";

export default async function ShellLayout({ children }: { children: React.ReactNode }) {
  const me = await apiServer("/api/auth/me");
  if (me.status !== 200) redirect("/login"); // sin sesión o vencida: pide login de nuevo
  const { usuario, municipio } = me.data;
  return (
    <>
      <BodyClass name="app-body" />
      <Shell marca={municipio} usuario={usuario}>{children}</Shell>
    </>
  );
}
