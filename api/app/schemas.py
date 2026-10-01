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
