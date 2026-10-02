import { UsuariosMunicipio } from "./UsuariosMunicipio";

export const metadata = { title: "Usuarios del municipio - Super admin" };

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <UsuariosMunicipio id={id} />;
}
