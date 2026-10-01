# Panel Indicadores — Fase 1: Especificación técnica

## Acceso y planeación

Basado en @santiago — Panel Indicadores — Documento de producto. Depende de la Fase 0 (Base e infraestructura).

## Resumen y alcance de esta fase

Fase 1 convierte el cascarón vacío de Fase 0 en un sistema usable para dar de alta la estructura de un municipio: sus usuarios (los 7 tipos, con sus programas asignados) y su jerarquía de planeación (centro gestor → eje → subtema → estrategia → programa). Al terminar esta fase, un Administrador puede armar todo el andamiaje de su municipio sin tocar MIR, presupuesto ni padrón —esos llegan después y dependen de que los programas ya existan.

**Depende de:** Fase 0 (municipio, subdominio, sesión, tabla `usuario` mínima).

**De esta fase dependen:** Fase 2 (MIR se captura sobre los programas creados aquí), Fase 4 (Presupuesto usa centro gestor y programa), y en general todo lo demás —sin programas no hay dónde capturar nada.

**Entregable:** en `demo.<dominio>`, un Administrador crea usuarios de los 7 tipos, les asigna programas por la matriz, y arma al menos un centro gestor completo (eje, subtema, estrategia, programa) duplicable a otro ejercicio.

## Modelo de datos de esta fase

### `usuario` (se extiende la de Fase 0)

Columnas nuevas sobre las ya creadas en Fase 0 (`municipio_id`, `usuario`, `password_encrypted`, `tipo`, `nombre`, `activo`, `debe_cambiar_password`, `created_at`):

| Columna | Tipo | Notas |
| --- | --- | --- |
| `direccion` | text, nullable |  |
| `telefono` | text, nullable |  |
| `email` | text, nullable |  |
| `anios_acceso` | int\[\] | años en los que el usuario tiene acceso. Resuelto: array simple (no tabla aparte) —no hay requisito de reportar por año, un `int[]` en la misma fila alcanza. |
| `meses_acceso` | int\[\] (1-12) | meses en los que tiene acceso dentro de esos años |

`tipo` pasa a aceptar los 7 valores: `informes`, `padron`, `presupuestacion`, `control_presupuestal`, `indicadores`, `alcalde`, `administrador`.

### `usuario_programa`

| Columna | Tipo | Notas |
| --- | --- | --- |
| `usuario_id` | fk → `usuario.id` |  |
| `programa_id` | fk → `programa.id` |  |
| `created_at` | timestamptz | para la bitácora de la matriz |

PK compuesta `(usuario_id, programa_id)`. Binario: existe o no existe la fila, no hay lectura/escritura por separado (regla ya establecida).

### Planeación

| Tabla | Columnas clave | Notas |
| --- | --- | --- |
| `centro_gestor` | `id`, `municipio_id`, `clave`, `nombre` | único `(municipio_id, clave)` |
| `eje` | `id`, `municipio_id`, `centro_gestor_id`, `clave`, `nombre` |  |
| `subtema` | `id`, `municipio_id`, `eje_id`, `clave`, `nombre` |  |
| `estrategia` | `id`, `municipio_id`, `subtema_id`, `clave`, `nombre` |  |
| `frecuencia` | `id`, `municipio_id`, `clave`, `nombre` | copiada de la plantilla global en Fase 0, editable por Admin y Alcalde |
| `programa` | `id`, `municipio_id`, `ejercicio_fiscal`, `clave`, `nombre`, `centro_gestor_id`, `subtema_id`, `estrategia_id`, `clasificacion_pragmatica`, `activo` | `activo=false` en vez de borrado (regla ya establecida); único `(municipio_id, ejercicio_fiscal, clave)`. `clasificacion_pragmatica` referencia `plantilla_clasificacion_programatica` (catálogo global de Fase 0, copiado al municipio): Específicos, Proyectos de Inversión, Prestación de Servicios Públicos, entre otros —misma clasificación que usa Cuenta Pública en Fase 3. |

### Configuración del municipio (columnas de `municipio`, sin tabla aparte)

Resuelto, consistente con Fase 0: **no se crea una tabla `config_municipio` separada.** `meses_avance_activos` (qué meses del año en curso aceptan captura —usado ya en Fase 2, pero configurado aquí) y `tolerancia_semaforo` se agregan como columnas de `municipio`, junto a `imagen_login_url`, `color_boton`, `mostrar_logos` y `duracion_sesion_dias` de Fase 0. Son 6 parámetros en total; si en una fase posterior crecen más allá de eso, ahí sí se extraen a una tabla aparte.

### `password_reset_token`

Soporta la recuperación de contraseña por email (vía Resend).

| Columna | Tipo | Notas |
| --- | --- | --- |
| `id` | uuid, PK |  |
| `usuario_id` | fk → `usuario.id` |  |
| `token_hash` | text | hash del token (el token en sí solo viaja en el link del email, nunca se guarda en claro) |
| `expires_at` | timestamptz | `created_at` + 1 hora |
| `used_at` | timestamptz, nullable |  |
| `created_at` | timestamptz |  |

## Tipos de usuario y permisos

7 tipos fijos, sin permisos casilla por casilla (detalle módulo por módulo en el Documento de producto y en el Análisis del sistema actual):

| Tipo | Qué ve y hace |
| --- | --- |
| `informes` | Inicio completo · catálogos MIR en consulta · Usuarios · 6 estadísticas de indicadores · Configuración |
| `padron` | Padrón (consultar/eliminar) · 8 catálogos del padrón · Usuarios · 4 estadísticas del padrón |
| `presupuestacion` | Inicio con Presupuestación · Programas con duplicar · capítulos/partidas/partidas específicas/artículos · Usuarios · Techo Presupuestal · Dependencias y PbR |
| `control_presupuestal` | Inicio con Presupuestación · Físico Financiero |
| `indicadores` | Inicio con Presupuestación · Usuarios |
| `alcalde` | Inicio con Presupuestación · catálogos MIR con edición · Usuarios · 6 estadísticas + Físico Financiero · Formato PbR · Meses de avances |
| `administrador` | Todo |

### Cómo se aplica

- **Front:** el menú lateral se arma en `GET /api/auth/me` → `tipo`; el front tiene un mapa fijo `tipo → lista de módulos visibles`, no configurable desde la UI.
- **API:** cada endpoint declara qué tipos lo pueden llamar (decorador o dependencia `require_tipo([...])`). Ocultar un módulo en el menú **no basta**: todo endpoint valida tipo en el servidor, porque el acceso directo por URL a un módulo no permitido debe negarse ahí, no solo en el menú.
- **Programas:** además del tipo, cada endpoint que devuelve o recibe datos ligados a un programa (selectores, reportes, matriz) filtra por los programas de `usuario_programa` del usuario en sesión. Dos usuarios del mismo tipo pueden trabajar programas distintos.
- **Cambio de tipo o de programas:** al no guardarse nada en la sesión más que el `usuario_id`, cambiar el tipo o los programas de un usuario aplica en su siguiente petición, sin volver a iniciar sesión —no se recalculan permisos en la cookie, se leen de la base en cada request.

## Endpoints de la API

Todos de ámbito municipio; `administrador` puede llamar los de Usuarios dentro de su propio municipio (los otros 6 tipos ni ven el módulo). El super admin tiene su propio conjunto de endpoints espejo bajo `/api/admin/municipios/{municipio_id}/usuarios*` (ámbito `admin`, ver más abajo) para crear y administrar usuarios de **cualquier** municipio, en cualquier momento —no solo al dar de alta el municipio.

### Usuarios

| Método y ruta | Qué hace |
| --- | --- |
| `GET /api/usuarios` | Lista, con filtros (tipo, activo, búsqueda por nombre) |
| `POST /api/usuarios` | Alta de un usuario (ver validaciones abajo) |
| `GET /api/usuarios/{id}` | Detalle, **incluye la contraseña desencriptada** (solo llamable por `administrador` o super admin; queda en bitácora cada consulta) |
| `PATCH /api/usuarios/{id}` | Editar datos, tipo, activo/inactivo |
| `POST /api/usuarios/{id}/forzar-password` | Genera y guarda una contraseña nueva, la devuelve una vez en la respuesta, marca `debe_cambiar_password=true`, revoca sesiones abiertas |
| `POST /api/usuarios/bulk` | Alta de varios usuarios a la vez (arreglo de filas); valida cada una y responde qué filas fallaron sin descartar las válidas |

### Usuarios (super admin, cualquier municipio)

Mismo comportamiento que los endpoints de Usuarios de arriba, pero de ámbito `admin` y con `municipio_id` explícito en la ruta en vez de resuelto por subdominio. Reutilizan la misma lógica de negocio (un solo lugar de validaciones), sin la restricción de tipo `administrador`.

| Método y ruta | Qué hace |
| --- | --- |
| `GET /api/admin/municipios/{municipio_id}/usuarios` | Lista de usuarios de ese municipio |
| `POST /api/admin/municipios/{municipio_id}/usuarios` | Alta de un administrador o usuario de cualquier tipo en ese municipio |
| `GET /api/admin/municipios/{municipio_id}/usuarios/{id}` | Detalle, incluida la contraseña desencriptada |
| `PATCH /api/admin/municipios/{municipio_id}/usuarios/{id}` | Editar datos, tipo, activo/inactivo |
| `POST /api/admin/municipios/{municipio_id}/usuarios/{id}/forzar-password` | Igual que la versión de municipio |

Toda acción del super admin sobre usuarios de un municipio queda en `bitacora` con `actor_tipo='super_admin'`, igual que las demás acciones de soporte.

### Matriz de usuarios y programas

| Método y ruta | Qué hace |
| --- | --- |
| `GET /api/usuarios/matriz?ejercicio=&centro_gestor_id=&tipo=&q=` | Devuelve usuarios (filas) × programas agrupados por centro gestor (columnas), con las celdas ya marcadas según `usuario_programa` |
| `POST /api/usuarios/matriz` | Guardado en lote: lista de altas y bajas `{usuario_id, programa_id}`; aplica todo en una transacción, escribe en bitácora el resumen ("12 asignaciones nuevas, 3 retiradas") y lo devuelve para el mensaje de confirmación en pantalla |

### Planeación

| Método y ruta | Qué hace |
| --- | --- |
| `GET/POST/PATCH /api/centros-gestores` | CRUD. Editable por `administrador` y `alcalde` (regla del Documento de producto). |
| `GET/POST/PATCH /api/ejes`, `/api/subtemas`, `/api/estrategias` | CRUD, cada uno filtrado por su padre en la jerarquía. Editable por `administrador` y `alcalde`. |
| `GET/POST/PATCH /api/frecuencias` | CRUD. Editable por `administrador` y `alcalde`. |
| `GET/POST/PATCH /api/programas` | CRUD, con `ejercicio_fiscal`. Editable por `administrador`, `alcalde` y `presupuestacion`. |
| `POST /api/programas/{id}/duplicar` | Crea un `programa` nuevo con clave nueva en el `ejercicio_fiscal` destino, **reutilizando** (no duplicando) su `centro_gestor_id`, `subtema_id` y `estrategia_id` originales —esos catálogos no tienen versión por ejercicio, así que no se copian, solo se referencian de nuevo. Editable por `administrador`, `alcalde` y `presupuestacion`, igual que el resto de Programas. |

### Configuración

| Método y ruta | Qué hace |
| --- | --- |
| `GET /api/config` | Config actual del municipio (login, meses de avance) |
| `PATCH /api/config` | Editar; `meses_avance_activos` solo editable por `administrador` y `alcalde` |

### Recuperación de contraseña por email

Envío de correo con **Resend**. Complementa a “forzar contraseña” (Fase 0/1, hecha por Administrador o super admin): esta vía la inicia el propio usuario.

| Método y ruta | Ámbito | Qué hace |
| --- | --- | --- |
| `POST /api/auth/recuperar` | municipio | Body `{usuario}`. Si existe, genera un token, guarda su hash en `password_reset_token` (vence en 1 hora) y envía por Resend un email con el link `https://<subdominio>.<dominio>/recuperar?token=...`. Responde `200` siempre, exista o no el usuario, para no revelar qué usuarios existen |
| `POST /api/auth/recuperar/confirmar` | municipio | Body `{token, password_nueva}`. Valida que el token no esté vencido ni usado (comparando el hash), actualiza `password_encrypted`, marca `used_at`, apaga `debe_cambiar_password`, revoca las sesiones abiertas de ese usuario |

**Variables de entorno (agregar a las de Fase 0):** `RESEND_API_KEY`, `EMAIL_FROM` (remitente del correo de recuperación).

**Pantallas:** “¿Olvidaste tu contraseña?” en el login, que pide el usuario; y una pantalla para capturar la contraseña nueva al abrir el link del correo (con aviso si el token ya venció o ya se usó).

## Pantallas del frontend

### Usuarios

- **Listado.** Tabla: nombre, usuario, tipo, activo, último acceso. Columna o acción para **ver la contraseña** directamente ahí (decisión del cliente) — se recomienda mostrarla oculta con un icono de "ojo" para revelarla en pantalla, y registrar la consulta en bitácora, aunque el requerimiento es que esté visible desde el listado sin pasos adicionales de exportación. Búsqueda y filtro por tipo/activo.
- **Alta/edición (modal).** Nombre, usuario, contraseña, tipo, dirección, teléfono, email, años y meses de acceso, activo. Selector de programas en árbol agrupado por centro gestor (alternativa a usar la matriz).
- **Forzar contraseña.** Botón en el listado/detalle; muestra la nueva contraseña una vez en pantalla tras confirmarlo.

&#91;image: Referencia real: listado de Usuarios, sistema actual (visto como tipo Informes)\]

### Matriz de usuarios y programas

Pantalla dedicada: filas = usuarios (con su tipo al lado), columnas = programas del ejercicio elegido agrupados bajo su centro gestor. Casillas marcables. Atajos en lote: fila completa, columna completa, grupo de centro gestor para usuarios seleccionados. Filtros: ejercicio, centro gestor, tipo, búsqueda. Botón **Guardar** explícito que muestra el resumen de cambios antes/después de aplicar.

### Alta de varios usuarios a la vez

Tabla editable: una fila por usuario nuevo (nombre, usuario, email, tipo, contraseña inicial o generada). Agregar filas con botón o pegando desde Excel (parseo de texto separado por tabs). Al guardar, filas inválidas se señalan sin perder las válidas; las creadas aparecen de inmediato en la Matriz.

### Catálogos de planeación

Una pantalla por nivel (Centros gestores, Ejes, Subtemas, Estrategias, Programas), mismo patrón de tabla + modal que el resto del sistema. Programas incluye acción **Duplicar a otro ejercicio**.

&#91;image: Referencia real: catálogo de Centros gestores, sistema actual\]

&#91;image: Referencia real: catálogo de Programas, sistema actual\]

### Configuración

Pestañas Login (imagen, color de botón, mostrar logos —ya en Fase 0) y Meses de avances (qué meses del año en curso aceptan captura, usado por Fase 2).

&#91;image: Referencia real: Configuración → Meses de avances — tolerancia en días y 12 casillas de meses activos, sistema actual\]

&#91;image: Referencia real: Configuración → Login, sistema actual\]

## Reglas de negocio y validaciones

- `usuario` único dentro del municipio, no globalmente: `unique(municipio_id, usuario)`.
- `administrador` crea usuarios dentro de su propio municipio; la API rechaza `POST/PATCH /api/usuarios*` de cualquier otro tipo con `403`, independientemente de lo que el front muestre. El super admin, desde `/api/admin/municipios/{id}/usuarios*`, no tiene esa restricción: puede crear o editar administradores y usuarios de cualquier tipo en cualquier municipio.
- Alta masiva: fila por fila, mismas validaciones que el alta individual (usuario repetido dentro del municipio, email con formato válido, tipo dentro de los 7 permitidos); una fila inválida no bloquea al resto.
- La contraseña inicial (individual o masiva) se guarda con `debe_cambiar_password=true`; el primer login exitoso la apaga y exige capturar una nueva antes de continuar.
- `programa` único por `(municipio_id, ejercicio_fiscal, clave)`; duplicar a otro ejercicio exige clave nueva (no puede repetir la del ejercicio origen).
- Catálogos de planeación (`centro_gestor`, `eje`, `subtema`, `estrategia`, `programa`) se deshabilitan, nunca se borran, igual que hoy — `activo=false` los saca de los selectores sin perder el histórico.
- `usuario_programa`: solo pueden asignarse programas del mismo municipio del usuario (validado en el servidor, no solo en el front del selector).
- Cambiar el tipo de un usuario no le quita ni le agrega programas automáticamente; son independientes.

  Sin reglas de complejidad de contraseña (ver Fase 0, Autenticación): ni el alta individual ni la masiva validan longitud mínima, mayúsculas, números ni símbolos.

## Criterios de aceptación y casos de prueba

| # | Caso | Resultado esperado |
| --- | --- | --- |
| 1 | Un usuario de cada uno de los 7 tipos inicia sesión | El menú que ve coincide con el perfil equivalente del sistema actual |
| 2 | Acceso directo por URL a un módulo no permitido para el tipo | La API lo niega (`403`), sin importar que el front oculte el enlace |
| 3 | Administrador cambia el tipo de un usuario | El usuario ve el nuevo menú en su siguiente petición, sin volver a iniciar sesión |
| 4 | Usuario con programas asignados A y B consulta un selector o reporte | Solo ve A y B, nunca los demás programas del municipio |
| 5 | Administrador ve la contraseña de un usuario desde el listado | Se muestra en texto plano; la consulta queda en bitácora |
| 6 | Guardar cambios en la Matriz (12 altas, 3 bajas) | Se aplican en una transacción; el resumen mostrado coincide con lo guardado; queda en bitácora |
| 7 | Alta masiva con una fila con usuario repetido | Esa fila se marca con error; las demás se crean igual |
| 8 | Duplicar un programa a otro ejercicio | Se copia con clave nueva al ejercicio destino; el original no se modifica |
| 9 | Deshabilitar un centro gestor/eje/programa en uso | Se marca `activo=false`, desaparece de los selectores, pero el histórico que lo referencia no se rompe |
| 10 | Usuario deshabilitado con sesión abierta | Pierde el acceso de inmediato (sesiones revocadas al deshabilitar) |

**Medición de la fase:** 7 de 7 tipos con menú idéntico al del perfil actual; cero accesos a módulos sin permiso en las pruebas.

**Cobertura de testing (ver Fase 0 § Testing):** los casos 2–10 de esta tabla son reglas de negocio (permisos, scoping por `usuario_programa`, auditoría, transacciones, baja lógica, revocación de sesión) y se agregan como unit tests de los validadores correspondientes. El caso 1 (menú idéntico al perfil del sistema actual) es de comparación visual y se verifica manualmente.

## Fuera de alcance de esta fase

- Árbol de problemas/objetivos, matriz MIR, indicadores y captura de avances — Fase 2 (necesita los programas de esta fase, pero el contenido MIR en sí no se construye aquí).
- Las 4 estadísticas de indicadores y los exportes oficiales (Cuenta Pública, Transparencia) — Fase 3.
- Presupuesto (techo, presupuestación, PbR) — Fase 4.
- Padrón de beneficiarios — Fase 5.
- Carga masiva desde el super admin — no está en el MVP.

## Dependencias hacia Fase 2

Fase 2 (MIR) necesita de esta fase: los `programa` ya creados (con su centro gestor, eje, subtema y estrategia), la sesión y tipos de usuario ya funcionando para decidir quién puede editar la matriz MIR, y `config_municipio.meses_avance_activos` para saber qué meses aceptan captura.
