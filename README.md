# Indicadores — monorepo

| Carpeta | Qué es | Despliegue |
| --- | --- | --- |
| `/front` | Next.js (App Router) + Bootstrap 3 con hoja de estilos propia (`styles/theme.css`) | Vercel, root directory `front` |
| `/api` | FastAPI + SQLAlchemy + Alembic, un solo Postgres compartido (aislado por `municipio_id`) | Railway, root directory `api` |

Especificación: ver los documentos `Panel Indicadores — …` en la raíz (Fase 0 = este código).

## Desarrollo local

Subdominios locales con `*.localhost` (Chrome/Firefox los resuelven a 127.0.0.1 sin tocar DNS).

```bash
# 1) Postgres
docker run -d --name indicadores-pg -e POSTGRES_USER=indicadores -e POSTGRES_PASSWORD=indicadores \
  -e POSTGRES_DB=indicadores -p 5433:5432 postgres:16-alpine

# 2) API
cd api && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
cp .env.example .env     # ROOT_DOMAIN=localhost, COOKIE_SECURE=false y una PASSWORD_ENCRYPTION_KEY
.venv/bin/alembic upgrade head
SEED_SUPER_ADMIN_USUARIO=root SEED_SUPER_ADMIN_PASSWORD='...' .venv/bin/python seed.py
.venv/bin/uvicorn app.main:app --port 8000

# 3) Front
cd front && npm install && cp .env.example .env.local   # ROOT_DOMAIN=localhost
npm run dev -- -p 3100
```

* Super admin: <http://admin.localhost:3100>
* Municipio: `http://<subdominio>.localhost:3100` (se da de alta desde el super admin)

## Pruebas

```bash
cd api && .venv/bin/pytest -q                      # SQLite en memoria
TEST_DATABASE_URL=postgresql+psycopg://… pytest -q   # contra Postgres real
```

## Variables de entorno

API: `DATABASE_URL`, `SESSION_SECRET`, `PASSWORD_ENCRYPTION_KEY` (32 bytes base64), `ROOT_DOMAIN`,
`SUPER_ADMIN_SUBDOMAIN` (=`admin`), `COOKIE_SECURE`, `ADMIN_SESSION_DIAS`; opcionales para imágenes:
`S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `MEDIA_PUBLIC_BASE_URL`.
Front: `API_URL`, `ROOT_DOMAIN`, `SUPER_ADMIN_SUBDOMAIN`.
