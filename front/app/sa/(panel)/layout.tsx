import { redirect } from "next/navigation";
import { apiServer } from "@/lib/api.server";
import { AppShell } from "@/components/shell/AppShell";
import { MENU_SUPER_ADMIN } from "@/components/shell/menu";

export default async function PanelLayout({ children }: { children: React.ReactNode }) {
  const me = await apiServer("/api/admin/auth/me");
  if (me.status !== 200) redirect("/login");
  return (
    <AppShell menu={MENU_SUPER_ADMIN} etiquetaUsuario="SUPER ADMIN" logoutUrl="/api/admin/auth/logout">
      {children}
    </AppShell>
  );
}
