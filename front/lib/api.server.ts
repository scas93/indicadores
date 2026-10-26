import { cookies, headers } from "next/headers";
import { apiUrl } from "@/lib/api-url";

export type ApiResult<T = any> = { status: number; data: T };

/** Llamada a la API desde un Server Component, reenviando ámbito (subdominio) y cookie. */
export async function apiServer<T = any>(path: string): Promise<ApiResult<T>> {
  const h = await headers();
  const c = await cookies();
  const res = await fetch(apiUrl() + path, {
    cache: "no-store",
    headers: {
      "x-municipio-slug": h.get("x-municipio-slug") ?? "",
      "x-ambito": h.get("x-ambito") ?? "",
      cookie: c.toString(),
    },
  });
  return { status: res.status, data: (await res.json().catch(() => null)) as T };
}
