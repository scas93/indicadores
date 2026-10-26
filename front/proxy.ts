import { NextResponse, type NextRequest } from "next/server";
import { apiUrl } from "./lib/api-url";
import { resolverHost } from "./lib/host";

const ROOT = process.env.ROOT_DOMAIN ?? "localtest.me";
const ADMIN_SUB = process.env.SUPER_ADMIN_SUBDOMAIN ?? "admin";

/**
 * Resolución de municipio por subdominio (spec Fase 0, "Resolución de subdominio"):
 *  - agrega X-Municipio-Slug (o X-Ambito: admin) a todo lo que se reenvía a /api/*
 *  - /api/* se reenvía a la API desde el propio subdominio (mismo origen => la cookie
 *    funciona en Safari/iOS)
 *  - las páginas se montan en /sa/* (super admin) o /mun/* (municipio) sin cambiar la URL.
 * Los headers que mande el cliente se descartan siempre: solo vale lo que dice el Host.
 */
export function proxy(req: NextRequest) {
  const r = resolverHost(req.headers.get("host") ?? "", ROOT, ADMIN_SUB);
  const headers = new Headers(req.headers);
  headers.delete("x-municipio-slug");
  headers.delete("x-ambito");
  if (r.ambito === "admin") headers.set("x-ambito", "admin");
  if (r.ambito === "municipio") headers.set("x-municipio-slug", r.slug);

  const { pathname, search } = req.nextUrl;
  if (pathname.startsWith("/api/")) {
    let destino: URL;
    try {
      destino = new URL(pathname + search, apiUrl());
    } catch (e) {
      console.error(e);
      return NextResponse.json({ codigo: "API_URL_NO_CONFIGURADA", mensaje: (e as Error).message, campos: {} }, { status: 500 });
    }
    return NextResponse.rewrite(destino, { request: { headers } });
  }
  const url = req.nextUrl.clone();
  url.pathname = (r.ambito === "admin" ? "/sa" : "/mun") + (pathname === "/" ? "" : pathname);
  return NextResponse.rewrite(url, { request: { headers } });
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|media/).*)"],
};
