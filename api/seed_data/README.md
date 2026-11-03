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

## Geografía: carga y copia a municipios existentes

Los CSV de geografía se cargan **por estado**, son tolerantes (una localidad cuyo municipio o estado no
existe se omite y se reporta, sin abortar) y se pueden repetir sin duplicar. Los municipios que se crean
después reciben su geografía automáticamente; los que **ya existen** (p. ej. `demo`) necesitan el paso 2.

### En staging (Railway)

Los CSV deben estar versionados en `api/seed_data/` y desplegados (el contenedor solo trae lo commiteado).

```bash
# 1. Cargar las plantillas (un estado a la vez; 11 = Guanajuato). Imprime estados/municipios/localidades
#    cargados, existentes y omitidos.
railway ssh -s outstanding-gratitude -e staging -- python cargar_geografia.py --estado 11

# 2. Ver qué se copiaría a demo, sin escribir
railway ssh -s outstanding-gratitude -e staging -- python copiar_geografia.py --subdominio demo --dry-run

# 3. Copiar a demo (solo agrega lo que falta del estado del municipio; no pisa lo editado)
railway ssh -s outstanding-gratitude -e staging -- python copiar_geografia.py --subdominio demo
```

Repetir el 1 o el 3 no agrega nada. El municipio debe tener su estado de la república asignado.
`--todos` en lugar de `--subdominio demo` copia a todos los municipios. Si el municipio borró una fila de
la plantilla, la copia la vuelve a agregar. Las colonias no tienen fuente de datos y no se tocan.
