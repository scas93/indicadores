# Panel Indicadores — Fase 4: Especificación técnica

## Presupuesto

Sep 25, 2026 · @santiago

## Resumen y alcance

Fase 4 depende de Fase 1 (programas, centro gestor, tipos de usuario y `usuario_programa`) y de Fase 2 (elemento\_matriz / Componentes y Actividades, sobre las que se reparte el techo). Agrega el módulo **Presupuestación**: catálogo de capítulos/partidas/partidas específicas/artículos, techo presupuestal por centro gestor y ejercicio, reparto del techo entre partidas, asignación mensual por actividad y artículo, y el reporte **PbR** (Presupuesto basado en Resultados) con exportación.

**Depende de:** Fase 1 (programas, centro gestor, `usuario_programa`), Fase 2 (Componentes y Actividades de la matriz, sobre las que se asigna el techo).

**De esta fase dependen:** Fase 6 (Control Presupuestal / Físico Financiero, que compara este presupuesto asignado contra el ejercido — fuera de alcance de Fase 4, ver sección Fuera de alcance).

**Entregable:** en `demo.<dominio>`, reproducir el ejemplo de PbR ya verificado contra el sistema de referencia — programa de Comedores Comunitarios, Componente 1 con techo de $100 repartido en 3 actividades ($45, $35, $20), con la partida específica 2213 (Productos alimenticios) y 2231 (Utensilios) desglosadas por artículo y mes, todo cargado en enero — y que el Excel exportado coincida en estructura y totales con el de muestra del sistema actual.

## Modelo de datos

### Catálogo de capítulo/partida/partida específica/artículo

Catálogo global (plantilla) copiado al espacio del municipio en Fase 0, editable por el usuario de Presupuestación dentro de su municipio (misma regla que el resto de catálogos de plantilla). **Verificado en vivo** contra el sistema de referencia: Capítulos (9 registros, claves 1000–9000), Partidas (349 registros, claves de 4 dígitos nivel 2, p. ej. 2210, 2230), Partidas Específicas (375 registros, p. ej. 2213, 2231) y Artículos (420 registros). Los 420 Artículos son los mismos 375 códigos CONAC de Partidas Específicas **más \~45 entradas adicionales de clave libre** (p. ej. "PAP" Papelería, "SIMP" Servicio de impresión, "CINS" Contratación de instructores) que el municipio agregó fuera del catálogo oficial — funcionan como partidas específicas "a medida" del municipio, no solo como artículos normales de una partida específica estándar.

| Tabla | Columnas clave | Notas |
| --- | --- | --- |
| `capitulo` | `id`, `municipio_id`, `clave`, `nombre` | nivel 1 (p. ej. 2000 Materiales y suministros) |
| `partida` | `id`, `municipio_id`, `capitulo_id`, `clave`, `nombre` | nivel 2 (p. ej. 2200 Alimentos y utensilios) |
| `partida_especifica` | `id`, `municipio_id`, `partida_id`, `clave`, `nombre` | nivel 3 (p. ej. 2213 Productos alimenticios, 2231 Utensilios) |
| `articulo` | `id`, `municipio_id`, `partida_especifica_id`, `clave`, `nombre` | nivel 4, es la unidad mínima de asignación mensual |

Jerarquía de 4 niveles (capítulo → partida → partida específica → artículo), análoga a `centro_gestor → eje → subtema → estrategia` de Fase 1: cada nivel referencia a su padre, `activo=false` en vez de borrado. **Punto abierto (confirmar con el equipo del sistema de referencia antes de construir):** para los 375 artículos que replican un código CONAC estándar, `partida_especifica_id` apunta a la partida específica del mismo clave; para los \~45 artículos de clave libre agregados por el municipio, no está confirmado si el sistema real les asigna una partida\_específica "padre" (y cuál) o si permite `partida_especifica_id` nulo — el MVP puede optar por exigir siempre un padre, pidiendo al municipio elegir la partida específica estándar más cercana al dar de alta un artículo personalizado.

### `techo_presupuestal`

| Columna | Tipo | Notas |
| --- | --- | --- |
| `id` | uuid, PK |  |
| `municipio_id` | fk |  |
| `centro_gestor_id` | fk → `centro_gestor.id` | Fase 1 |
| `ejercicio_fiscal` | int | único `(municipio_id, centro_gestor_id, ejercicio_fiscal)` |
| `monto_total` | numeric | > 0, validado al guardar |
| `estado` | enum: `abierto`, `cerrado` | controla si aún se puede repartir/reasignar (ver Reglas de negocio) |
| `created_at` | timestamptz |  |

### `techo_partida` (reparto del techo entre partidas)

| Columna | Tipo | Notas |
| --- | --- | --- |
| `id` | uuid, PK |  |
| `techo_presupuestal_id` | fk |  |
| `partida_id` | fk → `partida.id` | sin repetir partida dentro del mismo techo |
| `monto` | numeric | > 0; la suma de todas las filas de un `techo_presupuestal_id` debe igualar `monto_total` |

### `asignacion_actividad` (reparto del techo de una partida entre actividades)

| Columna | Tipo | Notas |
| --- | --- | --- |
| `id` | uuid, PK |  |
| `techo_partida_id` | fk | de qué partida sale el monto |
| `elemento_matriz_id` | fk → `elemento_matriz.id` (Fase 2) | debe ser una Actividad (`nivel = 'actividad'`) del mismo programa que el `centro_gestor` del techo |
| `monto` | numeric | no puede exceder lo que queda por distribuir de `techo_partida_id` |

### `asignacion_articulo` (los 12 montos mensuales)

| Columna | Tipo | Notas |
| --- | --- | --- |
| `id` | uuid, PK |  |
| `asignacion_actividad_id` | fk |  |
| `partida_especifica_id` | fk | debe pertenecer a la misma `partida_id` que `techo_partida_id` |
| `articulo_id` | fk | debe pertenecer a `partida_especifica_id` |
| `mes` | int (1-12) | único `(asignacion_actividad_id, articulo_id, mes)` |
| `monto` | numeric | puede ser 0; la suma de los 12 meses de un artículo es su total para esa actividad |

Caso verificado en vivo (Comedores Comunitarios, Componente 1, techo $100): `asignacion_actividad` con 3 filas ($45, $35, $20, una por Actividad); dentro de la actividad con partida específica 2213 y 2231, `asignacion_articulo` con el monto completo cargado en el mes 1 (enero) y 0 en los meses 2-12.

## Reglas de negocio y cálculo

### Techo presupuestal

- Al capturar el techo: monto total > 0, al menos una partida en `techo_partida`, sin repetir partida, y **la suma de los montos de `techo_partida` debe ser exactamente igual a `monto_total`** (regla de aceptación del producto). El guardado se rechaza (`422`) si no cuadra.
- El techo es por `(centro_gestor_id, ejercicio_fiscal)`, no por programa: varios programas del mismo centro gestor reparten el mismo techo.

### Reparto en cascada (techo → partida → actividad → artículo/mes)

- **Nunca se puede asignar más de lo que queda por repartir en el nivel padre.** Concretamente:
  - Una `asignacion_actividad.monto` no puede exceder `techo_partida.monto` menos la suma ya asignada a otras actividades de esa misma `techo_partida_id`.
  - La suma de los 12 meses de `asignacion_articulo` para un artículo, sumada a la de los demás artículos de la misma `asignacion_actividad_id`, no puede exceder `asignacion_actividad.monto`.
- Estas validaciones corren en el servidor en cada `POST/PATCH`, no solo en el front (misma regla que el resto del sistema: nunca confiar solo en la UI).

### Estado abierto/cerrado del techo

- `techo_presupuestal.estado = abierto`: se puede editar el reparto por partida y las asignaciones por actividad/artículo/mes.
- `techo_presupuestal.estado = cerrado`: de solo lectura; ningún `POST/PATCH` sobre `techo_partida`, `asignacion_actividad` ni `asignacion_articulo` de ese techo se acepta (`403 TECHO_CERRADO`). Cerrar es una acción explícita del usuario con permiso (ver Pantallas); no hay reversión automática a abierto salvo que el mismo usuario lo reabra.

### Visibilidad de la pestaña Presupuestación en Inicio

- La pestaña **solo aparece** en el módulo Inicio de un programa cuando (a) ese programa tiene un `techo_presupuestal` capturado para su `centro_gestor_id` y ejercicio, **y** (b) el usuario en sesión tiene el permiso (tipos `presupuestacion`, `alcalde` y `administrador`, según la matriz de Fase 1). Si falta cualquiera de las dos condiciones, la pestaña no se muestra (no deshabilitada, sino ausente — a diferencia del menú lateral de módulos completos de Fase 0, que sí muestra deshabilitado).

### Reporte PbR

- Se arma leyendo, para un programa y ejercicio: Fin y Propósito (resumen narrativo, de `elemento_matriz`), Componentes con su `techo_partida` total, las Actividades de cada Componente con su `asignacion_actividad.monto`, y dentro de cada actividad las partidas específicas/artículos con `asignacion_articulo` por mes y su total.
- Encabezado exacto (verificado en vivo): Programa, Centro Gestor, Fecha de Elaboración, Ejercicio Fiscal, Clasificación Funcional y Alineación al Programa (Eje, Subtema, Estrategia).
- No se persiste ningún total agregado: los totales de partida/actividad/artículo se calculan en el momento de generar el reporte o la exportación, a partir de `techo_partida` y `asignacion_actividad`/`asignacion_articulo` (misma filosofía que Fase 2 con sumatorias y cumplimiento).

## Endpoints de la API

Todos de ámbito municipio, filtrados por `usuario_programa` cuando aplica (mismo principio que Fase 2 y 3).

### Catálogo capítulo/partida/partida específica/artículo

| Método y ruta | Qué hace |
| --- | --- |
| `GET/POST/PATCH /api/capitulos` | CRUD, editable por `presupuestacion`, `alcalde` y `administrador` |
| `GET/POST/PATCH /api/partidas` | CRUD, filtrado por `capitulo_id` |
| `GET/POST/PATCH /api/partidas-especificas` | CRUD, filtrado por `partida_id` |
| `GET/POST/PATCH /api/articulos` | CRUD, filtrado por `partida_especifica_id` |

### Techo presupuestal

| Método y ruta | Qué hace |
| --- | --- |
| `GET /api/centros-gestores/{id}/techo?ejercicio=` | Techo del centro gestor en el ejercicio, con su reparto por partida |
| `POST /api/centros-gestores/{id}/techo` | Alta: `monto_total` + arreglo de `{partida_id, monto}`; rechaza si la suma no cuadra (`422`) |
| `PATCH /api/techo/{id}` | Editar monto total y/o reparto por partida, solo si `estado=abierto` |
| `PATCH /api/techo/{id}/estado` | Cambia `abierto ↔ cerrado` |

### Presupuestación (pestaña en Inicio)

| Método y ruta | Qué hace |
| --- | --- |
| `GET /api/programas/{id}/presupuestacion?ejercicio=` | Componentes y Actividades del programa con su `asignacion_actividad` actual y lo que queda por repartir de cada `techo_partida` |
| `POST /api/elementos-matriz/{id}/asignacion` | Asigna un monto de una partida a esa Actividad (`elemento_matriz_id` debe ser Actividad) |
| `PATCH /api/asignacion-actividad/{id}` | Editar el monto asignado a la actividad |
| `GET /api/asignacion-actividad/{id}/articulos?ejercicio=` | Partidas específicas/artículos disponibles de esa partida, con sus 12 meses actuales |
| `PUT /api/asignacion-actividad/{id}/articulos` | Guarda los montos mensuales por artículo (arreglo de `{articulo_id, meses: [12 valores]}`) |

### Reporte y exportación PbR

| Método y ruta | Qué hace |
| --- | --- |
| `GET /api/programas/{id}/pbr?ejercicio=` | Reporte PbR completo (para verlo en pantalla) |
| `GET /api/programas/{id}/pbr/exportar?ejercicio=` | Excel (`.xlsx`) del PbR, mismo encabezado y estructura verificados contra el sistema de referencia |

Respuestas de error relevantes: `422` con detalle de campo cuando el reparto no cuadra (techo ≠ suma de partidas, o asignación > disponible); `403 TECHO_CERRADO` sobre cualquier escritura a un techo cerrado.

## Pantallas del frontend

### Catálogos (capítulo, partida, partida específica, artículo)

Una pantalla por nivel, mismo patrón tabla + modal que el resto del sistema (análogo a los catálogos de planeación de Fase 1). Cada nivel filtrado por su padre.

### Techo presupuestal

**Módulo de nivel superior independiente** (no anidado dentro de Inicio de un programa) — visible en el menú lateral junto a Catálogos y Estadísticas. Pantalla de lista con filtros (Ejercicio Fiscal, Centro Gestor, Buscar) y botón **+Nuevo**; tabla de techos existentes (Centro Gestor, Ejercicio Fiscal, Monto). Alta/edición en un modal: Ejercicio Fiscal, Centro Gestor, Monto total, Estado (abierto/cerrado), un botón **Calcula techo de partidas** y la tabla de reparto por partida (agregar fila, editar monto, eliminar), con un indicador en vivo de "repartido / total" que debe llegar a cero de diferencia antes de poder guardar. Botón **Cerrar techo** (con confirmación) visible solo si `estado=abierto`; **Reabrir** visible solo si `estado=cerrado` y el usuario tiene el permiso. **Punto abierto:** no se probó qué hace exactamente el botón "Calcula techo de partidas" en el sistema de referencia — antes de construir, confirmar si autogenera un reparto proporcional o solo recalcula/valida la suma.

### Presupuestación (pestaña en Inicio, junto a Árbol de problemas, Matriz y Captura de avances — Fase 2)

Solo aparece si el programa tiene techo y el usuario tiene permiso (regla de negocio arriba). Tabla con los Componentes y, debajo de cada uno, sus Actividades con el monto ya asignado (p. ej. $45.00, $35.00, $20.00). Al abrir una Actividad (icono de editar) se abre el modal **Captura Presupuestación**: programa y resumen narrativo de solo lectura, y una sección "Presupuesto por partida específica" con, por cada partida del techo del programa, su **Techo presupuestal** (total del programa para esa partida, no de la Actividad), lo **Por distribuir** y la clave de la Partida Específica; debajo, la lista de Artículos ya asignados a esa Actividad con su monto (editar/eliminar) y opción de agregar uno nuevo. Editar un Artículo de la lista abre un segundo modal anidado, **Editar Mes Articulo a Actividad**, con un campo Total y una rejilla de 12 meses (ENE–DIC) editables uno por uno (mismo patrón visual que la rejilla de Captura de avances de Fase 2); el total del artículo es la suma de sus 12 meses. Si el techo está cerrado, toda la pantalla (incluidos ambos modales) es de solo lectura. **Punto abierto:** en el sistema de referencia, el encabezado de esta tabla mostró "Presupuesto Terminado: $0.00" pese a que las filas visibles sumaban el monto correcto ($100) — no se confirmó si es un total que no se actualiza o un error del sistema de referencia; no replicar ese comportamiento sin confirmar.

### Reporte PbR

Selector de programa y ejercicio. Vista de solo lectura con la estructura completa (Fin, Propósito, Componentes con su techo, Actividades con su monto, partidas específicas/artículos con los 12 meses) y botón **Exportar** que descarga el `.xlsx`.

&#91;image: Referencia real: Excel de muestra del PbR — programa Comedores Comunitarios, encabezados de columna\]

## Criterios de aceptación y casos de prueba

| # | Caso | Resultado esperado |
| --- | --- | --- |
| 1 | **Paridad principal.** Reproducir el techo de $100 de Comedores Comunitarios repartido en 3 actividades ($45, $35, $20) con partidas 2213 y 2231 desglosadas por artículo, todo en enero | El PbR generado coincide en estructura y totales con el Excel de muestra del sistema actual |
| 2 | Capturar un techo cuya suma de partidas no cuadra con el monto total | Rechazado (`422`), no se guarda nada |
| 3 | Asignar a una Actividad más de lo que queda disponible en la partida | Rechazado, con el monto disponible indicado en el error |
| 4 | Asignar en un artículo/mes más de lo que queda disponible en la Actividad | Rechazado |
| 5 | Cerrar un techo y luego intentar editar su reparto o las asignaciones de sus actividades | Rechazado (`403 TECHO_CERRADO`); la pantalla se muestra de solo lectura |
| 6 | Reabrir un techo cerrado | Vuelve a aceptar ediciones |
| 7 | Programa sin techo capturado aún | La pestaña Presupuestación no aparece en Inicio |
| 8 | Usuario sin el permiso de Presupuestación entra a un programa con techo | La pestaña no aparece, aunque el programa sí tenga techo |
| 9 | Exportar el PbR de un programa con múltiples Componentes/Actividades | El `.xlsx` respeta el encabezado exacto (Programa, Centro Gestor, Fecha de Elaboración, Ejercicio Fiscal, Clasificación Funcional, Alineación al Programa) y el desglose completo |

**Medición de la fase:** PbR idéntico en estructura y totales al del sistema actual para el programa de paridad (Comedores Comunitarios), y cero casos donde una asignación exceda su disponible.

**Cobertura de testing (ver Fase 0 § Testing):** los casos 2, 3, 4, 5, 6 y 8 de esta tabla son validaciones de negocio (cuadre de reparto, topes de asignación, estado abierto/cerrado, permisos) y se agregan como unit tests de los validadores (`test_validadores_presupuesto.py`). Los casos 1, 7 y 9 (paridad completa del PbR, visibilidad de la pestaña, estructura exacta del Excel exportado) se verifican manualmente contra el sistema de referencia.

## Fuera de alcance de esta fase

- **Control Presupuestal / Físico Financiero** (comparar lo asignado aquí contra el gasto ejercido real) — Fase 6, según el documento de producto.
- **Clasificación Funcional** como módulo propio (distinto de `clasificacion_pragmatica`, ya usado desde Fase 1/3) — documentado como fuera del MVP.
- Cancelación de registros del Padrón — Fase 5.
- Cualquier integración con un sistema contable o de tesorería externo — no está en el alcance del proyecto.

## Dependencias hacia Fase 5

Fase 5 (Padrón de beneficiarios) no depende de esta fase; puede avanzar en paralelo una vez lista Fase 1. Fase 6 sí depende de esta fase: necesita `techo_partida` y `asignacion_actividad`/`asignacion_articulo` con datos capturados para poder comparar presupuesto asignado contra gasto ejercido.
