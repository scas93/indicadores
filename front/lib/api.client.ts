export class ApiError extends Error {
  constructor(public status: number, public codigo: string, mensaje: string,
              public campos: Record<string, string> = {}) {
    super(mensaje);
  }
}

/** Mismo origen: /api/* lo reenvía el proxy a la API con la cookie de este subdominio. */
export async function api<T = any>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, ...rest } = init;
  const res = await fetch(path, {
    ...rest,
    headers: { ...(json !== undefined ? { "content-type": "application/json" } : {}), ...rest.headers },
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  });
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, data?.codigo ?? "ERROR", data?.mensaje ?? "Error", data?.campos ?? {});
  return data as T;
}
