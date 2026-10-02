import { redirect } from "next/navigation";
import { apiServer } from "@/lib/api.server";
import { TipoProvider } from "@/components/TipoContext";
import { AppShell } from "@/components/shell/AppShell";
import { MENU_MUNICIPIO, TIPO_ETIQUETA, menuPara, type TipoUsuario } from "@/components/shell/menu";

export default async function ShellLayout({ children }: { children: React.ReactNode }) {
  const me = await apiServer("/api/auth/me");
  if (me.status !== 200) redirect("/login"); // sin sesión o vencida: pide login de nuevo
  const { usuario, municipio } = me.data;
  const tipo = usuario.tipo as TipoUsuario;
  return (
    <AppShell
      menu={menuPara(MENU_MUNICIPIO, tipo)}
      etiquetaUsuario={TIPO_ETIQUETA[tipo] ?? usuario.nombre}
      logoutUrl="/api/auth/logout"
      marca={municipio}
      cambiarPassword
    >
      <TipoProvider tipo={tipo}>{children}</TipoProvider>
    </AppShell>
  );
}
