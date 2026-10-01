import { redirect } from "next/navigation";
import { apiServer } from "@/lib/api.server";
import { AdminShell } from "./AdminShell";
import { BodyClass } from "@/components/BodyClass";

export default async function PanelLayout({ children }: { children: React.ReactNode }) {
  const me = await apiServer("/api/admin/auth/me");
  if (me.status !== 200) redirect("/login");
  return (
    <>
      <BodyClass name="app-body" />
      <AdminShell nombre={me.data.admin.nombre}>{children}</AdminShell>
    </>
  );
}
