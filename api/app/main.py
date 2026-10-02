from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .errors import ApiError, TenantViolation
from .routers import (admin_auth, arbol, auth, config, matriz, mir, municipios, planeacion, plantillas,
                      uploads, usuarios)

app = FastAPI(title="Indicadores API", docs_url="/api/docs", openapi_url="/api/openapi.json")


@app.exception_handler(ApiError)
async def _api_error(_: Request, e: ApiError):
    return JSONResponse(
        {"codigo": e.codigo, "mensaje": e.mensaje, "campos": e.campos}, status_code=e.status)


@app.exception_handler(TenantViolation)
async def _tenant(_: Request, e: TenantViolation):
    return JSONResponse({"codigo": "MUNICIPIO_NO_COINCIDE", "mensaje": str(e), "campos": {}},
                        status_code=403)


@app.exception_handler(RequestValidationError)
async def _validation(_: Request, e: RequestValidationError):
    campos = {}
    for err in e.errors():
        loc = [str(p) for p in err["loc"] if p not in ("body", "query", "path")]
        campos[".".join(loc) or "_"] = err["msg"]
    return JSONResponse({"codigo": "VALIDACION", "mensaje": "Datos inválidos", "campos": campos},
                        status_code=422)


@app.get("/api/health")
def health():
    return {"ok": True}


# matriz antes que usuarios: "/api/usuarios/matriz" no debe caer en "/api/usuarios/{id}"
for r in (auth.router, admin_auth.router, municipios.router, plantillas.router, uploads.router,
          matriz.router, usuarios.router, usuarios.admin_router, planeacion.router, config.router, arbol.router, mir.router):
    app.include_router(r)

_up = Path(get_settings().upload_dir)
_up.mkdir(parents=True, exist_ok=True)
app.mount("/api/media", StaticFiles(directory=_up), name="media")
