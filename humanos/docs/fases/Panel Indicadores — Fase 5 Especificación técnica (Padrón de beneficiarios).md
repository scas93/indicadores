# Panel Indicadores — Fase 5: Especificación técnica (Padrón de beneficiarios)

Nov 3, 2026 · @santiago

> **Estado: borrador.** Se levantó en el sistema de referencia con el **usuario 2** (tipo PADRON BENEFICIARIOS, un solo programa asignado: Comedores Comunitarios, centro gestor DIF). Lo marcado **[Por verificar]** no se pudo confirmar en la referencia o contradice otro documento; está concentrado en la sección *Pendientes de verificación*. No se capturó ni se guarda ningún dato personal real de beneficiarios: todo lo de abajo es estructura de pantallas y catálogos.

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
- **Edad y grupo de edad:** el grupo de edad se asigna automáticamente a partir de la edad. Rangos observados: 2–10 Niño, 11-17 Adolescente, 18-59 Adulto, 60-80 Tercera edad. **[Por verificar]** qué pasa con 0-1 y con más de 80.
- **Apoyo y descripción:** la descripción de apoyo es una lista en cascada filtrada por el apoyo elegido (p. ej. DESPENSAS → DESPENSAS BASICAS). El apoyo se elige de un catálogo con autocompletado. Solo aparecen los apoyos del programa elegido (regla del Documento de producto).
- **CURP:** única por municipio. Al escribirla, se autocompleta contra un beneficiario ya existente del padrón (nombre y datos), para no duplicar a la persona.
- **Entrega:** cada captura es una entrega de apoyo a un beneficiario (apoyo, descripción, cantidad, fecha de entrega, observaciones). La entrega guarda la foto del momento (edad, grupo de edad y nivel socioeconómico tal como estaban al entregar), de modo que un cambio posterior en el beneficiario no reescribe reportes pasados.
- **Borrado:** eliminar una captura o un beneficiario pide confirmación escribiendo "eliminar". Los catálogos del padrón se borran, pero solo si nada los usa.
- **Documentos:** se rastrea qué documentos tiene entregados cada beneficiario: INE/IFE, CURP y Comprobante de domicilio. El Reporte Documentos lista a quien le falte cada tipo.
- **Datos personales:** documentos en almacenamiento privado con enlaces temporales, acceso solo con permiso, bitácora de consultas y exportes (ver Riesgos del Documento de producto).

## Modelo de datos

Todas las tablas son de ámbito municipio (`municipio_id`), aisladas por la capa común. **Propuesta**; los campos observados en la referencia están marcados con ✓.

| Tabla | Campos principales | Notas |
| --- | --- | --- |
| `beneficiario` | `id`, `municipio_id`, `curp` ✓ (única por municipio), `nombre` ✓, `edad` ✓, `nivel_socioeconomico_id` ✓, geografía (`municipio_geo_id`, `localidad_id`, `colonia_id`) | Domicilio, fecha de nacimiento y género **[Por verificar]**: no aparecen en la pantalla de captura observada. |
| `documento` | `id`, `beneficiario_id`, `tipo` (`ine`, `curp`, `comprobante_domicilio`) ✓, `archivo_ref`, `entregado_en` | Faltante = no existe fila del tipo. Archivo en almacenamiento privado. |
| `apoyo` | `id`, `municipio_id`, `clave`, `nombre` ✓ | Vacío al crear el municipio. |
| `descripcion_apoyo` | `id`, `apoyo_id` ✓, `nombre` ✓ | Cascada filtrada por apoyo. |
| `entrega` | `id`, `beneficiario_id`, `programa_id` ✓, `apoyo_id` ✓, `descripcion_apoyo_id` ✓, `cantidad` ✓, `fecha_entrega` ✓, `observaciones` ✓, `fecha_registro` ✓ (autollenada), foto del momento: `edad`, `grupo_edad_id`, `nivel_socioeconomico_id` | `centro_gestor` se deriva del programa. |
| `grupo_edad` | `id`, `municipio_id`, `nombre` ✓, `edad_min`, `edad_max` ✓ | Copia de la plantilla de Fase 0. |
| `nivel_socioeconomico` | `id`, `municipio_id`, `nombre` ✓ (Muy bajo, Bajo, Medio, Alto) | Copia de la plantilla de Fase 0. |
| `municipio_geo`, `localidad`, `colonia` | jerarquía municipio → localidad → colonia | Municipios y localidades: copia de la plantilla de geografía de Fase 0. **Colonias no vienen en esa plantilla**: arrancan vacías y las captura el Padrón **[Por verificar]**. |

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
Ocho entradas bajo el menú Catálogos: Beneficiarios, Apoyos, Descripciones de apoyo, Niveles socioeconómicos, Grupos de edad, Municipios, Localidades y Colonias. Mismo patrón de tabla de los catálogos de Fase 1 (alta, edición, borrado condicionado).

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

## Pendientes de verificación (en la referencia, con el usuario 2)

1. **Género:** una gráfica es "Apoyos por género", pero la captura no tiene campo de género. **Hipótesis:** se deriva de la CURP. Confirmar.
2. **Fecha de nacimiento y domicilio:** el Documento de producto habla de validar la CURP contra fecha de nacimiento y domicilio, pero la captura observada solo pide Edad. Confirmar si existen en otra pantalla (p. ej. el catálogo Beneficiarios).
3. **Dónde se suben los documentos** (INE/IFE, CURP, comprobante): la pantalla de captura no los muestra, aunque el Reporte Documentos implica que se rastrean.
4. **Grupos de edad:** qué pasa con 0-1 y con más de 80 años.
5. **Colonias:** el Documento de producto dice que vienen copiadas del estado, pero la plantilla de geografía de Fase 0 no las incluye.
6. **Columnas reales** de los exportes de Detalles y Comparativo (descargar un Excel de muestra).
7. **Alcance por programa de los apoyos:** confirmar si el catálogo de apoyos se filtra por programa o por centro gestor.

## Fuera de alcance y dependencias

- Cancelación de Padrón, importación masiva de beneficiarios y cualquier reporte del padrón no listado arriba.
- Generación asíncrona de exportes grandes.

**Depende de:** Fase 0 (plantillas de geografía, grupos de edad y niveles socioeconómicos; almacenamiento privado) y Fase 1 (`usuario_programa`, `centro_gestor`, `programa`, tipos de usuario).
