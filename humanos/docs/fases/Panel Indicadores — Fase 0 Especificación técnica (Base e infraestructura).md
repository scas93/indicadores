# Panel Indicadores — Fase 0: Especificación técnica

## Base e infraestructura

Basado en @santiago — Panel Indicadores — Documento de producto.

## Resumen y alcance de esta fase

Fase 0 deja funcionando la infraestructura sobre la que corren todas las demás fases: repos desplegados, resolución de subdominio por municipio, el panel del super admin (alta, suspensión, plantillas globales) y el cascarón visual (login + menú + barra superior) de un municipio, con su primer Administrador ya creado. No incluye ningún módulo operativo (MIR, presupuesto, padrón): esos llegan en fases 1 a 5. Los módulos que aún no existen se muestran en el menú pero deshabilitados, para que el cascarón se vea completo desde el inicio.

**Depende de:** nada, es la fase 0.

**De esta fase dependen:** todas las demás (1 a 6) — ninguna puede empezar sin municipio, subdominio y sesión funcionando.

**Entregable:** un municipio de prueba (`demo.<dominio>`) dado de alta desde el super admin, con su Administrador pudiendo iniciar sesión y ver el cascarón con el aspecto final.

## Stack y repos

Un solo repo (monorepo) `indicadores`, con `/front` y `/api` como carpetas independientes — mantiene el patrón de "un repo" que usas en Aelika; Vercel y Railway se configuran cada uno con su propio *root directory* dentro del mismo repo:

- **`/front`** — Next.js (App Router), desplegado en Vercel (root directory `/front`). Middleware para resolución de subdominio (sección siguiente). Hoja de estilos propia basada en Bootstrap (ver Documento de producto, sección Diseño visual); sin librería de componentes tipo shadcn/MUI.
- **`/api`** — FastAPI en Railway (root directory `/api`). Toda regla de negocio, validaciones y acceso a datos.

**Base de datos:** un solo Postgres en Railway, compartido entre todos los municipios (aislado por `municipio_id`, no por esquema ni por base). Migraciones con Alembic.

**Entornos:** `dev` (local), `staging` (rama `main`, Vercel/Railway preview) y `prod`. `demo.<dominio>` vive en `staging` y es el municipio de prueba para el método de paridad de todas las fases.

**Variables de entorno clave para esta fase:**

| Variable | Dónde | Para qué |
| --- | --- | --- |
| `DATABASE_URL` | API | Conexión a Postgres |
| `SESSION_SECRET` | API | Firma de las cookies de sesión |
| `PASSWORD_ENCRYPTION_KEY` | API | Cifrado reversible de contraseñas de usuario (ver Autenticación y sesión) |
| `ROOT_DOMAIN` | Front y API | Dominio raíz para resolver subdominios (p. ej. `insadisa.mx`) |
| `SUPER_ADMIN_SUBDOMAIN` | Front y API | Fijo en `admin` |

**CI/CD:** despliegue automático a `staging` en cada push a `main`; a `prod` manual, por ahora (no hay aún múltiples municipios en producción).

## Modelo de datos de esta fase

Solo las tablas necesarias para que un municipio exista, tenga un subdominio y su primer usuario pueda entrar. El resto del modelo (planeación, MIR, presupuesto, padrón) llega en fases posteriores.

### `municipio`

| Columna | Tipo | Notas |
| --- | --- | --- |
| `id` | uuid, PK |  |
| `nombre` | text |  |
| `subdominio` | text, unique | slug, p. ej. `guadalajara`; validado único contra `admin` y contra la lista de subdominios reservados |
| `estado_republica_id` | fk → `geografia_estado.id` | por defecto al dar de alta |
| `logo_url` | text, nullable |  |
| `imagen_login_url` | text, nullable |  |
| `color_boton` | enum (7 valores fijos) | Confirmado en vivo contra el sistema actual, son los 7 estilos de botón de Bootstrap: `default` (blanco/gris estándar), `primary` (#A978D1), `info` (#69C2FE), `success` (#5CC691), `warning` (#F1C500), `danger` (#E55957), `dark` (#454545). |
| `mostrar_logos` | boolean | default `true` |
| `duracion_sesion_dias` | int | default `30`; parámetro editable por el super admin (ver Autenticación) |
| `estado` | enum: `activo`, `suspendido` |  |
| `created_at` | timestamptz |  |

### `super_admin`

| Columna | Tipo | Notas |
| --- | --- | --- |
| `id` | uuid, PK |  |
| `usuario` | text, unique |  |
| `password_hash` | text | hash irreversible (argon2) — nadie necesita ver la contraseña del super admin, a diferencia de los usuarios de municipio (ver Autenticación) |
| `nombre` | text |  |
| `created_at` | timestamptz |  |

Se puebla solo por seed (sección “Seed inicial”), nunca desde una pantalla.

### `usuario` (mínimo para esta fase; se completa en Fase 1)

| Columna | Tipo | Notas |
| --- | --- | --- |
| `id` | uuid, PK |  |
| `municipio_id` | fk → `municipio.id` |  |
| `usuario` | text | único dentro del municipio: `unique(municipio_id, usuario)` |
| `password_encrypted` | text | cifrado reversible (AES-256-GCM con `PASSWORD_ENCRYPTION_KEY`), **no hash** — decisión del cliente para que el Administrador y el super admin puedan ver la contraseña real desde Usuarios (ver Riesgos, en el Documento de producto) |
| `tipo` | enum (7 valores fijos) | en esta fase solo se usa `administrador`, para el primero de cada municipio |
| `nombre` | text |  |
| `activo` | boolean | default `true` |
| `debe_cambiar_password` | boolean | default `true` en el alta; se apaga en su primer login exitoso |
| `created_at` | timestamptz |  |

### `sesion`

| Columna | Tipo | Notas |
| --- | --- | --- |
| `id` | uuid, PK | valor de la cookie |
| `usuario_id` | fk → `usuario.id`, nullable |  |
| `super_admin_id` | fk → `super_admin.id`, nullable | exactamente uno de los dos no nulo |
| `municipio_id` | fk → `municipio.id`, nullable | nulo para sesiones de super admin |
| `expires_at` | timestamptz | `created_at` + `duracion_sesion_dias` del municipio (o valor fijo para super admin) |
| `revoked_at` | timestamptz, nullable |  |
| `created_at` | timestamptz |  |

### `bitacora`

| Columna | Tipo | Notas |
| --- | --- | --- |
| `id` | uuid, PK |  |
| `municipio_id` | fk, nullable | nulo para acciones del super admin sobre la plataforma |
| `actor_tipo` | enum: `usuario`, `super_admin` |  |
| `actor_id` | uuid |  |
| `accion` | text | p. ej. `municipio.crear`, `municipio.suspender` |
| `entidad` | text |  |
| `entidad_id` | uuid, nullable |  |
| `detalle` | jsonb |  |
| `created_at` | timestamptz |  |

### Plantillas globales (sin `municipio_id`, viven a nivel plataforma)

`plantilla_conac` (capítulo/partida/partida específica/artículo), `geografia_estado` / `geografia_municipio` / `geografia_localidad`, `plantilla_frecuencia`, `plantilla_dimension`, `plantilla_algoritmo`, `plantilla_grupo_edad`, `plantilla_nivel_socioeconomico`, `plantilla_clasificacion_programatica`. Estructura de catálogo simple (`id`, `clave`, `nombre`, jerarquía cuando aplica). Se cargan una vez (seed) y se **copian** —no se referencian— al espacio del municipio cuando este se crea, para que cada municipio pueda editar su copia sin afectar a los demás (regla ya establecida en el Documento de producto).

`plantilla_clasificacion_programatica` es el catálogo que usa `programa.clasificacion_pragmatica` (Fase 1). Confirmado en vivo contra el sistema actual, sus valores incluyen al menos: Específicos, Proyectos de Inversión, Prestación de Servicios Públicos —es la misma clasificación CONAC que aparece como columna en el exporte de Cuenta Pública (Fase 3).

### `config_municipio`

En esta fase solo lo relativo a login: `imagen_login_url`, `color_boton`, `mostrar_logos` (puede vivir como columnas de `municipio` directamente, como arriba, o extraerse a esta tabla si en fases posteriores crece mucho — se deja como columnas de `municipio` por simplicidad mientras no haya más de 5-6 parámetros).

## Resolución de subdominio y multi-tenancy

1. El dominio se compra propio y su DNS se administra en Cloudflare (igual que el resto de la infraestructura de Aelika): un registro comodín `*.<dominio>` apunta a Vercel. `admin.<dominio>` es un subdominio reservado, no un municipio.
2. El middleware de Next.js lee el `Host` de cada request, extrae el subdominio y lo agrega como header (`X-Municipio-Slug`) a toda llamada que reenvía a `/api/*`. Si el subdominio es `admin`, marca el request como ámbito super admin en vez de municipio.
3. En la API, una dependencia común (FastAPI `Depends`) se ejecuta antes de cualquier endpoint de ámbito municipio: busca el municipio por `subdominio`, verifica `estado = activo`, y lo deja disponible como `municipio_actual` para el resto del request. Si no existe o está suspendido, responde con un código específico (`404 MUNICIPIO_NO_ENCONTRADO` o `403 MUNICIPIO_SUSPENDIDO`) que el front traduce en la página de error (no un login).
4. Esa misma dependencia valida que el `municipio_id` de la sesión (cookie) coincida con `municipio_actual.id`. Si no coincide —sesión de un municipio usada en el subdominio de otro— responde `403 MUNICIPIO_NO_COINCIDE`.
5. **Ninguna consulta de negocio se escribe sin filtrar por `municipio_id`.** Se aplica en una capa común (un mixin de repositorio o un `session.query` ya filtrado), nunca endpoint por endpoint, para que un desarrollador no pueda olvidarlo.
6. Los endpoints de super admin (`/api/admin/*`) exigen ámbito `admin` (paso 2) y sesión de `super_admin`; nunca aceptan una sesión de usuario de municipio, y viceversa.

## Autenticación y sesión

### Contraseñas: dos esquemas distintos, a propósito

- **`usuario.password_encrypted`** (usuarios de municipio): cifrado **reversible** (AES-256-GCM, llave `PASSWORD_ENCRYPTION_KEY` fuera del repo, en el gestor de secretos de Railway). Decisión explícita del cliente: el Administrador del municipio y el super admin necesitan poder ver la contraseña real desde el listado de Usuarios (Fase 1), no solo forzar una nueva. El riesgo de esto —exposición total si se filtra la base de datos— ya está documentado en el Documento de producto, sección Riesgos.
- **`super_admin.password_hash`**: hash **irreversible** (argon2). Nadie necesita ver la contraseña del super admin —no hay pantalla que la liste—, así que aquí sí aplica la práctica estándar.

**Sin reglas de complejidad.** Decisión explícita del cliente: no hay mínimo de longitud, ni exigencia de mayúsculas/números/símbolos, ni límite de intentos fallidos. No se agrega nada de esto por default —si se quiere en el futuro, es una decisión nueva, no algo que la implementación deba asumir.

### Login de municipio — `POST /api/auth/login`

Requiere ámbito municipio (subdominio resuelto, ver sección anterior). Verifica `usuario` + contraseña (desencriptando y comparando, ya que no es hash), que el usuario esté `activo` y que el municipio esté `activo`. Crea un registro en `sesion` y responde con la cookie.

### Login de super admin — `POST /api/admin/auth/login`

Solo válido en ámbito `admin`. Verifica contra `super_admin.password_hash` (comparación de hash, no desencriptado).

### Cookie

`httpOnly`, `Secure`, `SameSite=Lax`, nombre único por ámbito (p. ej. `sesion_municipio` / `sesion_admin`). Vigencia = `duracion_sesion_dias` del municipio (usuarios) o un valor fijo de configuración de plataforma (super admin). El front reenvía `/api/*` desde el propio subdominio (mismo origen), así la cookie funciona en Safari/iOS.

Cerrar el navegador no borra la cookie (vigencia larga, no de sesión de navegador). El vencimiento se calcula en el servidor (`sesion.expires_at`), no en el cliente.

### Revocación

`POST /api/auth/logout` marca `revoked_at`. Deshabilitar un usuario o forzarle nueva contraseña (Fase 1) revoca todas sus sesiones abiertas. Cada request valida `revoked_at IS NULL AND expires_at > now()` antes de aceptar la sesión.

### `GET /api/auth/me`

Devuelve usuario/tipo/municipio (o super admin) de la sesión actual; el front lo usa para armar el menú. En esta fase el tipo relevante es solo `Administrador` (los otros 6 llegan con Fase 1), pero el endpoint ya responde con el campo `tipo` para no requerir cambio de contrato después.

## Endpoints de la API para esta fase

### Auth

| Método y ruta | Ámbito | Qué hace |
| --- | --- | --- |
| `POST /api/auth/login` | municipio | Login de usuario, crea sesión |
| `POST /api/auth/logout` | municipio | Revoca la sesión actual |
| `GET /api/auth/me` | municipio | Datos de la sesión activa |
| `POST /api/admin/auth/login` | admin | Login de super admin |
| `POST /api/admin/auth/logout` | admin | Revoca la sesión de super admin |

### Municipios (super admin)

| Método y ruta | Qué hace |
| --- | --- |
| `GET /api/admin/municipios` | Lista con nombre, subdominio, estado, fecha de alta |
| `POST /api/admin/municipios` | Alta: datos del municipio + datos del primer Administrador. Transacción única: crea `municipio`, copia las plantillas globales a su espacio, crea el usuario Administrador. Si cualquier paso falla, no queda nada a medias |
| `GET /api/admin/municipios/{id}` | Detalle |
| `PATCH /api/admin/municipios/{id}` | Editar datos, y/o cambiar `estado` (activar / suspender) |

Respuestas de error relevantes: `409 SUBDOMINIO_EN_USO`, `422` con detalle de campo para validaciones del formulario de alta.

### Plantillas globales (super admin)

| Método y ruta | Qué hace |
| --- | --- |
| `GET /api/admin/plantillas/{tipo}` | Lista de un catálogo (`conac`, `geografia`, `frecuencia`, `dimension`, `algoritmo`, `grupo_edad`, `nivel_socioeconomico`) |
| `POST /api/admin/plantillas/{tipo}` | Alta de un registro en la plantilla global |
| `PATCH /api/admin/plantillas/{tipo}/{id}` | Editar |
| `DELETE /api/admin/plantillas/{tipo}/{id}` | Solo si nada la referencia aún (misma regla que en el Documento de producto para catálogos del padrón/presupuesto) |

Editar una plantilla global **no** afecta las copias ya hechas en municipios existentes (regla ya establecida: cada municipio edita su propia copia).

## Pantallas del frontend para esta fase

### `admin.<dominio>` — super admin

Sin referencia visual real: no tenemos credenciales al panel de super admin del sistema actual (Insadisa no las comparte). Estas pantallas se diseñan desde cero siguiendo la misma hoja de estilos (Documento de producto, Diseño visual), no son una réplica pixel a pixel de algo existente.

- **Login.** Formulario simple, sin branding de municipio.
- **Listado de municipios.** Tabla: nombre, subdominio, estado (con badge activo/suspendido), fecha de alta. Botón “+ Nuevo municipio”. Acción activar/suspender por fila. *No incluye* el tablero de métricas (usuarios activos, programas, indicadores) descrito en el Documento de producto —eso requiere datos que aún no existen (programas, indicadores llegan en fases 1 y 2); se agrega cuando haya algo que medir.
- **Modal de alta de municipio.** Nombre, subdominio (con validación de formato y disponibilidad en vivo), estado de la república, logo (carga de imagen), y los datos del primer Administrador (nombre, usuario, contraseña inicial o generada).
- **Plantillas globales.** Una pantalla con pestañas (CONAC, geografía, frecuencias, dimensiones, algoritmos, grupos de edad, niveles socioeconómicos), cada una con su tabla editable —mismo patrón visual de tabla + modal que el resto del sistema.

### `<subdominio>.<dominio>` — municipio

- **Login.** Usa `imagen_login_url`, `color_boton` y `mostrar_logos` del municipio resuelto por el subdominio. Si el municipio no existe o está suspendido, esta pantalla ni se intenta: se muestra la página de error (siguiente punto).
- **Página de error de subdominio.** Para `404 MUNICIPIO_NO_ENCONTRADO` y `403 MUNICIPIO_SUSPENDIDO`. Genérica, sin datos del municipio (para no filtrar información de subdominios válidos por tanteo).
- **Cascarón.** Barra superior (logo del municipio + menú de usuario) y menú lateral con **todas** las secciones del sistema final, incluidas las de fases posteriores y las de Fase 6 (por inferencia): las que aún no están construidas aparecen deshabilitadas o con aviso “próximamente”, nunca ocultas. El contenido central queda vacío en esta fase (no hay Inicio aún, eso es Fase 1).

Todas estas pantallas siguen el criterio de aceptación visual general del Documento de producto: comparadas lado a lado con el sistema actual, la diferencia se limita a textos o logos del municipio.

## Seed inicial

Un script (`seed.py` o comando de Alembic/CLI de la carpeta `/api`) que corre una sola vez por ambiente, fuera de la interfaz:

1. Crea el registro en `super_admin` (usuario y contraseña por variables de entorno o parámetros del comando, nunca hardcodeados en el repo).
2. Carga las plantillas globales: CONAC, geografía (estados/municipios/localidades de INEGI), frecuencias, dimensiones, algoritmos, grupos de edad, niveles socioeconómicos.
3. Deja la lista de subdominios reservados (`admin`, `www`, y los que se decidan) para que la validación de alta de municipio los rechace.

El mismo seed corre en `staging` para tener el super admin listo antes de dar de alta `demo.<dominio>`. En `prod` se corre una sola vez al lanzar.

## Criterios de aceptación y casos de prueba

| # | Caso | Resultado esperado |
| --- | --- | --- |
| 1 | Super admin da de alta “demo” con nombre, subdominio, estado y datos de un Administrador | `demo.<dominio>` responde; el Administrador puede iniciar sesión de inmediato; las plantillas globales aparecen copiadas en su espacio |
| 2 | Alta con subdominio ya usado | `409 SUBDOMINIO_EN_USO`, no se crea nada (transacción completa revertida) |
| 3 | Visitar un subdominio inexistente | Página de error genérica, nunca la pantalla de login |
| 4 | Super admin suspende “demo” | Login y cualquier request de ese municipio responden `403 MUNICIPIO_SUSPENDIDO`; las sesiones ya abiertas de ese municipio dejan de aceptarse en la siguiente petición |
| 5 | Aislamiento entre municipios | Crear municipios A y B; tomar el token/cookie de un usuario de A y usarlo contra el subdominio de B → `403 MUNICIPIO_NO_COINCIDE` |
| 6 | Sesión de super admin contra `/api/*` de un municipio, o sesión de usuario contra `/api/admin/*` | Ambas rechazadas |
| 7 | Ver la contraseña de un usuario recién creado | La API puede devolverla en texto plano al Administrador/super admin (Fase 1 expone esto en la UI; aquí se prueba que el cifrado es reversible: se puede desencriptar de vuelta al valor original) |
| 8 | Duración de sesión en minutos (para prueba) | Al vencer el tiempo configurado, la siguiente petición pide login de nuevo, sin necesidad de cerrar sesión explícitamente |
| 9 | Comparación visual | Login y cascarón vacío de `demo.<dominio>` contra las capturas de referencia del sistema actual: la diferencia se limita a textos/logos |

**Medición de la fase:** tiempo de alta de un municipio nuevo hasta que su Administrador puede iniciar sesión, con meta menor a 5 minutos, sin tocar código ni DNS.

## Fuera de alcance de esta fase

- Los otros 6 tipos de usuario, la matriz de usuarios × programas, el alta masiva de usuarios — Fase 1.
- Cualquier pantalla de contenido dentro del cascarón (Inicio, planeación, MIR, etc.) — el menú existe, el contenido no.
- El tablero de métricas por municipio en el panel del super admin (requiere programas/indicadores, que aún no existen).
- Carga masiva desde el super admin (documentada como idea futura en el Documento de producto, no en el MVP).
- Almacenamiento de archivos (R2/S3) — no hay nada que subir aún; llega con el padrón en Fase 5, aunque el logo/imagen de login de esta fase ya necesita algún storage básico de imágenes (puede resolverse con el mismo bucket desde ahora, sin esperar a Fase 5).

## Dependencias hacia Fase 1

Fase 1 (Acceso y planeación) necesita de esta fase: el municipio y su subdominio funcionando, la sesión y sus cookies, el esquema de `usuario` (que Fase 1 extiende con los 6 tipos restantes y el resto de sus columnas), y el cascarón visual donde monta su menú ya con contenido real.

## Testing

Alcance acotado a propósito: no buscamos cobertura total de UI ni perseguir un número de cobertura, sino blindar con unit tests las reglas de negocio que, si se rompen, generan datos incorrectos silenciosos — sumas que no cuadran, techos que se exceden, estados que no se respetan, permisos mal aplicados. El objetivo es poder hacer cambios y refactors sin miedo a romper algo esencial.

**Convención de código que lo hace posible:** las validaciones de negocio (ej. "la suma de `techo_partida` debe igualar `monto_total`", "una asignación no puede exceder lo disponible", "un techo cerrado rechaza escrituras") se escriben como funciones puras en un módulo de validadores, separadas del handler de FastAPI que las invoca — así se prueban sin levantar la API ni la base de datos.

**Backend (`/api`):** `pytest`. Un archivo de tests por módulo de negocio (p. ej. `test_validadores_presupuesto.py`, `test_validadores_matriz.py`), uno por cada regla ya descrita en la tabla de "Criterios de aceptación y casos de prueba" de cada fase que sea una **validación de negocio** (no los casos de UI puros, como qué pestaña se muestra — esos se verifican a mano contra el sistema de referencia, como se ha hecho hasta ahora).

**Frontend (`/front`):** sin suite automatizada en el MVP — las reglas que nos importa blindar viven en el backend.

**CI:** GitHub Actions corre `pytest` en cada PR contra `main`; un PR con tests en rojo no se puede mergear.

**Convención para fases futuras:** cada fase, al cerrar su tabla de "Criterios de aceptación y casos de prueba", marca con una nota qué filas son reglas de negocio (se agregan como unit test) y cuáles son de UI/flujo (quedan como verificación manual — ver las notas agregadas en las Fases 1–4).
