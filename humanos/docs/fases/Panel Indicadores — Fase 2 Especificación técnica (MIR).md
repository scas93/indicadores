# Panel Indicadores — Fase 2: Especificación técnica

## MIR

Basado en @santiago — Panel Indicadores — Documento de producto y Análisis del sistema actual. Depende de la Fase 1 (Acceso y planeación).

## Resumen y alcance de esta fase

Fase 2 construye el módulo **Inicio**, el corazón del sistema: el árbol de problemas y objetivos, la matriz de indicadores (Fin, Propósito, Componentes, Actividades) y la captura mensual de avances, con el cálculo de cumplimiento y semaforización. Todo se captura sobre los `programa` creados en Fase 1.

**Depende de:** Fase 1 (programas, tipos de usuario y sus programas asignados, sesión).

**De esta fase dependen:** Fase 3 (las estadísticas de indicadores leen `indicador`, `meta_anual` y `avance_mensual` de aquí) y, más adelante, Fase 4 (la pestaña Presupuestación reparte el techo entre las Actividades de la matriz creada aquí).

**Entregable:** en `demo.<dominio>`, capturar el mismo indicador de Fin de "Fortalecimiento del empleo" que existe en el sistema actual, con los mismos valores, y obtener el mismo cumplimiento (2024 = 1.18).

## Modelo de datos de esta fase

### `arbol_causa_medio`

Un nodo representa un par causa/medio espejo (comparten número). 2 niveles: `1`, `1.1`.

| Columna | Tipo | Notas |
| --- | --- | --- |
| `id` | uuid, PK |  |
| `municipio_id` | fk |  |
| `programa_id` | fk → `programa.id` |  |
| `padre_id` | fk → `arbol_causa_medio.id`, nullable | nulo en nivel 1 |
| `numero` | text | `1`, `1.1`… calculado al insertar |
| `orden` | int |  |
| `texto_causa` | text |  |
| `texto_medio` | text |  |

### `arbol_efecto_fin`

Misma estructura que `arbol_causa_medio`, para efectos/fines: `id`, `municipio_id`, `programa_id`, `padre_id`, `numero`, `orden`, `texto_efecto`, `texto_fin`.

### `elemento_matriz`

Las filas de la matriz: Fin, Propósito, Componentes y Actividades.

| Columna | Tipo | Notas |
| --- | --- | --- |
| `id` | uuid, PK |  |
| `municipio_id` | fk |  |
| `programa_id` | fk → `programa.id` |  |
| `nivel` | enum: `fin`, `proposito`, `componente`, `actividad` |  |
| `numero` | text | vacío en fin/propósito (uno por programa); `1`, `2`… en componentes; `1.1`, `1.2`… en actividades |
| `padre_id` | fk → `elemento_matriz.id`, nullable | una actividad cuelga de su componente |
| `resumen_narrativo` | text |  |
| `medios_verificacion` | text |  |
| `supuestos` | text |  |
| `evidencia` | text, nullable |  |

Restricción: a lo más un `fin` y un `proposito` por `programa_id` (único parcial).

### `indicador`

| Columna | Tipo | Notas |
| --- | --- | --- |
| `id` | uuid, PK |  |
| `municipio_id` | fk |  |
| `elemento_matriz_id` | fk → `elemento_matriz.id` | un elemento puede tener más de un indicador |
| `tipo` | enum: `gestion`, `estrategico` |  |
| `prioritario` | boolean |  |
| `nombre` | text |  |
| `interpretacion` | text |  |
| `dimension` | enum: `eficacia`, `eficiencia`, `calidad`, `economia` |  |
| `frecuencia_id` | fk → `frecuencia.id` (Fase 1) |  |
| `unidad_medida` | text |  |
| `algoritmo` | enum: `a_sobre_b_pct`, `a_sobre_b_menos1_pct`, `a_sobre_b`, `a` | ver “Reglas de cálculo” |
| `unidad_a` | text |  |
| `unidad_b` | text, nullable | nulo/ignorado si `algoritmo = a` |
| `rango_verde_desde` / `rango_verde_hasta` | numeric |  |
| `rango_amarillo_desde` / `rango_amarillo_hasta` | numeric |  |
| `rango_rojo_desde` / `rango_rojo_hasta` | numeric |  |
| `anio_base` | int |  |
| `meta_administracion` | numeric, nullable | única, no por año |

### `meta_anual`

| Columna | Tipo | Notas |
| --- | --- | --- |
| `id` | uuid, PK |  |
| `indicador_id` | fk |  |
| `anio` | int | único `(indicador_id, anio)` |
| `valor_a_programado` | numeric |  |
| `valor_b_programado` | numeric, nullable |  |
| `es_ejercicio_fiscal` | boolean | el año marcado como vigente |

### `avance_mensual`

| Columna | Tipo | Notas |
| --- | --- | --- |
| `id` | uuid, PK |  |
| `indicador_id` | fk |  |
| `anio` | int |  |
| `mes` | int (1-12) | único `(indicador_id, anio, mes)` |
| `valor_a` | numeric, nullable | nulo = sin captura ese mes |
| `valor_b` | numeric, nullable |  |
| `updated_at` | timestamptz |  |

Sumatoria y cumplimiento **no se guardan**: se calculan en cada lectura a partir de `avance_mensual` (regla ya establecida en el Documento de producto).

## Reglas de cálculo

### Sumatorias

Para un `indicador` en un `anio`: `sumatoria_a = SUM(avance_mensual.valor_a)` y `sumatoria_b = SUM(avance_mensual.valor_b)`, sobre los meses con valor capturado (`NULL` no cuenta ni como 0).

### Los 4 algoritmos

| `algoritmo` | Fórmula sobre las sumatorias | Notas |
| --- | --- | --- |
| `a_sobre_b_pct` | `(sumatoria_a / sumatoria_b) * 100` |  |
| `a_sobre_b_menos1_pct` | `((sumatoria_a / sumatoria_b) - 1) * 100` |  |
| `a_sobre_b` | `sumatoria_a / sumatoria_b` |  |
| `a` | `sumatoria_a` | con este algoritmo la variable B se bloquea: no se pide, no se captura, no se guarda |

`sumatoria_b = 0` con un algoritmo que divide → el cumplimiento no es calculable; la API responde el indicador sin cumplimiento (`null`) en vez de un error de división, y el front lo pinta gris (ver abajo).

### Semáforo

El cumplimiento calculado se compara contra los rangos `desde`/`hasta` del indicador (`rango_verde_*`, `rango_amarillo_*`, `rango_rojo_*` — valores absolutos definidos por indicador, no porcentajes fijos: ejemplo real, verde 8.1–10, amarillo 6.1–8, rojo −50–6). El color es el primer rango que contiene el valor calculado.

**Gris = sin datos.** No es un color de rango: se pinta gris cuando el indicador no tiene ningún mes capturado en el año (sumatorias nulas), o cuando `sumatoria_b = 0` vuelve el cumplimiento no calculable. Nunca es un rango configurable, es la ausencia de resultado.

### Dónde se usa

Este mismo cálculo (sumatorias → algoritmo → rango → color) es el que Fase 3 reutiliza para las 4 gráficas de estadísticas y para Cuenta Pública/Transparencia —no se recalcula distinto en ningún otro lugar del sistema.

## Endpoints de la API

Todos de ámbito municipio, filtrados además por los `programa` asignados al usuario en sesión (`usuario_programa`, Fase 1): un usuario no puede leer ni escribir nada de un programa que no tiene asignado, sin importar su tipo.

### Árbol de problemas y objetivos

| Método y ruta | Qué hace |
| --- | --- |
| `GET /api/programas/{id}/arbol` | Devuelve `arbol_causa_medio` y `arbol_efecto_fin` completos, anidados por `padre_id` |
| `POST /api/programas/{id}/arbol/causas` | Alta de causa/subcausa (con su medio espejo) |
| `PATCH /api/arbol-causa-medio/{id}` | Editar (causa, medio, o ambos) |
| `DELETE /api/arbol-causa-medio/{id}` | Elimina el nodo y sus hijos (con confirmación en el front) |
| `POST /api/programas/{id}/arbol/efectos` · `PATCH/DELETE /api/arbol-efecto-fin/{id}` | Análogos para efectos/fines |
| `PUT /api/programas/{id}/arbol/encabezado` | Guarda la situación no deseada (problema) y el objetivo que encabezan el árbol (tabla `arbol_encabezado`: `programa_id`, `problema`, `objetivo`) |
| `GET /api/programas/{id}/arbol/descarga?tipo=completo\|problemas\|objetivos` | PDF |

### Matriz de indicadores

| Método y ruta | Qué hace |
| --- | --- |
| `GET /api/programas/{id}/matriz` | `elemento_matriz` anidado (fin, propósito, componentes con sus actividades), cada uno con sus `indicador` |
| `POST /api/programas/{id}/matriz/componentes` | Alta de un componente |
| `POST /api/elementos-matriz/{id}/actividades` | Alta de una actividad bajo ese componente |
| `PATCH /api/elementos-matriz/{id}` | Editar resumen narrativo, medios de verificación, supuestos, evidencia |
| `DELETE /api/elementos-matriz/{id}` | Solo componentes y actividades (fin/propósito no se borran, son únicos por programa) |
| `POST /api/elementos-matriz/{id}/indicadores` | Alta de un indicador completo (las 4 pestañas del modal en un solo payload: MIR, ficha técnica, metas por año, rangos) |
| `PATCH /api/indicadores/{id}` | Editar cualquier pestaña |
| `GET /api/programas/{id}/matriz/descarga?tipo=resultados\|cumplimiento` | PDF: Matriz de Indicadores de Resultados / Matriz de Cumplimiento de Indicadores |

Fin y Propósito se crean automáticamente (vacíos) la primera vez que se entra al módulo Inicio de un programa, si aún no existen —así la matriz siempre tiene sus 2 filas base.

### Captura de avances

| Método y ruta | Qué hace |
| --- | --- |
| `GET /api/programas/{id}/captura-avances` | Lista de indicadores del programa con datos generales de solo lectura |
| `GET /api/indicadores/{id}/avances?anio=` | Rejilla del año: A/B × 12 meses, más sumatoria y cumplimiento calculados |
| `POST /api/indicadores/{id}/avances/calcular` | Vista previa en vivo (sin guardar): sumatoria, cumplimiento y semáforo de los valores capturados, con el mismo motor (`app/calculo.py`) que la lectura |
| `PUT /api/indicadores/{id}/avances?anio=` | Guarda los 12 valores de A (y B si aplica) de ese año. Valida meses activos y tolerancia (ver Reglas de negocio) antes de aceptar cada mes |
| `GET /api/indicadores/{id}/exportar?formato=fn\|fa` | PDF: Exportar FN (Ficha Narrativa) / Exportar FA (Ficha de Avance) |

## Pantallas del frontend

### Módulo Inicio

Selector de programa (solo los asignados al usuario) y 3 pestañas: Árbol de problemas y objetivos, Matriz de indicadores, Captura de avances. Una 4a pestaña, Presupuestación, se agrega en Fase 4 (aparece si el usuario tiene el permiso y el programa tiene techo). Botón de descargas globales (ícono de nube) con las 5 opciones de PDF del módulo (árbol completo, solo problemas, solo objetivos, Matriz de Resultados, Matriz de Cumplimiento). Las 2 de nivel indicador (Ficha Narrativa y Ficha de Avance) se descargan desde el modal de Captura de avances, no desde este botón.

### Árbol de problemas y objetivos

Encabezado con la situación no deseada (problema) y el objetivo (positivo). Árbol de 2 niveles causas↔medios, y árbol espejo de efectos↔fines. Agregar/editar/eliminar causas y subcausas (efectos/subefectos); los medios/fines se editan junto con su causa/efecto espejo, no por separado. Confirmación al eliminar un nodo con hijos.

&#91;image: Referencia real: Árbol de problemas y objetivos, sistema actual (programa Fortalecimiento del empleo)\]

### Matriz de indicadores

Tabla en 4 niveles (Fin, Propósito, Componentes, Actividades) con columnas Tipo · Resumen narrativo · Indicador · Medios de verificación · Supuestos. Al editar/crear un indicador se abre un modal con los datos del programa en solo lectura (eje, subtema, estrategia, centro gestor, nivel) y 4 pestañas:

&#91;image: Referencia real: Matriz de indicadores, sistema actual\]

- **M.I.R.** — resumen narrativo, medios de verificación, supuestos, evidencia (del elemento).
- **Ficha técnica** — tipo, prioritario, nombre, interpretación, dimensión, frecuencia, unidad de medida, algoritmo, variables A y B con sus unidades. Elegir `algoritmo = a` oculta/deshabilita el campo de la variable B en el resto del formulario.
- **Determinación de metas** — año base, meta de la administración, y una fila por año con A, B y el resultado programado; casilla para marcar el año fiscal vigente.
- **Parametrización** — rangos del semáforo verde/amarillo/rojo (de/hasta).

La pestaña de metas y la de parámetros quedan deshabilitadas hasta que se hayan elegido algoritmo y frecuencia en Ficha técnica (regla de negocio, abajo).

### Captura de avances

Lista de indicadores del programa. Cada uno abre un modal con los datos generales en solo lectura, línea base y meta, y una rejilla por año (Var A / Var B × enero-diciembre, más Sumatoria y Cumplimiento calculados en vivo mientras se captura). Los meses fuera de los meses activos del municipio (Fase 1, Configuración) aparecen deshabilitados, salvo que caigan dentro de los días de tolerancia. Botones Guardar, Exportar FN y Exportar FA.

&#91;image: Referencia real: listado de Captura de avances, sistema actual\]

&#91;image: Referencia real: modal de Captura de avances con la rejilla A por año, sistema actual\]

## Reglas de negocio y validaciones

- Con `algoritmo = a` la variable B se bloquea en el servidor: `POST/PATCH` de avances ignora o rechaza cualquier `valor_b` enviado para ese indicador.
- No se puede guardar `meta_anual` sin que el indicador ya tenga `algoritmo` y `frecuencia_id` definidos (`422` si se intenta).
- Un mes fuera de los meses activos del municipio **y** fuera de los días de tolerancia no se puede capturar: `PUT /api/indicadores/{id}/avances` rechaza esos meses específicos con detalle de cuáles fallaron, sin bloquear los demás.
- Días de tolerancia: ventana de gracia después de que un mes deja de estar activo en la que aún se acepta su captura (p. ej. los primeros N días del mes siguiente para cerrar el mes anterior). “Sin selección” en Configuración equivale a la función automática del sistema actual (12 meses activos, sin tolerancia).
- Fin y Propósito son únicos por programa; el servidor rechaza un segundo alta de cualquiera de los dos.
- Eliminar un componente elimina sus actividades e indicadores en cascada, con la confirmación ya descrita en el front; queda en bitácora.
- Los rangos del semáforo (`verde`, `amarillo`, `rojo`) se validan en el servidor para no traslaparse entre sí al guardar Parametrización, pero no se exige que cubran el 100% del rango numérico posible (un valor fuera de los tres rangos es válido, y no es lo mismo que “sin datos” — se documenta como caso de borde a validar en la Fase de pruebas).

## Criterios de aceptación y casos de prueba

| # | Caso | Resultado esperado |
| --- | --- | --- |
| 1 | **Paridad principal.** Capturar el indicador de Fin de “Fortalecimiento del empleo” con las mismas metas y avances A/B 2024 que tiene hoy el sistema actual | Cumplimiento 2024 calculado = **1.18**, igual que en `demo-indicadores.insadisa.mx` |
| 2 | Ese mismo indicador, con sus rangos reales (verde 8.1–10, amarillo 6.1–8, rojo −50–6) | El color mostrado coincide con el del sistema actual para ese cumplimiento |
| 3 | Elegir `algoritmo = a` en un indicador | El campo/columna de variable B desaparece o se deshabilita en ficha técnica, metas y captura; el servidor rechaza cualquier `valor_b` para ese indicador |
| 4 | Intentar guardar metas sin haber elegido algoritmo o frecuencia | Rechazado (`422`), con mensaje indicando qué falta |
| 5 | Capturar un mes fuera de los meses activos y fuera de tolerancia | Rechazado; un mes dentro de tolerancia sí se acepta |
| 6 | Indicador sin ningún mes capturado en el año | Se pinta gris, no rojo ni sin color |
| 7 | Indicador con algoritmo que divide y `sumatoria_b = 0` | Cumplimiento `null`, se pinta gris, sin error 500 |
| 8 | Crear dos programas distintos, cada uno con su árbol y matriz | Ningún dato de un programa aparece en el otro (mismo principio de aislamiento que en fases anteriores, ahora a nivel programa) |
| 9 | Usuario sin el programa asignado intenta `GET /api/programas/{id}/matriz` de un programa ajeno | `403`, aunque el programa sea del mismo municipio |
| 10 | Descargar los 5 PDF (árbol completo, solo problemas, solo objetivos, Matriz de Resultados, Matriz de Cumplimiento) | Estructura y datos coinciden con el sistema actual para el programa de paridad |

**Medición de la fase:** 100% de coincidencia en cumplimiento, color y estructura de la matriz para el programa de paridad, contra el sistema actual.

**Cobertura de testing (ver Fase 0 § Testing):** los casos 1–9 de esta tabla son cálculo y reglas de negocio (cumplimiento, color por rango, validación de algoritmo, tolerancia de meses, manejo de división entre cero, aislamiento entre programas, permisos) y se agregan como unit tests. El caso 10 (estructura de los 5 PDF) se verifica manualmente contra el sistema de referencia.

## Fuera de alcance de esta fase

- Las 4 gráficas de estadísticas de indicadores y los exportes de Cuenta Pública/Transparencia — Fase 3 (reutilizan el cálculo de esta fase, pero la presentación y los reportes se construyen ahí).
- La pestaña Presupuestación dentro de Inicio, y todo lo de techo/partidas — Fase 4.
- Padrón de beneficiarios — Fase 5.

## Dependencias hacia Fase 3

Fase 3 necesita de esta fase: `indicador` con su algoritmo y rangos, `meta_anual` y `avance_mensual` con datos capturados, y el mismo cálculo de sumatoria → cumplimiento → color documentado arriba —las estadísticas no recalculan nada distinto, solo agrupan y presentan estos mismos números por centro gestor, eje o programa.
