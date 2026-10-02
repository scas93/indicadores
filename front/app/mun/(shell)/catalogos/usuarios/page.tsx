"use client";
import { useTipo } from "@/components/TipoContext";
import { UsuariosAdmin } from "@/components/usuarios/UsuariosAdmin";
import { puede } from "@/lib/permisos";

export default function Page() {
  const tipo = useTipo();
  return <UsuariosAdmin base="/api/usuarios" gestion={puede.gestionarUsuarios(tipo)} conProgramas enlaces />;
}
