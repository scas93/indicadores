export type AmbitoHost =
  | { ambito: "admin"; slug: null }
  | { ambito: "municipio"; slug: string }
  | { ambito: "ninguno"; slug: null };

/** `demo.insadisa.mx:3000` -> municipio "demo"; `admin.insadisa.mx` -> super admin. */
export function resolverHost(host: string, rootDomain: string, adminSub = "admin"): AmbitoHost {
  const h = host.toLowerCase().replace(/:\d+$/, "");
  const root = rootDomain.toLowerCase();
  if (!h.endsWith("." + root)) return { ambito: "ninguno", slug: null };
  const slug = h.slice(0, -(root.length + 1));
  if (!slug || slug.includes(".")) return { ambito: "ninguno", slug: null };
  if (slug === adminSub) return { ambito: "admin", slug: null };
  return { ambito: "municipio", slug };
}
