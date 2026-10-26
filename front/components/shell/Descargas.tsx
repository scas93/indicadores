"use client";
import { createContext, useContext, useMemo, useState } from "react";

export type Descarga = { label: string; href: string };
type Ctx = { items: Descarga[]; setItems: (i: Descarga[]) => void };

const DescargasCtx = createContext<Ctx>({ items: [], setItems: () => {} });

/** Las pantallas registran aquí sus descargas (p. ej. Inicio, según el programa elegido) y el
 *  encabezado del cascarón las muestra en el ícono de nube. Sin descargas, el ícono queda inerte. */
export function DescargasProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<Descarga[]>([]);
  const valor = useMemo(() => ({ items, setItems }), [items]);
  return <DescargasCtx.Provider value={valor}>{children}</DescargasCtx.Provider>;
}

export const useDescargas = () => useContext(DescargasCtx);
