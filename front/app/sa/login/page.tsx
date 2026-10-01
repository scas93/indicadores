import { redirect } from "next/navigation";
import { apiServer } from "@/lib/api.server";
import { AdminLoginForm } from "./AdminLoginForm";

export default async function Page() {
  const me = await apiServer("/api/admin/auth/me");
  if (me.status === 200) redirect("/");
  return <AdminLoginForm />;
}
