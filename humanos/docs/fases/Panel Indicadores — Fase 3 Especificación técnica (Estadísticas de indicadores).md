# Panel Indicadores — Fase 3: Especificación técnica (Estadísticas de indicadores)

Sep 25, 2026 · @santiago

## Resumen y alcance

Fase 3 depende de Fase 2 (MIR: `elemento_matriz`, `indicador`, `meta_anual`, `avance_mensual` ya definidos y con datos capturados). No introduce tablas nuevas: es una capa de **lectura y agregación** sobre esos datos, más 2 endpoints de exportación a Excel.

Entrega:

1. **4 gráficas de conteo por color de semáforo**, cada una agrupando el mismo conteo base por una dimensión distinta:
   - **Dependencias** (por centro gestor)
   - **Ejes** (por eje estratégico)
   - **Cumplimiento de Metas** (% de metas por color de semáforo, por dependencia)
   - **Consolidado** (barras, vista global)
2. **Exportación Cuenta Pública** (Excel, 38 columnas confirmadas, agrupadas por Programa/proyecto de inversión → Presupuesto del programa → MIR → Indicadores; cada indicador ocupa 2 filas HTML, una por variable A/B, con los campos de meta compartidos vía rowspan).
3. **Exportación Transparencia** (Excel, 26 columnas confirmadas, una fila por indicador — no por variable).

**Decisión de producto ya resuelta** (heredada del documento de producto): en el sistema nuevo, los 4 conteos y el detalle de indicadores se restringen a los **programas asignados al usuario** dentro de la dependencia elegida, no a todos los indicadores de la dependencia completa (a diferencia del sistema actual). Esto aplica de forma uniforme a los 4 reportes y a ambas exportaciones.

## Reglas de agrupación, filtros y cálculo

### Query base de conteo

Las 4 gráficas (Dependencias, Ejes, Cumplimiento de Metas, Consolidado) parten de la **misma consulta**: para un conjunto de indicadores (filtrado por año, dependencia y programas del usuario), contar cuántos caen en cada color de semáforo (verde/amarillo/rojo/gris), calculado según las reglas de Fase 2 (primer rango que contiene el cumplimiento; gris = sin datos capturados o sumatoria de B = 0). Lo único que cambia entre las 4 gráficas es el **agrupador** y la **visualización**:

| Gráfica | Agrupador | Visualización | Origen en sistema actual |
| --- | --- | --- | --- |
| Dependencias | `centro_gestor_id` | Barras/dona por dependencia | `grafica_centro_gestor.php` |
| Ejes | `eje_id` | Barras/dona por eje | `semaforizacion.php` |
| Cumplimiento de Metas | `centro_gestor_id` (selección única) | Barras de % de metas por color (verificado en vivo: una gráfica por color, % sobre el total de la dependencia) | `grafica_por_color.php` |
| Consolidado | `centro_gestor_id` (selección múltiple) | Barras apiladas por dependencia, en % (verificado en vivo: una barra por cada dependencia seleccionada) | `grafica_barras.php` |

### Tipos de cumplimiento

Cada gráfica soporta un filtro "tipo de cumplimiento" con 2 modos, que cambia cómo se calcula el valor contra el que se compara el semáforo:

1. **`(C.O/C.E)×100`** — cumplimiento obtenido entre esperado: compara el avance real contra la meta programada a la fecha (% de la meta programada alcanzado).
2. **Cumplimiento obtenido** — usa directamente el valor calculado por el algoritmo del indicador (sin comparar contra una meta esperada).

Ambos modos usan las mismas reglas de color de Fase 2 (rangos verde/amarillo/rojo específicos por indicador), solo cambia qué valor numérico se evalúa contra esos rangos.

### Filtros de dependencia — selección múltiple

Los reportes agrupados por dependencia (Dependencias, y cualquier otro que permita elegir más de un centro gestor) reciben el filtro como una **cadena de ids separados por comas** (p. ej. `128,131`), no como un arreglo JSON. Verificado en vivo probando con 2 dependencias seleccionadas a la vez en el sistema de referencia. El nuevo API puede optar por:

- Replicar el mismo formato (`centro_gestor_ids=128,131` como query param de texto), o
- Normalizarlo a un arreglo estándar (`centro_gestor_ids[]=128&centro_gestor_ids[]=131`) en el nuevo backend.

**Decisión:** el nuevo API usa arreglo estándar (`centro_gestor_ids: int[]` en query string repetida o JSON body según el endpoint), ya que no hay necesidad de replicar la limitación del sistema legado — solo se documenta el quirk como referencia de comportamiento a igualar en los resultados, no en el formato del contrato.

### Restricción por programas del usuario

Para los 4 conteos y para el detalle de indicadores, el universo de indicadores considerado es: indicadores cuyo `elemento_matriz` pertenece a un `programa` de la dependencia filtrada **Y** ese programa está en `usuario_programa` para el usuario autenticado (ver Fase 1). Un usuario sin programas asignados en una dependencia ve conteo 0 para esa dependencia, no error. **Actualización:** administrador y alcalde ven todos los programas del municipio, igual que en las demás fases (ver "Decisiones de construcción"); para el resto el alcance sale de `usuario_programa`.

## Modelo de datos

Fase 3 **no agrega tablas nuevas**. Opera por completo sobre entidades ya definidas en fases previas:

- `elemento_matriz`, `indicador`, `meta_anual`, `avance_mensual` (Fase 2) — fuente de los conteos por semáforo y de los datos de las exportaciones.
- `programa`, `centro_gestor`, `eje` (Fase 1) — dimensiones de agrupación.
- `usuario_programa` (Fase 1) — fuente de la restricción de alcance por usuario.
- `plantilla_clasificacion_programatica` / `programa.clasificacion_pragmatica` (Fase 0/1) — columna requerida en ambas exportaciones.

Todos los valores de esta fase (conteos, semáforos, sumatorias, cumplimientos) se **calculan en tiempo real** a partir de esas tablas; no se persiste ningún resultado agregado (consistente con la regla de Fase 2 de nunca guardar sumatoria/cumplimiento).

## Endpoints de la API

Todos requieren sesión activa (`require_tipo`: cualquier tipo con acceso al módulo `indicadores`, según la matriz de Fase 1). Todos aplican la restricción por `usuario_programa` descrita arriba.

### Gráficas de conteo por semáforo

- `GET /api/estadisticas/dependencias?anio=&centro_gestor_ids[]=&tipo_cumplimiento=` → conteo por color, agrupado por `centro_gestor_id`, dentro del alcance del usuario.
- `GET /api/estadisticas/ejes?anio=&eje_ids[]=&tipo_cumplimiento=` → conteo por color, agrupado por `eje_id`.
- `GET /api/estadisticas/cumplimiento-metas?anio=&centro_gestor_id=&tipo_cumplimiento=` → % de metas por color de semáforo (una dependencia a la vez, verificado en vivo), para las 4 gráficas de barras (una por color).
- `GET /api/estadisticas/consolidado?anio=&centro_gestor_ids[]=&tipo_cumplimiento=` → conteo por color en % (barras apiladas), agrupado por `centro_gestor_id` (una o varias dependencias seleccionadas), dentro del alcance del usuario.

Respuesta común de las 3 primeras (forma general):

```json
{
  "grupos": [
    {"id": 128, "nombre": "Desarrollo Social", "verde": 14, "amarillo": 0, "rojo": 4, "gris": 1, "total": 19}
  ]
}
```

### Detalle de indicadores

- `GET /api/estadisticas/indicadores?anio=&centro_gestor_id=&eje_id=&color=&tipo_cumplimiento=` → lista de indicadores que cumplen los filtros, con: nombre, programa, dependencia, eje, algoritmo, meta anual, sumatoria, cumplimiento calculado, color de semáforo. Usado para "ver detalle" al hacer clic en una porción de gráfica o fila de tabla.

### Exportaciones

- `GET /api/estadisticas/exportar/cuenta-publica?anio=&centro_gestor_ids[]=` → archivo `.xlsx`, 38 columnas, agrupado Programa → Presupuesto → MIR → Indicadores (2 filas por indicador, una por variable A/B).
- `GET /api/estadisticas/exportar/transparencia?anio=&centro_gestor_ids[]=` → archivo `.xlsx`, 26 columnas, 1 fila por indicador.

Ambas exportaciones respetan el alcance por `usuario_programa` del usuario que las solicita; no exportan indicadores fuera de su alcance aunque pertenezcan a la dependencia filtrada.

## Pantallas del frontend

Todas viven bajo el módulo **Estadísticas** (menú lateral, visible según tipo de usuario — Fase 1). Capturas de referencia del sistema actual se insertan junto a cada pantalla; se capturan en vivo siguiendo el mismo mecanismo usado en Fases 1 y 2.

### Dependencias

Filtros: año, tipo de cumplimiento, selección múltiple de centros gestores (opcional — vacío = todos los del alcance del usuario). Gráfica de barras/dona con conteo por color de semáforo por dependencia. Clic en una dependencia o color → abre el detalle de indicadores filtrado.

&#91;image: Reporte Dependencias, sistema de referencia — Económico y Social, 2025\]

### Ejes

Mismos filtros que Dependencias, agrupado por eje estratégico en vez de centro gestor. Mismo comportamiento de clic-a-detalle.

&#91;image: Reporte Ejes, sistema de referencia — Eje Económico 2025: 14 verde / 0 amarillo / 4 rojo / 1 gris = 19 total\]

### Cumplimiento de Metas

Filtros: año, dependencia (selección única), tipo de cumplimiento. 4 gráficas de barras (una por color: verde, amarillo, rojo, gris) mostrando el % de metas de esa dependencia en cada color — verificado en vivo.

&#91;image: Reporte Cumplimiento de Metas, sistema de referencia — Económico 2025\]

### Consolidado

Filtros: año, tipo de cumplimiento, selección múltiple de centros gestores (verificado en vivo: seleccionar más de una dependencia muestra una barra apilada por cada una, en porcentaje). No es un total único sin agrupador — es la misma gráfica de Dependencias pero en modo porcentaje/apilado en vez de conteo absoluto. Clic en una barra o segmento → abre el detalle de indicadores filtrado.

&#91;image: Reporte Consolidado, sistema de referencia — Económico y Social, 2025\]

### Cuenta Pública (exportación)

Pantalla con selector de año y dependencias, botón "Exportar" que descarga el `.xlsx` de 38 columnas vía el endpoint de exportación.

&#91;image: Exportación Cuenta Pública, sistema de referencia — encabezados de columnas\]

### Transparencia (exportación)

Análoga a Cuenta Pública: selector de año y dependencias, botón "Exportar" que descarga el `.xlsx` de 26 columnas.

&#91;image: Exportación Transparencia, sistema de referencia — encabezados de columnas\]

## Reglas de negocio y validaciones

- El color gris (sin datos) cuenta como una categoría propia en los 4 reportes; nunca se excluye del total ni se reclasifica como rojo.
- Un indicador sin ningún mes capturado en el año filtrado se cuenta como gris en todos los reportes.
- El filtro "tipo de cumplimiento" es independiente por request (no se persiste como preferencia de usuario); cada pantalla recuerda su última selección solo durante la sesión de navegación (estado de UI, no backend).
- Si el usuario no tiene programas asignados (`usuario_programa` vacío) en ninguna dependencia, los 4 reportes devuelven conteos en cero y las exportaciones generan archivos vacíos (con encabezados) en vez de error.
- Las exportaciones son síncronas (generación del `.xlsx` en la misma request); si el volumen de indicadores lo justifica, se puede mover a generación asíncrona en una fase posterior — fuera de alcance de Fase 3.
- Los cálculos de cumplimiento y color reutilizan exactamente las funciones de Fase 2 (mismo algoritmo, mismos rangos por indicador); Fase 3 no reimplementa lógica de cálculo, solo agrega y filtra.

## Criterios de aceptación

1. Los 4 endpoints de conteo devuelven el mismo total de indicadores para el mismo filtro de año/alcance, sin importar el agrupador (la suma de `verde+amarillo+rojo+gris` por grupo coincide con el total consolidado).
2. **Caso verificado en vivo** (Ejes, eje Económico, año 2025, sistema de referencia): 19 indicadores totales → 14 verde, 0 amarillo, 4 rojo, 1 gris. El nuevo sistema debe reproducir este resultado para el mismo conjunto de datos migrado (ajustado, si aplica, a la restricción por programas del usuario que hace la prueba).
3. **Caso verificado en vivo** (cálculo de cumplimiento, programa 1017 — Pobreza y desarrollo social, indicador 416, algoritmo `a`): sumatoria mensual 15+15+32+25+18 = 105 = meta alcanzada, con avance = programado. Debe reproducirse idéntico en el nuevo sistema.
4. La exportación Cuenta Pública genera exactamente 38 columnas en el orden y agrupación confirmados (Programa → Presupuesto → MIR → Indicadores, 2 filas por indicador).
5. La exportación Transparencia genera exactamente 26 columnas, 1 fila por indicador.
6. Un usuario sin acceso a ciertos programas de una dependencia nunca ve, en ningún reporte o exportación, indicadores de programas fuera de su `usuario_programa`, aunque pertenezcan a esa dependencia.
7. El filtro de selección múltiple de dependencias produce resultados equivalentes a consultar cada dependencia por separado y sumar (sin duplicados ni omisiones).

**Cobertura de testing (ver Fase 0 § Testing):** los casos 1, 2, 3, 6 y 7 son cálculo y reglas de negocio (invariante de conteo por color, reproducción del cálculo de cumplimiento, restricción por `usuario_programa`, equivalencia de selección múltiple) y se agregan como unit tests. Los casos 4 y 5 (estructura exacta de columnas de las exportaciones) quedan fuera del alcance mínimo de testing automatizado acordado; se verifican manualmente contra el sistema de referencia.

## Fuera de alcance y dependencias

- Presupuesto y ejercicio del gasto (Fase 4) — Fase 3 solo referencia `programa.clasificacion_pragmatica` para las columnas de exportación; no calcula ni gestiona montos presupuestales.
- Generación asíncrona/en segundo plano de exportaciones grandes — evaluar en fase posterior si el volumen de datos lo requiere.
- Cualquier formato de exportación adicional (PDF, CSV) más allá de `.xlsx` para Cuenta Pública y Transparencia.
- Dashboards o reportes ejecutivos adicionales no confirmados contra el sistema de referencia.

**Depende de:** Fase 2 (datos de MIR y cálculo de semáforo), Fase 1 (`usuario_programa`, `centro_gestor`, `eje`, `programa`, `clasificacion_pragmatica`).

## Decisiones de construcción (2026-10, verificadas contra el sistema de referencia)

- **Modo "(C.O/C.E)×100":** valor = cumplimiento obtenido (Fase 2) ÷ meta anual numérica × 100, redondeado a 2 decimales; es la misma cifra de "Avance / Programado" del export. La meta anual numérica es el mismo algoritmo aplicado a lo programado del año (`meta_anual` A y B). Meta nula o 0 → gris. **No se prorratea** en el año en curso (pendiente de verificación con datos de año en curso). Ambos modos usan los mismos rangos de color del indicador.
- **Fuera de los tres rangos = gris** (verificado en la referencia), no "sin color": así verde + amarillo + rojo + gris = total siempre. El detalle de Fase 2 sigue distinguiendo `sin_color` internamente.
- **Universo:** entran los 4 niveles de la MIR; un indicador entra solo con meta anual programada Y al menos un mes capturado en el año (año sin datos → 0/0/0/0, no todo gris). El caso "con meta pero sin capturas" queda fuera del conteo, **pendiente de verificación**.
- **Alcance (decisión 2026-10):** la misma regla de las demás fases (`programas.visibles`): administrador y alcalde ven todos los programas del municipio; el resto, solo los de su `usuario_programa`. Una sola función (`programas_en_alcance`) sirve a reportes, detalle, `/opciones` y exportaciones. Conteos: dependencia sin programas del usuario → grupo en 0. Exportaciones: programa fuera de alcance → `403 PROGRAMA_NO_ASIGNADO`. (Reemplaza la regla anterior de "sin bypass por tipo de usuario".)
- **Permisos de API:** `estadisticas` (informes, alcalde, administrador: Ejes, Cumplimiento de Metas, Consolidado, Cuenta Pública, Transparencia) y `estadisticas_dependencias` (suma presupuestación y control presupuestal: Dependencias, detalle y selectores).
- **Respuestas:** todos los conteos devuelven `grupos[{id, nombre, verde, amarillo, rojo, gris, total}]`; el % lo calcula el front. Parámetros de lista con `[]` (`centro_gestor_ids[]`, `eje_ids[]`). Se agrega `GET /api/estadisticas/opciones` (años, centros gestores, ejes y programas del alcance del usuario). Programas sin subtema caen en el grupo "Sin eje" de Ejes.
- **Cuenta Pública y Transparencia** (corrige el texto de arriba): filtros de selección única año + centro gestor + programa (solo los asignados al usuario); una sola hoja. `GET /api/estadisticas/{cuenta-publica|transparencia}` devuelve la tabla (botón Buscar) y `GET /api/estadisticas/exportar/{...}` el `.xlsx` (botón Exportar). Estructura, orden y agrupación tomados de `humanos/docs/referencias/indicadores_resultados.xls` y `transparencia.xls`.
- **Columnas vacías a propósito** (el sistema de referencia también las deja vacías o no hay dato): ejercicio fiscal, clasificación funcional, Aprobado…Pagado (Fase 4), meta programada (texto), meta modificada, fechas, definición, sentido, metas ajustadas, nota. **Pendientes de decidir:** "ID del indicador" (la referencia usa un id numérico que aquí no existe) y "Valor línea base" (hoy: meta anual numérica del año base, si existe).
- **Caso 3:** el "105" del criterio 3 no cuadra con la referencia; se usa la fila real de Transparencia (indicador 416, Fin, algoritmo A, meta 100, avance 86.00). Los rangos de color de los 19 indicadores de 2025 en los tests son **inferidos** (solo se conocen los del 410).
- **Gráficas:** SVG propio, sin librería (número sobre cada barra, tooltip con nombre y 4 conteos, clic a detalle Programa | Indicador | Cumplimiento).
