import { redirect } from "next/navigation";
import { apiServer } from "@/lib/api.server";
import { LoginForm } from "./LoginForm";

export const metadata = { title: "Iniciar sesión - Sistema Indicadores" };

export default async function LoginPage() {
  const [branding, me] = await Promise.all([apiServer("/api/auth/branding"), apiServer("/api/auth/me")]);
  if (me.status === 200) redirect("/");
  return <LoginForm marca={branding.data} />;
}
