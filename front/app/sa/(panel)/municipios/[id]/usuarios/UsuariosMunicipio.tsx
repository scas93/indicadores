"use client";
import { useEffect, useState } from "react";
import { UsuariosAdmin } from "@/components/usuarios/UsuariosAdmin";
import { api } from "@/lib/api.client";

/** Super admin: usuarios de CUALQUIER municipio (endpoints espejo, ámbito admin). Misma pantalla que
 *  el Administrador del municipio; sin selector de programas (los programas son de ámbito municipio). */
export function UsuariosMunicipio({ id }: { id: string }) {
  const [m, setM] = useState<{ nombre: string; subdominio: string } | null>(null);
  useEffect(() => { api(`/api/admin/municipios/${id}`).then(setM).catch(() => {}); }, [id]);
  return (
    <>
      <p><a href="/"><i className="fa fa-arrow-left" /> Municipios</a>{m && <span className="text-muted"> · {m.nombre} ({m.subdominio})</span>}</p>
      <UsuariosAdmin base={`/api/admin/municipios/${id}/usuarios`} gestion conProgramas={false} />
    </>
  );
}
