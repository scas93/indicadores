import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, CheckConstraint, DateTime, Enum, ForeignKey,
                        Integer, String, Text, TypeDecorator, UniqueConstraint, Uuid)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column, relationship


class UTCDateTime(TypeDecorator):
    """timestamptz portable: siempre devuelve datetimes con tzinfo=UTC."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value


JSONType = JSON().with_variant(JSONB(), "postgresql")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _enum(cls: type[enum.Enum]) -> Enum:
    # VARCHAR + CHECK en vez de tipo ENUM nativo: migraciones más simples.
    return Enum(cls, native_enum=False, length=32, values_callable=lambda e: [m.value for m in e])


class Base(DeclarativeBase):
    pass


class ColorBoton(str, enum.Enum):
    default = "default"
    primary = "primary"  # #A978D1
    info = "info"        # #69C2FE
    success = "success"  # #5CC691
    warning = "warning"  # #F1C500
    danger = "danger"    # #E55957
    dark = "dark"        # #454545


class EstadoMunicipio(str, enum.Enum):
    activo = "activo"
    suspendido = "suspendido"


class TipoUsuario(str, enum.Enum):
    informes = "informes"
    padron = "padron"
    presupuestacion = "presupuestacion"
    control_presupuestal = "control_presupuestal"
    indicadores = "indicadores"
    alcalde = "alcalde"
    administrador = "administrador"


class ActorTipo(str, enum.Enum):
    usuario = "usuario"
    super_admin = "super_admin"


class TenantMixin:
    """Toda tabla de negocio de un municipio hereda esto. La capa común (tenancy.py)
    filtra y valida `municipio_id` automáticamente: ningún endpoint lo escribe a mano."""

    @declared_attr
    def municipio_id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(Uuid, ForeignKey("municipio.id"), nullable=False, index=True)


# --------------------------------------------------------------------------- plantillas globales
class PlantillaBase:
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    clave: Mapped[str] = mapped_column(String(32))
    nombre: Mapped[str] = mapped_column(Text)


class GeografiaEstado(PlantillaBase, Base):
    __tablename__ = "geografia_estado"
    __table_args__ = (UniqueConstraint("clave"),)


class GeografiaMunicipio(PlantillaBase, Base):
    __tablename__ = "geografia_municipio"
    __table_args__ = (UniqueConstraint("estado_id", "clave"),)
    estado_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("geografia_estado.id"), index=True)


class GeografiaLocalidad(PlantillaBase, Base):
    __tablename__ = "geografia_localidad"
    __table_args__ = (UniqueConstraint("municipio_geo_id", "clave"),)
    municipio_geo_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("geografia_municipio.id"), index=True)


class PlantillaConac(PlantillaBase, Base):
    """Jerarquía capítulo > partida > partida específica > artículo."""

    __tablename__ = "plantilla_conac"
    __table_args__ = (UniqueConstraint("nivel", "clave"),)
    nivel: Mapped[str] = mapped_column(String(24))  # capitulo|partida|partida_especifica|articulo
    padre_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("plantilla_conac.id"), index=True)


class PlantillaFrecuencia(PlantillaBase, Base):
    __tablename__ = "plantilla_frecuencia"
    __table_args__ = (UniqueConstraint("clave"),)


class PlantillaDimension(PlantillaBase, Base):
    __tablename__ = "plantilla_dimension"
    __table_args__ = (UniqueConstraint("clave"),)


class PlantillaAlgoritmo(PlantillaBase, Base):
    __tablename__ = "plantilla_algoritmo"
    __table_args__ = (UniqueConstraint("clave"),)


class PlantillaGrupoEdad(PlantillaBase, Base):
    __tablename__ = "plantilla_grupo_edad"
    __table_args__ = (UniqueConstraint("clave"),)
    edad_min: Mapped[int | None] = mapped_column(Integer)
    edad_max: Mapped[int | None] = mapped_column(Integer)


class PlantillaNivelSocioeconomico(PlantillaBase, Base):
    __tablename__ = "plantilla_nivel_socioeconomico"
    __table_args__ = (UniqueConstraint("clave"),)


class PlantillaClasificacionProgramatica(PlantillaBase, Base):
    __tablename__ = "plantilla_clasificacion_programatica"
    __table_args__ = (UniqueConstraint("clave"),)


# --------------------------------------------------------------------------- plataforma
class Municipio(Base):
    __tablename__ = "municipio"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(Text)
    subdominio: Mapped[str] = mapped_column(String(63), unique=True)
    estado_republica_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("geografia_estado.id"))
    logo_url: Mapped[str | None] = mapped_column(Text)
    imagen_login_url: Mapped[str | None] = mapped_column(Text)
    color_boton: Mapped[ColorBoton] = mapped_column(_enum(ColorBoton), default=ColorBoton.info)
    mostrar_logos: Mapped[bool] = mapped_column(Boolean, default=True)
    duracion_sesion_dias: Mapped[int] = mapped_column(Integer, default=30)
    estado: Mapped[EstadoMunicipio] = mapped_column(
        _enum(EstadoMunicipio), default=EstadoMunicipio.activo)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)

    estado_republica: Mapped[GeografiaEstado | None] = relationship()


class SubdominioReservado(Base):
    __tablename__ = "subdominio_reservado"
    subdominio: Mapped[str] = mapped_column(String(63), primary_key=True)


class SuperAdmin(Base):
    __tablename__ = "super_admin"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    usuario: Mapped[str] = mapped_column(String(100), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)  # argon2
    nombre: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)


class Usuario(TenantMixin, Base):
    __tablename__ = "usuario"
    __table_args__ = (UniqueConstraint("municipio_id", "usuario"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    usuario: Mapped[str] = mapped_column(String(100))
    password_encrypted: Mapped[str] = mapped_column(Text)  # AES-256-GCM reversible, NO hash
    tipo: Mapped[TipoUsuario] = mapped_column(_enum(TipoUsuario))
    nombre: Mapped[str] = mapped_column(Text)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    debe_cambiar_password: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)


class Sesion(Base):
    __tablename__ = "sesion"
    __table_args__ = (
        CheckConstraint(
            "(usuario_id IS NULL) <> (super_admin_id IS NULL)", name="ck_sesion_un_solo_actor"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuario.id"), index=True)
    super_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("super_admin.id"), index=True)
    municipio_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("municipio.id"))
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)


class Bitacora(Base):
    __tablename__ = "bitacora"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    municipio_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("municipio.id"), index=True)
    actor_tipo: Mapped[ActorTipo] = mapped_column(_enum(ActorTipo))
    actor_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    accion: Mapped[str] = mapped_column(Text)
    entidad: Mapped[str] = mapped_column(Text)
    entidad_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    detalle: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)


class CatalogoMunicipio(TenantMixin, Base):
    """Copia por municipio de las plantillas globales. Un solo almacén genérico en Fase 0;
    las fases siguientes pueden promover cada `tipo` a su tabla propia (frecuencia, partida…)."""

    __tablename__ = "catalogo_municipio"
    __table_args__ = (UniqueConstraint("municipio_id", "tipo", "clave", "padre_id"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # conac_capitulo|conac_partida|conac_partida_especifica|conac_articulo|geo_municipio|
    # geo_localidad|frecuencia|dimension|algoritmo|grupo_edad|nivel_socioeconomico|
    # clasificacion_programatica
    tipo: Mapped[str] = mapped_column(String(40), index=True)
    clave: Mapped[str] = mapped_column(String(32))
    nombre: Mapped[str] = mapped_column(Text)
    padre_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("catalogo_municipio.id"), index=True)
    datos: Mapped[dict] = mapped_column(JSONType, default=dict)
