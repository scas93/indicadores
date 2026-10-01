/** Página de error de subdominio. Genérica a propósito: igual para "no existe" y "suspendido",
 *  sin datos del municipio, para no revelar qué subdominios son válidos por tanteo. */
export function ErrorSubdominio() {
  return (
    <div className="error-page">
      <div>
        <h1><i className="fa fa-chain-broken" /> Sitio no disponible</h1>
        <p>La dirección que visitaste no está disponible.<br />Verifica el enlace o contacta a tu administrador.</p>
      </div>
    </div>
  );
}
