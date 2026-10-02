import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (JSON, Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Index,
                        Integer, Numeric, String, Text, TypeDecorator, UniqueConstraint, Uuid, text)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
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
# int[] en Postgres; JSON en SQLite (pruebas)
IntArray = JSON().with_variant(ARRAY(Integer), "postgresql")


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
    # Fase 1: configuración del municipio (columnas, sin tabla aparte)
    meses_avance_activos: Mapped[list[int]] = mapped_column(IntArray, default=list)
    tolerancia_semaforo: Mapped[int] = mapped_column(Integer, default=0)  # días
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
    # Solo informativo: el login nunca obliga a cambiar la contraseña (decisión de producto)
    debe_cambiar_password: Mapped[bool] = mapped_column(Boolean, default=True)
    direccion: Mapped[str | None] = mapped_column(Text)
    telefono: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    anios_acceso: Mapped[list[int]] = mapped_column(IntArray, default=list)
    meses_acceso: Mapped[list[int]] = mapped_column(IntArray, default=list)
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


# --------------------------------------------------------------------------- Fase 1: planeación
class _Catalogo(TenantMixin):
    """Catálogo por municipio con baja lógica: se deshabilita, nunca se borra."""

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    clave: Mapped[str] = mapped_column(String(32))
    nombre: Mapped[str] = mapped_column(Text)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class CentroGestor(_Catalogo, Base):
    __tablename__ = "centro_gestor"
    __table_args__ = (UniqueConstraint("municipio_id", "clave"),)


class Eje(_Catalogo, Base):
    __tablename__ = "eje"
    __table_args__ = (UniqueConstraint("municipio_id", "centro_gestor_id", "clave"),)
    centro_gestor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("centro_gestor.id"), index=True)


class Subtema(_Catalogo, Base):
    __tablename__ = "subtema"
    __table_args__ = (UniqueConstraint("municipio_id", "eje_id", "clave"),)
    eje_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("eje.id"), index=True)


class Estrategia(_Catalogo, Base):
    __tablename__ = "estrategia"
    __table_args__ = (UniqueConstraint("municipio_id", "subtema_id", "clave"),)
    subtema_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subtema.id"), index=True)


class Frecuencia(_Catalogo, Base):
    """Copiada de plantilla_frecuencia al crear el municipio; editable por Admin y Alcalde."""

    __tablename__ = "frecuencia"
    __table_args__ = (UniqueConstraint("municipio_id", "clave"),)


class ClasificacionProgramatica(_Catalogo, Base):
    """Copiada de plantilla_clasificacion_programatica; solo lectura en Fase 1."""

    __tablename__ = "clasificacion_programatica"
    __table_args__ = (UniqueConstraint("municipio_id", "clave"),)


class Programa(TenantMixin, Base):
    __tablename__ = "programa"
    __table_args__ = (UniqueConstraint("municipio_id", "ejercicio_fiscal", "clave"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    ejercicio_fiscal: Mapped[int] = mapped_column(Integer, index=True)
    clave: Mapped[str] = mapped_column(String(32))
    nombre: Mapped[str] = mapped_column(Text)
    centro_gestor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("centro_gestor.id"), index=True)
    subtema_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("subtema.id"))
    estrategia_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("estrategia.id"))
    clasificacion_programatica_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clasificacion_programatica.id"))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)


class UsuarioPrograma(TenantMixin, Base):
    """Binario: existe o no existe la fila (sin lectura/escritura por separado)."""

    __tablename__ = "usuario_programa"
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"), primary_key=True)
    programa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("programa.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)


class PasswordResetToken(TenantMixin, Base):
    __tablename__ = "password_reset_token"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)  # sha256 hex; el token no se guarda
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)


# --------------------------------------------------------------------------- Fase 2: MIR
class NivelMatriz(str, enum.Enum):
    fin = "fin"
    proposito = "proposito"
    componente = "componente"
    actividad = "actividad"


class TipoIndicador(str, enum.Enum):
    gestion = "gestion"
    estrategico = "estrategico"


class DimensionIndicador(str, enum.Enum):
    eficacia = "eficacia"
    eficiencia = "eficiencia"
    calidad = "calidad"
    economia = "economia"


class Algoritmo(str, enum.Enum):
    a_sobre_b_pct = "a_sobre_b_pct"
    a_sobre_b_menos1_pct = "a_sobre_b_menos1_pct"
    a_sobre_b = "a_sobre_b"
    a = "a"


_VALOR = Numeric(18, 4)


class ArbolEncabezado(TenantMixin, Base):
    """Situación no deseada (problema) y objetivo (positivo) que encabezan el árbol."""

    __tablename__ = "arbol_encabezado"
    programa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("programa.id"), primary_key=True)
    problema: Mapped[str | None] = mapped_column(Text)
    objetivo: Mapped[str | None] = mapped_column(Text)


class _ArbolNodo(TenantMixin):
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    numero: Mapped[str] = mapped_column(Text)  # "1", "1.1": se recalcula al insertar y al borrar
    orden: Mapped[int] = mapped_column(Integer)


class ArbolCausaMedio(_ArbolNodo, Base):
    """Par causa/medio espejo (comparten número). 2 niveles."""

    __tablename__ = "arbol_causa_medio"
    programa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("programa.id"), index=True)
    padre_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("arbol_causa_medio.id"), index=True)
    texto_causa: Mapped[str] = mapped_column(Text, default="")
    texto_medio: Mapped[str] = mapped_column(Text, default="")


class ArbolEfectoFin(_ArbolNodo, Base):
    __tablename__ = "arbol_efecto_fin"
    programa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("programa.id"), index=True)
    padre_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("arbol_efecto_fin.id"), index=True)
    texto_efecto: Mapped[str] = mapped_column(Text, default="")
    texto_fin: Mapped[str] = mapped_column(Text, default="")


class ElementoMatriz(TenantMixin, Base):
    """Filas de la MIR. A lo más un fin y un propósito por programa (índice único parcial)."""

    __tablename__ = "elemento_matriz"
    __table_args__ = (
        Index("uq_elemento_matriz_fin_proposito", "programa_id", "nivel", unique=True,
              postgresql_where=text("nivel IN ('fin', 'proposito')"),
              sqlite_where=text("nivel IN ('fin', 'proposito')")),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    programa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("programa.id"), index=True)
    nivel: Mapped[NivelMatriz] = mapped_column(_enum(NivelMatriz))
    numero: Mapped[str] = mapped_column(Text, default="")  # vacío en fin/propósito
    orden: Mapped[int] = mapped_column(Integer, default=0)
    padre_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("elemento_matriz.id"), index=True)
    resumen_narrativo: Mapped[str] = mapped_column(Text, default="")
    medios_verificacion: Mapped[str] = mapped_column(Text, default="")
    supuestos: Mapped[str] = mapped_column(Text, default="")
    evidencia: Mapped[str | None] = mapped_column(Text)


class Indicador(TenantMixin, Base):
    __tablename__ = "indicador"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    elemento_matriz_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("elemento_matriz.id"), index=True)
    tipo: Mapped[TipoIndicador] = mapped_column(_enum(TipoIndicador))
    prioritario: Mapped[bool] = mapped_column(Boolean, default=False)
    nombre: Mapped[str] = mapped_column(Text, default="")
    interpretacion: Mapped[str] = mapped_column(Text, default="")
    dimension: Mapped[DimensionIndicador | None] = mapped_column(_enum(DimensionIndicador))
    frecuencia_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("frecuencia.id"))
    unidad_medida: Mapped[str] = mapped_column(Text, default="")
    algoritmo: Mapped[Algoritmo | None] = mapped_column(_enum(Algoritmo))
    unidad_a: Mapped[str] = mapped_column(Text, default="")
    unidad_b: Mapped[str | None] = mapped_column(Text)
    rango_verde_desde: Mapped[Decimal | None] = mapped_column(_VALOR)
    rango_verde_hasta: Mapped[Decimal | None] = mapped_column(_VALOR)
    rango_amarillo_desde: Mapped[Decimal | None] = mapped_column(_VALOR)
    rango_amarillo_hasta: Mapped[Decimal | None] = mapped_column(_VALOR)
    rango_rojo_desde: Mapped[Decimal | None] = mapped_column(_VALOR)
    rango_rojo_hasta: Mapped[Decimal | None] = mapped_column(_VALOR)
    anio_base: Mapped[int | None] = mapped_column(Integer)
    meta_administracion: Mapped[Decimal | None] = mapped_column(_VALOR)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)


class MetaAnual(TenantMixin, Base):
    __tablename__ = "meta_anual"
    __table_args__ = (UniqueConstraint("indicador_id", "anio"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    indicador_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("indicador.id"), index=True)
    anio: Mapped[int] = mapped_column(Integer)
    valor_a_programado: Mapped[Decimal | None] = mapped_column(_VALOR)
    valor_b_programado: Mapped[Decimal | None] = mapped_column(_VALOR)
    es_ejercicio_fiscal: Mapped[bool] = mapped_column(Boolean, default=False)


class AvanceMensual(TenantMixin, Base):
    """Sumatoria y cumplimiento NO se guardan: se calculan al leer (app/calculo.py)."""

    __tablename__ = "avance_mensual"
    __table_args__ = (UniqueConstraint("indicador_id", "anio", "mes"),
                      CheckConstraint("mes BETWEEN 1 AND 12", name="ck_avance_mes"))
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    indicador_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("indicador.id"), index=True)
    anio: Mapped[int] = mapped_column(Integer)
    mes: Mapped[int] = mapped_column(Integer)
    valor_a: Mapped[Decimal | None] = mapped_column(_VALOR)
    valor_b: Mapped[Decimal | None] = mapped_column(_VALOR)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now, onupdate=_now)
