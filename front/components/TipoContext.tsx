"use client";
import { createContext, useContext } from "react";
import type { TipoUsuario } from "./shell/menu";

const Ctx = createContext<TipoUsuario | null>(null);

/** El layout del cascarón (servidor) conoce el tipo de la sesión; las pantallas lo leen de aquí. */
export function TipoProvider({ tipo, children }: { tipo: TipoUsuario; children: React.ReactNode }) {
  return <Ctx.Provider value={tipo}>{children}</Ctx.Provider>;
}
export const useTipo = () => useContext(Ctx);
