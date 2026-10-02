import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import ColorBoton, EstadoMunicipio


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginIn(BaseModel):
    usuario: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1)  # sin reglas de complejidad (decisión del cliente)


class VerificarUsuarioIn(BaseModel):
    usuario: str = Field(min_length=1, max_length=100)


class MunicipioCrearIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=200)
    subdominio: str
    estado_republica_id: uuid.UUID | None = None
    logo_url: str | None = None
    admin_nombre: str = Field(min_length=1, max_length=200)
    admin_usuario: str = Field(min_length=1, max_length=100)
    admin_password: str | None = None  # vacío = generada

    @field_validator("admin_password")
    @classmethod
    def _vacio_es_none(cls, v):
        return v or None


class MunicipioEditarIn(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=200)
    estado_republica_id: uuid.UUID | None = None
    logo_url: str | None = None
    imagen_login_url: str | None = None
    color_boton: ColorBoton | None = None
    mostrar_logos: bool | None = None
    duracion_sesion_dias: int | None = None
    estado: EstadoMunicipio | None = None


class MunicipioOut(Out):
    id: uuid.UUID
    nombre: str
    subdominio: str
    estado: EstadoMunicipio
    estado_republica_id: uuid.UUID | None
    logo_url: str | None
    imagen_login_url: str | None
    color_boton: ColorBoton
    mostrar_logos: bool
    duracion_sesion_dias: int
    created_at: datetime


class PlantillaIn(BaseModel):
    clave: str = Field(min_length=1, max_length=32)
    nombre: str = Field(min_length=1)
    model_config = ConfigDict(extra="allow")  # columnas propias de cada catálogo


# --------------------------------------------------------------------------- Fase 1
class UsuarioCrearIn(BaseModel):
    nombre: str
    usuario: str
    password: str | None = None  # vacío = generada (se devuelve una vez)
    tipo: str
    direccion: str | None = None
    telefono: str | None = None
    email: str | None = None
    anios_acceso: list[int] = []
    meses_acceso: list[int] = []
    activo: bool = True
    programa_ids: list[uuid.UUID] | None = None

    @field_validator("password")
    @classmethod
    def _vacio_es_none(cls, v):
        return v or None


class UsuarioEditarIn(BaseModel):
    nombre: str | None = None
    usuario: str | None = None
    password: str | None = None
    tipo: str | None = None
    activo: bool | None = None
    direccion: str | None = None
    telefono: str | None = None
    email: str | None = None
    anios_acceso: list[int] | None = None
    meses_acceso: list[int] | None = None
    programa_ids: list[uuid.UUID] | None = None

    @field_validator("password")
    @classmethod
    def _vacio_es_none(cls, v):
        return v or None


class UsuariosBulkIn(BaseModel):
    filas: list[dict]  # cada fila se valida por separado: una inválida no descarta las demás


class ParIn(BaseModel):
    usuario_id: uuid.UUID
    programa_id: uuid.UUID


class MatrizGuardarIn(BaseModel):
    altas: list[ParIn] = []
    bajas: list[ParIn] = []


class CatalogoIn(BaseModel):
    clave: str | None = None
    nombre: str | None = None
    activo: bool | None = None
    centro_gestor_id: uuid.UUID | None = None  # ejes
    eje_id: uuid.UUID | None = None            # subtemas
    subtema_id: uuid.UUID | None = None        # estrategias


class ProgramaIn(BaseModel):
    ejercicio_fiscal: int | None = None
    clave: str | None = None
    nombre: str | None = None
    centro_gestor_id: uuid.UUID | None = None
    subtema_id: uuid.UUID | None = None
    estrategia_id: uuid.UUID | None = None
    clasificacion_programatica_id: uuid.UUID | None = None
    activo: bool | None = None


class ProgramaDuplicarIn(BaseModel):
    ejercicio_fiscal: int
    clave: str
    nombre: str | None = None


class ConfigEditarIn(BaseModel):
    imagen_login_url: str | None = None
    color_boton: ColorBoton | None = None
    mostrar_logos: bool | None = None
    meses_avance_activos: list[int] | None = None
    tolerancia_semaforo: int | None = None


class RecuperarIn(BaseModel):
    usuario: str = Field(min_length=1, max_length=100)


class RecuperarConfirmarIn(BaseModel):
    token: str = Field(min_length=1)
    password_nueva: str = Field(min_length=1)  # sin reglas de complejidad (decisión del cliente)


class CambiarPasswordIn(BaseModel):
    password_actual: str = Field(min_length=1)
    password_nueva: str = Field(min_length=1)
