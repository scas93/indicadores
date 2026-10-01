import type { Metadata } from "next";
import { Source_Sans_3 } from "next/font/google";
import "bootstrap/dist/css/bootstrap.min.css";
import "font-awesome/css/font-awesome.min.css";
import "../styles/theme.css";

const fuente = Source_Sans_3({ subsets: ["latin"], weight: ["300", "400", "600", "700"], display: "swap" });

export const metadata: Metadata = {
  title: "Sistema Indicadores",
  description: "Sistema de Control y Gestión de Indicadores",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body className={fuente.className}>{children}</body>
    </html>
  );
}
