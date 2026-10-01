import { Toasts } from "@/components/Toasts";

export const metadata = { title: "Super admin - Sistema Indicadores" };

export default function SaLayout({ children }: { children: React.ReactNode }) {
  return <>{children}<Toasts /></>;
}
