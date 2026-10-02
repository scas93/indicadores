# Indicadores — mapa del proyecto

Panel administrativo multi-tenant para municipios (réplica del sistema de
Insadisa, reconstruido con permiso del dueño). Ver humanos/docs/producto/ para el
contexto completo de negocio; este archivo es solo un mapa.

## Arquitectura (no renegociar sin avisar a Santiago)

- Monorepo: `/front` (Next.js App Router, Vercel) + `/api` (FastAPI, Railway).
- Multi-tenant por subdominio: `<municipio>.<dominio>` resuelto por middleware,
  un solo Postgres compartido, aislado por `municipio_id` en una capa común
  (nunca filtrado endpoint por endpoint). `admin.<dominio>` es el super admin,
  ámbito separado, sesiones no intercambiables entre los dos.
- Dos esquemas de contraseña a propósito: reversible para usuarios de
  municipio, hash para super admin — no es un descuido, está documentado en
  humanos/docs/fases/Panel Indicadores — Fase 0 Especificación técnica (Base e infraestructura).md.
- Migraciones con Alembic. Hoja de estilos propia basada en Bootstrap, sin
  librería de componentes (shadcn/MUI, etc.).

## Paridad visual — no negociable

Cada pantalla debe compararse contra la captura de referencia incluida en el
doc de su fase. No modernizar ni reinventar el flujo aunque parezca "mejor".
La diferencia aceptable contra el sistema de referencia se limita a textos o
logos del municipio.

## Testing

Unit tests de reglas de negocio críticas únicamente (pytest en `/api`,
validadores como funciones puras, separados de los handlers). No hay suite
de frontend ni meta de cobertura. Ver humanos/docs/fases/Panel Indicadores — Fase 0 Especificación técnica (Base e infraestructura).md
§ Testing para la convención completa.

## Fases — leer el doc correspondiente antes de tocar esa área

| Fase | Qué cubre | Doc |
|---|---|---|
| 0 | Infraestructura, multi-tenancy, super admin, login | humanos/docs/fases/Panel Indicadores — Fase 0 Especificación técnica (Base e infraestructura).md |
| 1 | Usuarios, permisos, catálogos de planeación | humanos/docs/fases/Panel Indicadores — Fase 1 Especificación técnica (Acceso y planeación).md |
| 2 | MIR — matriz de indicadores, metas, avances | humanos/docs/fases/Panel Indicadores — Fase 2 Especificación técnica (MIR).md |
| 3 | Estadísticas, exportaciones Cuenta Pública/Transparencia | humanos/docs/fases/Panel Indicadores — Fase 3 Especificación técnica (Estadísticas de indicadores).md |
| 4 | Presupuesto — techo, presupuestación, PbR | humanos/docs/fases/Panel Indicadores — Fase 4 Especificación técnica (Presupuesto).md |

Cada doc de fase trae, al final de su tabla de criterios de aceptación, una
nota de qué casos ya están cubiertos por unit test y cuáles son verificación
manual contra el sistema de referencia.
