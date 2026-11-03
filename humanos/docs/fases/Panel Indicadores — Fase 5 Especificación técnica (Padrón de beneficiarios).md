# Panel Indicadores — Fase 5: Especificación técnica (Padrón de beneficiarios)

Nov 3, 2026 · @santiago

> **Estado: verificada contra la referencia (2026-11-03).** Todo lo de este documento se revisó pantalla por pantalla en `demo-indicadores.insadisa.mx` con el usuario **2.- PADRON BENEFICIARIOS** (un solo programa asignado: [2076] Comedores Comunitarios). Lo que no se pudo confirmar está en *Pendientes menores*. No se guarda ningún dato personal real de beneficiarios: solo estructura de pantallas, catálogos y reportes.

## Resumen y alcance

Fase 5 es el módulo completo del tipo `padron` (usuario 2). Depende de Fase 1 (usuarios, programas, `usuario_programa`, `centro_gestor`) y reutiliza catálogos que Fase 0 ya carga como plantillas (geografía, grupos de edad, niveles socioeconómicos). No depende de Fase 2 ni de Fase 3.

Menú del usuario 2 en la referencia: **Catálogos** (Beneficiarios, Apoyos, Descripción de Apoyo, Nivel Socioeconómico, Grupo Edad, Localidades, Municipios, Colonias, Usuarios), **Estadísticas** (4 reportes) y **Padrón de Beneficiarios** (captura). La página de inicio muestra el selector de programa con las pestañas de MIR (Fase 2), con solo su programa asignado.

Entrega:

1. **8 catálogos del Padrón**: Beneficiarios (con su ficha de documentos), Apoyos, Descripciones de apoyo, Niveles socioeconómicos, Grupos de edad, Municipios, Localidades y Colonias. Usuarios es la consulta de Fase 1.
2. **Captura de entrega de apoyo** (pantalla "Padrón de Beneficiarios") con la tabla "Capturas del día" debajo.
3. **4 reportes**: Padrón Beneficiario (dashboard de 5 gráficas), Detalles Padrón Beneficiario, Comparativo Padrón Beneficiario y Reporte Documentos.

El tipo `padron` ve además Usuarios (consulta), igual que hoy. El `administrador` accede a todo lo de esta fase. El tipo `informes` no.

**Fuera de alcance:** Cancelación de Padrón (recortada el 2026-11-03), carga masiva de beneficiarios desde Excel, y cualquier reporte no listado aquí.

## Reglas de negocio

- **Programa:** el usuario solo captura y consulta sobre los programas de su `usuario_programa`. El centro gestor y la fecha de registro se autollenan (solo lectura).
- **Beneficiario vs. entrega:** el beneficiario es la persona (datos personales y domicilio); la **entrega** es cada captura de apoyo. La edad, el grupo de edad y el nivel socioeconómico se capturan **en la entrega**, no en el beneficiario, y se conservan tal como estaban ese día (la tabla "Capturas del día" los muestra por fila).
- **Edad y grupo de edad:** el grupo de edad se asigna según la edad capturada. Rangos de la referencia: 2-10 NIÑO, 11-17 ADOLESCENTE, 18-59 ADULTO, 60-80 TERCERA EDAD. Una edad fuera de todos los rangos se rechaza con error de validación (la referencia no lo documenta; decisión de construcción); el catálogo es editable para agregar rangos.
- **Apoyos y descripciones:** cada **Apoyo pertenece a un Programa** y cada **Descripción de apoyo pertenece a un Apoyo**. En la captura, el apoyo se elige con autocompletado y la descripción se filtra por el apoyo (p. ej. DESPENSAS → DESPENSAS BASICAS).
- **CURP:** única por municipio. En la captura se escribe o se selecciona de los beneficiarios existentes (autocompletado por CURP o por nombre).
- **Género:** es un dato del beneficiario (selector Femenino/Masculino). Los reportes lo usan para "Apoyos por género".
- **Documentos:** cada beneficiario tiene su ficha de documentos, abierta desde su fila en el catálogo. Cada documento tiene tipo (INE/IFE, CURP, COMPROBANTE DOMICILIO u OTRO), título (se llena con el tipo), observaciones y archivo adjunto. El Reporte Documentos lista a quien le falte INE/IFE, CURP o Comprobante de domicilio.
- **Borrado:** los catálogos se borran solo si nada los usa; el borrado de capturas y de beneficiarios pide confirmación.
- **Datos personales:** documentos en almacenamiento privado con enlaces temporales, acceso solo con permiso, bitácora de consultas y exportes (ver Riesgos del Documento de producto).

## Modelo de datos

Todas las tablas son de ámbito municipio (`municipio_id`), aisladas por la capa común. Los campos observados en la referencia están marcados con ✓.

| Tabla | Campos principales | Notas |
| --- | --- | --- |
| `beneficiario` | `curp` ✓ (única por municipio), `nombre` ✓ ("Apellido Paterno Materno Nombre(s)"), `fecha_nacimiento` ✓, `genero` ✓, `cp` ✓, `estado` ✓, `municipio` ✓, `localidad` ✓, `calle` ✓, `num` ✓, `colonia` ✓ (texto), `telefono` ✓, `correo` ✓ | Estado, municipio y localidad se eligen de los catálogos geográficos; la colonia del formulario es de texto libre en la referencia. |
| `documento` | `beneficiario_id`, `tipo` ✓ (INE/IFE, CURP, COMPROBANTE DOMICILIO, OTRO), `titulo` ✓, `observaciones` ✓, `archivo_ref` ✓ | Faltante = el beneficiario no tiene documento de ese tipo. Archivo en almacenamiento privado. |
| `apoyo` | `clave` ✓, `nombre` ✓, `programa_id` ✓, `observaciones` ✓ | Vacío al crear el municipio. |
| `descripcion_apoyo` | `clave` ✓, `nombre` ✓, `apoyo_id` ✓, `observaciones` ✓ | Vacío al crear el municipio. |
| `entrega` | `beneficiario_id`, `programa_id` ✓, `apoyo_id` ✓, `descripcion_apoyo_id` ✓, `edad` ✓, `grupo_edad_id` ✓, `nivel_socioeconomico_id` ✓, `cantidad` ✓ (default 1), `fecha_entrega` ✓ (default hoy), `observaciones` ✓, `fecha_registro` ✓ (autollenada) | El centro gestor se deriva del programa. |
| `grupo_edad` | `nombre` ✓, rango mínimo-máximo ✓ | Copia de la plantilla de Fase 0. |
| `nivel_socioeconomico` | `nombre` ✓ (Muy bajo, Bajo, Medio, Alto) | Sin clave. Copia de la plantilla de Fase 0. |
| `municipio_geo`, `localidad`, `colonia` | `clave` ✓, `nombre` ✓; la localidad tiene municipio y estado ✓; la **colonia tiene estado y municipio** ✓ (no localidad) | En la referencia vienen precargados con Guanajuato (claves tipo `[015]GUANAJUATO`). Los tres son editables. |

## Endpoints de la API

Ámbito municipio. Tipos permitidos: `padron` y `administrador`. Todo endpoint valida tipo y programa en el servidor (no basta con ocultar el menú).

| Método y ruta | Qué hace |
| --- | --- |
| `GET/POST/PATCH/DELETE /api/apoyos`, `/api/descripciones-apoyo` | CRUD de catálogos (búsqueda por clave y nombre); borrado solo si nada los usa. |
| `GET/POST/PATCH/DELETE /api/grupos-edad`, `/api/niveles-socioeconomicos` | CRUD sobre la copia del municipio. |
| `GET/POST/PATCH/DELETE /api/geo/municipios`, `/api/geo/localidades`, `/api/geo/colonias` | CRUD sobre la copia del municipio. |
| `GET /api/beneficiarios?curp=&nombre=` | Búsqueda, listado y autocompletado. |
| `POST/PATCH/DELETE /api/beneficiarios` | Alta, edición y borrado. Valida CURP única por municipio. |
| `GET/POST /api/beneficiarios/{id}/documentos`, `GET .../{doc_id}` | Ficha de documentos: lista, subida y descarga (enlace temporal). |
| `POST /api/entregas`, `GET /api/entregas?fecha=hoy`, `DELETE /api/entregas/{id}` | Captura, "Capturas del día" y borrado. |
| `GET /api/padron/estadisticas/resumen` | Datos de las 5 gráficas del dashboard. |
| `GET /api/padron/estadisticas/detalle` | Reporte Detallado; `?formato=xlsx` exporta. |
| `GET /api/padron/estadisticas/comparativo` | Comparativo por año. |
| `GET /api/padron/estadisticas/documentos` | Reporte de documentos faltantes; `?formato=xlsx` exporta. |

Los catálogos y reportes tienen botón **Exportar** en la referencia.

## Pantallas del frontend

Cada pantalla se compara contra la referencia antes de darse por cerrada (paridad visual). **[Pendiente]:** guardar las capturas de referencia del usuario 2 en `referencias/`.

### Catálogos
Todos con el mismo patrón: sección de búsqueda (filtros + **Buscar**, **Nuevo**, **Exportar**), tabla con casillas ("Todo"), columna Acciones (editar, eliminar) y botón de eliminar en lote debajo; alta y edición en modal "Ingresar / Modificar …" con **Guardar**.

- **Beneficiarios:** búsqueda por CURP y Beneficiario; columnas Curp y Beneficiario; acciones **editar**, **documentos** (ícono morado) y eliminar. Formulario: Curp, Nombre, Fecha Nacimiento, Género, CP, Estado, Municipio, Localidad, Calle, Num, Colonia, Teléfono, Correo. Modal de documentos "Alta y Visualización de Documentos": Tipo Documento, Título, Observaciones, Adjunto, **Guardar**, y abajo la lista "Documentos del beneficiario".
- **Apoyos:** búsqueda por Clave y Apoyo; columnas Clave, Apoyo, Observaciones. Formulario: Clave, Nombre, Programa (autocompletado), Observaciones.
- **Descripción de Apoyo:** búsqueda por Clave y Descripción de Apoyo; columnas Clave, Descripción de Apoyo, Observaciones. Formulario: Clave, Nombre, Apoyo (autocompletado), Observaciones.
- **Nivel Socioeconómico:** búsqueda por Nivel; una columna.
- **Grupo Edad:** búsqueda por Edad; columnas Edad y Rango min-max.
- **Localidades:** búsqueda por Clave y Localidad; columnas Clave, Localidad, Municipio, Estado.
- **Municipios:** búsqueda por Clave y Municipio; columnas Clave, Municipio, Estado.
- **Colonias:** búsqueda por Clave y Colonia; columnas Clave, Colonia, Estado, Municipio.

### Padrón de Beneficiarios (captura)
Tres bloques: **Datos del programa** (selector de programa, Centro Gestor y Fecha Registro de solo lectura) · **Datos del beneficiario** (Curp con ícono de edición, Nombre, Edad, Grupo de Edad, Nivel Socioeconómico, Apoyo, Cantidad, Descripción de Apoyo con ícono de edición, Fecha de Entrega, Observaciones, **Guardar**) · **Capturas del día** (tabla con CURP, Nombre, Edad, Grupo Edad, Niv. Socioeconómico, Apoyo, Cantidad, Descrip.Apoyo, Observaciones y acciones).

### Estadísticas del padrón
- **Padrón Beneficiario:** filtros Programas (selección múltiple), Apoyo, Descripción Apoyo, Estado, Municipio, Localidad, Fecha Inicial y Fecha Final, y botón **Generar Graficas**. Resultado: (1) gráfica de barras "Numero de Apoyos por Localidad" con tabla "Localidad Top 5"; (2) "Apoyos por Genero" con porcentaje Femenino y Masculino; (3) "Apoyos Por Grupo de Edad"; (4) "Apoyos por Nivel Socioeconómico"; (5) "Apoyos Otorgados" (gráfica y tabla con total por apoyo). Las etiquetas de localidad y apoyo se muestran como `[clave]Nombre`.
- **Detalles Padrón Beneficiario:** filtros Programas, Apoyo, Descripción Apoyo, Estado, Municipio, Localidad, CURP, Nombre, Fecha Inicial, Fecha Final, Año Inicial, Año Final y Tipo (Detallado); botones **Generar Reporte** y **Exportar**. Tabla "DETALLADO PADRON BENEFICIARIO" con 16 columnas: CURP, Nombre, Estado, Municipio, Localidad, Colonia, Edad, Grupo Edad, Nivel Socioeconómico, Apoyo, Descrip.Apoyo, Programa, Fecha de Entrega, Centro Gestor, Cantidad, Observación.
- **Comparativo Padrón Beneficiario:** filtros Programas, Apoyo, Descripción Apoyo, Estado, Municipio, Localidad, Año Inicial y Año Final; botón **Generar Reporte**. Resultado: tabla "APOYOS OTORGADOS POR LOCALIDAD TOP 5" con Total y una columna por año, y debajo la gráfica "Comparativo — Top 5 Localidades".
- **Reporte Documentos:** filtros CURP, Nombre y Documento Faltante (TODOS, INE/IFE, CURP, COMPROBANTE DE DOMICILIO); botones **Generar Reporte** y **Exportar**. Tabla "REPORTE FALTA DE DOCUMENTOS" con CURP, Nombre, Estado, Municipio, Localidad, Colonia, Tel. y Correo.

## Criterios de aceptación

1. La edad asigna el grupo de edad con los rangos de la referencia, y la captura guarda edad, grupo y nivel socioeconómico de ese día.
2. Un apoyo solo aparece para los programas a los que pertenece, y la descripción se filtra por el apoyo elegido.
3. Una CURP repetida en el alta de un beneficiario se rechaza; en la captura, una CURP existente se autocompleta.
4. El Reporte Documentos lista a cada beneficiario al que le falte el tipo de documento elegido.
5. Un usuario `padron` nunca ve entregas ni beneficiarios de programas que no tiene asignados, ni por la API directa.
6. Un usuario `informes` no puede llamar los endpoints de esta fase (403).
7. Los 4 reportes aplican sus filtros y las columnas coinciden con las de la referencia.
8. **Prueba de paridad:** capturar el mismo lote de entregas (con datos ficticios) en ambos sistemas y comparar el Top 5 de localidades y las 5 gráficas.

**Cobertura de testing (ver Fase 0 § Testing):** los criterios 1–3, 5 y 6 son reglas de negocio y se agregan como unit tests; el 4 se prueba con datos sintéticos; el 7 y el 8 son verificación manual contra la referencia.

## Decisiones de construcción

- **Colonias:** en la referencia vienen precargadas (Guanajuato). La plantilla de geografía de Fase 0 no las trae, así que en el sistema nuevo el catálogo arranca vacío y lo llena el Padrón o el Administrador. Es la única diferencia intencional frente a la referencia en datos precargados.
- **Edad fuera de los 4 rangos:** se rechaza; la referencia no lo documenta.
- **Documentos:** archivo en almacenamiento privado, no en base de datos.

## Pendientes menores (no bloquean la construcción)

1. Opciones del campo **Tipo** en Detalles además de "Detallado" (probablemente "Concentrado").
2. Qué hacen los íconos de lápiz junto a **Curp** y **Descripción de Apoyo** en la pantalla de captura (se asume edición rápida del beneficiario y de la descripción).
3. Si el campo **Colonia** del formulario de beneficiario autocompleta desde el catálogo de colonias o es texto libre.
4. Opciones completas del selector **Género** (se vieron Femenino por defecto y, en el dashboard, Femenino y Masculino).
5. Si el borrado de capturas pide escribir "eliminar" en este módulo.
6. Los Excel que generan los botones **Exportar** (se asumen las mismas columnas que las tablas en pantalla).

## Fuera de alcance y dependencias

- Cancelación de Padrón, importación masiva de beneficiarios y cualquier reporte no listado arriba.
- Generación asíncrona de exportes grandes.

**Depende de:** Fase 0 (plantillas de geografía, grupos de edad y niveles socioeconómicos; almacenamiento privado) y Fase 1 (`usuario_programa`, `centro_gestor`, `programa`, tipos de usuario).
