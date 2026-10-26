/** URL base de la API para las llamadas hechas DESDE EL SERVIDOR de Next (Server Components y el
 *  proxy de /api/*). El navegador no la usa: llama a /api/* en su mismo origen y el proxy reenvía aquí.
 *
 *  Variable: `API_URL` (la misma de .env.example y de Vercel). Fuera de producción cae en
 *  http://localhost:8000 para desarrollo; en producción NO hay valor por defecto: si falta, falla
 *  con un mensaje que lo dice, en vez de intentar conectarse a localhost. */
export function apiUrl(): string {
  const url = process.env.API_URL?.trim();
  if (url) return url.replace(/\/+$/, "");
  if (process.env.NODE_ENV !== "production") return "http://localhost:8000";
  throw new Error("Falta la variable de entorno API_URL (URL pública de la API, p. ej. https://<servicio>.up.railway.app). " +
    "Defínela en Vercel para este entorno (Production/Preview) y vuelve a desplegar.");
}
