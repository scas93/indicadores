# Panel Indicadores — Fase 5: Especificación técnica (Padrón de beneficiarios)

Nov 3, 2026 · @santiago

> **Estado: lista para construir (2026-11-03).** Se levantó en el sistema de referencia con el **usuario 2** (tipo PADRON BENEFICIARIOS, un solo programa asignado: Comedores Comunitarios, centro gestor DIF). Se perdió el acceso a ese usuario antes de cerrar la verificación, así que los puntos que no se pudieron confirmar quedaron resueltos con **decisiones de construcción** (sección *Decisiones de construcción*), marcadas como **sin verificar contra la referencia**. No se capturó ni se guarda ningún dato personal real de beneficiarios: todo lo de abajo es estructura de pantallas y catálogos.

## Resumen y alcance

Fase 5 es el módulo completo del tipo `padron` (usuario 2). Depende de Fase 1 (usuarios, programas, `usuario_programa`, `centro_gestor`) y reutiliza catálogos que Fase 0 ya carga como plantillas (geografía, grupos de edad, niveles socioeconómicos). No depende de Fase 2 ni de Fase 3.

Entrega:

1. **Catálogos propios del Padrón** (8): Apoyos, Descripciones de apoyo, Grupos de edad, Niveles socioeconómicos, Municipios, Localidades, Colonias y Beneficiarios.
2. **Captura de beneficiario y de su entrega de apoyo** (pantalla "Padrón de Beneficiarios") con la tabla "Capturas del día" debajo, y borrado con confirmación.
3. **4 reportes de estadísticas del padrón**: Padrón Beneficiario (dashboard de 5 gráficas), Detalles Padrón Beneficiario, Comparativo Padrón Beneficiario y Reporte Documentos.

El tipo `padron` ve además el módulo de Usuarios (solo consulta), igual que hoy. El `administrador` accede a todo lo de esta fase.

**Fuera de alcance:** Cancelación de Padrón (recortada el 2026-11-03), carga masiva de beneficiarios desde Excel, y cualquier reporte del padrón no confirmado contra la referencia.

## Reglas de negocio

- **Programa:** el usuario solo captura y consulta sobre los programas de su `usuario_programa`. El centro gestor y la fecha de registro se autollenan (no se editan).
- **Edad y grupo de edad:** el grupo de edad se asigna automáticamente a partir de la edad. Rangos observados: 2–10 Niño, 11-17 Adolescente, 18-59 Adulto, 60-80 Tercera edad. Una edad fuera de todos los rangos se rechaza con error de validación; el Administrador puede agregar grupos (p. ej. 0-1) en el catálogo.
- **Apoyo y descripción:** la descripción de apoyo es una lista en cascada filtrada por el apoyo elegido (p. ej. DESPENSAS → DESPENSAS BASICAS). El apoyo se elige de un catálogo con autocompletado. Solo aparecen los apoyos del programa elegido (regla del Documento de producto).
- **CURP:** única por municipio. Al escribirla, se autocompleta contra un beneficiario ya existente del padrón (nombre y datos), para no duplicar a la persona.
- **Entrega:** cada captura es una entrega de apoyo a un beneficiario (apoyo, descripción, cantidad, fecha de entrega, observaciones). La entrega guarda la foto del momento (edad, grupo de edad y nivel socioeconómico tal como estaban al entregar), de modo que un cambio posterior en el beneficiario no reescribe reportes pasados.
- **Borrado:** eliminar una captura o un beneficiario pide confirmación escribiendo "eliminar". Los catálogos del padrón se borran, pero solo si nada los usa.
- **Género:** no se captura ni se guarda. Se deriva de la CURP (carácter 11: H o M) al calcular los reportes; cualquier otro valor se cuenta como "No especificado".
- **Documentos:** cada beneficiario tiene su ficha con 3 tipos de documento (INE/IFE, CURP y Comprobante de domicilio), cada uno con subida de archivo. El Reporte Documentos lista a quien le falte cada tipo.
- **Datos personales:** documentos en almacenamiento privado con enlaces temporales, acceso solo con permiso, bitácora de consultas y exportes (ver Riesgos del Documento de producto).

## Modelo de datos

Todas las tablas son de ámbito municipio (`municipio_id`), aisladas por la capa común. **Propuesta**; los campos observados en la referencia están marcados con ✓.

| Tabla | Campos principales | Notas |
| --- | --- | --- |
| `beneficiario` | `id`, `municipio_id`, `curp` ✓ (única por municipio), `nombre` ✓, `edad` ✓, `nivel_socioeconomico_id` ✓, geografía (`municipio_geo_id`, `localidad_id`, `colonia_id`) | No se capturan domicilio ni fecha de nacimiento (no están en la referencia). El género no se guarda: se deriva de la CURP. |
| `documento` | `id`, `beneficiario_id`, `tipo` (`ine`, `curp`, `comprobante_domicilio`) ✓, `archivo_ref`, `entregado_en` | Faltante = no existe fila del tipo. Archivo en almacenamiento privado. |
| `apoyo` | `id`, `municipio_id`, `clave`, `nombre` ✓ | Vacío al crear el municipio. |
| `descripcion_apoyo` | `id`, `apoyo_id` ✓, `nombre` ✓ | Cascada filtrada por apoyo. |
| `entrega` | `id`, `beneficiario_id`, `programa_id` ✓, `apoyo_id` ✓, `descripcion_apoyo_id` ✓, `cantidad` ✓, `fecha_entrega` ✓, `observaciones` ✓, `fecha_registro` ✓ (autollenada), foto del momento: `edad`, `grupo_edad_id`, `nivel_socioeconomico_id` | `centro_gestor` se deriva del programa. |
| `grupo_edad` | `id`, `municipio_id`, `nombre` ✓, `edad_min`, `edad_max` ✓ | Copia de la plantilla de Fase 0. |
| `nivel_socioeconomico` | `id`, `municipio_id`, `nombre` ✓ (Muy bajo, Bajo, Medio, Alto) | Copia de la plantilla de Fase 0. |
| `municipio_geo`, `localidad`, `colonia` | jerarquía municipio → localidad → colonia | Municipios y localidades: copia de la plantilla de geografía de Fase 0. **Colonias no vienen en esa plantilla**: arrancan vacías y las captura el Padrón o el Administrador. |

## Endpoints de la API

Ámbito municipio. Tipos permitidos: `padron` y `administrador`, salvo donde se indica. Todo endpoint valida tipo y programa en el servidor (no basta con ocultar el menú).

| Método y ruta | Qué hace |
| --- | --- |
| `GET/POST/PATCH/DELETE /api/apoyos`, `/api/descripciones-apoyo` | CRUD de catálogos; borrado solo si nada los usa. |
| `GET/POST/PATCH/DELETE /api/grupos-edad`, `/api/niveles-socioeconomicos` | CRUD sobre la copia del municipio. |
| `GET/POST/PATCH/DELETE /api/geo/municipios`, `/api/geo/localidades`, `/api/geo/colonias` | CRUD sobre la copia del municipio. |
| `GET /api/beneficiarios?curp=&nombre=` | Búsqueda y autocompletado por CURP o nombre. |
| `POST/PATCH /api/beneficiarios` | Alta/edición. Valida CURP única por municipio. |
| `POST /api/entregas` | Captura una entrega; asigna grupo de edad por la edad y guarda la foto del momento. |
| `GET /api/entregas?fecha=hoy` | "Capturas del día". |
| `DELETE /api/entregas/{id}`, `DELETE /api/beneficiarios/{id}` | Borrado con confirmación en el front; la API exige el flag de confirmación. |
| `GET /api/padron/estadisticas/resumen` | Datos de las 5 gráficas del dashboard. |
| `GET /api/padron/estadisticas/detalle` | Reporte filtrable (Detallado o Concentrado); `?formato=xlsx` exporta. |
| `GET /api/padron/estadisticas/comparativo` | Comparativo año contra año. |
| `GET /api/padron/estadisticas/documentos` | Reporte de documentos faltantes por beneficiario. |
| `POST /api/beneficiarios/{id}/documentos`, `GET .../documentos/{doc_id}` | Subida y descarga (enlace temporal). |

## Pantallas del frontend

Cada pantalla se compara contra su captura de referencia antes de darse por cerrada (paridad visual). **[Pendiente]:** guardar las capturas de referencia del usuario 2 en `referencias/` como se hizo con las demás fases.

### Catálogos
Ocho entradas bajo el menú Catálogos: Beneficiarios (con su ficha de documentos: subida, descarga y estado de cada uno de los 3 tipos), Apoyos, Descripciones de apoyo, Niveles socioeconómicos, Grupos de edad, Municipios, Localidades y Colonias. Mismo patrón de tabla de los catálogos de Fase 1 (alta, edición, borrado condicionado).

### Padrón de Beneficiarios (captura)
Formulario en este orden: Programa → Centro gestor y Fecha de registro (autollenados) · CURP (autocompletado) y Nombre · Edad · Grupo de edad (lista desplegable que se asigna sola) · Nivel socioeconómico · Apoyo (autocompletado) + Descripción de apoyo (cascada) · Cantidad · Fecha de entrega · Observaciones. Debajo, tabla **Capturas del día** con borrado confirmado.

### Estadísticas del padrón
- **Padrón Beneficiario:** dashboard de 5 gráficas. Núm. de apoyos por localidad (con tabla Top 5), Apoyos por género (%), Apoyos por grupo de edad, Apoyos por nivel socioeconómico y Apoyos otorgados por tipo (con tabla).
- **Detalles Padrón Beneficiario:** filtros por programa, apoyo, descripción, estado, municipio, localidad, CURP, nombre, rango de fechas y año inicial/final; tipo Detallado o Concentrado; exportar.
- **Comparativo Padrón Beneficiario:** los mismos filtros, comparando año contra año (p. ej. localidad × año).
- **Reporte Documentos:** CURP/Nombre y tipo de documento faltante (INE/IFE, CURP, Comprobante de domicilio).

## Criterios de aceptación

1. La edad asigna el grupo de edad automáticamente, con los rangos observados.
2. Solo aparecen los apoyos del programa elegido, y la descripción se filtra por el apoyo.
3. Una CURP existente se autocompleta y no se duplica; una CURP repetida en alta se rechaza.
4. La entrega guarda la foto del momento: editar al beneficiario después no cambia los reportes de entregas pasadas.
5. El Reporte Documentos lista a cada beneficiario que le falte cada tipo de documento.
6. Un usuario `padron` nunca ve entregas ni beneficiarios de programas que no tiene asignados, ni por la API directa.
7. Un usuario `informes` no puede llamar los endpoints de esta fase (403).
8. Eliminar pide escribir "eliminar"; sin confirmación la API rechaza el borrado.
9. **Prueba de paridad:** capturar el mismo lote de entregas en ambos sistemas y comparar el Top 5 de localidades y las 5 gráficas.

**Cobertura de testing (ver Fase 0 § Testing):** los criterios 1–4 y 6–8 son reglas de negocio y se agregan como unit tests; el 5 se prueba con datos sintéticos; el 9 es verificación manual contra la referencia, con datos ficticios.

## Decisiones de construcción (2026-11-03, sin verificar contra la referencia)

No se pudo volver a entrar como usuario 2 en la referencia. Estos puntos se resolvieron así; si se recupera el acceso, se contrastan y se ajusta lo que difiera.

1. **Género:** se deriva de la CURP; no hay campo en el formulario. *(Hipótesis: la referencia hace lo mismo.)*
2. **Fecha de nacimiento y domicilio:** no se capturan; el formulario replica solo los campos observados.
3. **Documentos:** se suben en la ficha del beneficiario (catálogo Beneficiarios), no en la pantalla de captura.
4. **Grupos de edad:** los 4 observados (2-10, 11-17, 18-59, 60-80). Una edad fuera de rango se rechaza; el catálogo es editable para agregar rangos.
5. **Colonias:** catálogo vacío al crear el municipio; lo llena el Padrón o el Administrador.
6. **Exportes de Detalles y Comparativo:** las columnas se definen a partir de los filtros y de la estructura observada (no hay Excel de muestra). Es lo menos seguro de esta fase: con un Excel real de la referencia se ajusta.
7. **Apoyos:** catálogo general del municipio; en la captura se ofrecen los apoyos del programa elegido, y la regla exacta de esa relación se define al construir la captura.

## Fuera de alcance y dependencias

- Cancelación de Padrón, importación masiva de beneficiarios y cualquier reporte del padrón no listado arriba.
- Generación asíncrona de exportes grandes.

**Depende de:** Fase 0 (plantillas de geografía, grupos de edad y niveles socioeconómicos; almacenamiento privado) y Fase 1 (`usuario_programa`, `centro_gestor`, `programa`, tipos de usuario).
