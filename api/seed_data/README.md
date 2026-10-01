# Datos de seed

`seed.py` carga catálogos embebidos mínimos (estados INEGI, frecuencias, dimensiones, algoritmos,
clasificación programática y CONAC de muestra). Para cargar los catálogos completos, deja CSV aquí
(UTF-8, con encabezado) y vuelve a correr el seed (es idempotente, no duplica):

| Archivo | Columnas |
| --- | --- |
| `geografia_municipio.csv` | `estado_clave,clave,nombre` (clave INEGI del municipio, p. ej. `11,003,Apaseo el Alto`) |
| `geografia_localidad.csv` | `estado_clave,municipio_clave,clave,nombre` |
| `conac.csv` | `nivel,clave,nombre,padre_clave` (nivel: capitulo, partida, partida_especifica, articulo) |
| `grupo_edad.csv` | `clave,nombre,edad_min,edad_max` (reemplaza los de ejemplo) |
| `nivel_socioeconomico.csv` | `clave,nombre` (reemplaza los de ejemplo) |
