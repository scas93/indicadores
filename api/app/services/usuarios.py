"""Lógica de usuarios de un municipio. La usan igual el administrador (ámbito municipio) y el
super admin (endpoints espejo): la `Session` ya viene aislada al municipio."""
import uuid

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import validators as v
from .. import validators_usuarios as vu
from ..deps import ActorCtx
from ..errors import ApiError
from ..models import Programa, Sesion, TipoUsuario, Usuario, UsuarioPrograma
from ..security import decrypt_password, encrypt_password
from .bitacora import registrar
from .municipios import generar_password

CAMPOS_EDITABLES = {"nombre", "usuario", "tipo", "activo", "direccion", "telefono", "email",
                    "anios_acceso", "meses_acceso"}


def a_dict(u: Usuario, ultimo_acceso=None, programa_ids: list | None = None) -> dict:
    d = {"id": u.id, "usuario": u.usuario, "nombre": u.nombre, "tipo": u.tipo.value,
         "activo": u.activo, "debe_cambiar_password": u.debe_cambiar_password,
         "direccion": u.direccion, "telefono": u.telefono, "email": u.email,
         "anios_acceso": list(u.anios_acceso or []), "meses_acceso": list(u.meses_acceso or []),
         "created_at": u.created_at, "ultimo_acceso": ultimo_acceso}
    if programa_ids is not None:
        d["programa_ids"] = programa_ids
    return d


def obtener(db: Session, id: uuid.UUID) -> Usuario:
    u = db.get(Usuario, id)  # filtrado por municipio: de otro municipio => None
    if u is None:
        raise ApiError(404, "USUARIO_NO_ENCONTRADO", "Usuario no encontrado")
    return u


def listar(db: Session, tipo: str | None, activo: bool | None, q: str | None) -> list[dict]:
    acceso = (select(Sesion.usuario_id, func.max(Sesion.created_at).label("ultimo"))
              .where(Sesion.usuario_id.is_not(None)).group_by(Sesion.usuario_id).subquery())
    stmt = select(Usuario, acceso.c.ultimo).join(acceso, acceso.c.usuario_id == Usuario.id, isouter=True)
    if tipo:
        stmt = stmt.where(Usuario.tipo == tipo)
    if activo is not None:
        stmt = stmt.where(Usuario.activo == activo)
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(func.lower(Usuario.nombre).like(like), func.lower(Usuario.usuario).like(like)))
    return [a_dict(u, ult) for u, ult in db.execute(stmt.order_by(Usuario.nombre)).all()]


def revocar_sesiones(db: Session, usuario_id: uuid.UUID, excepto: uuid.UUID | None = None) -> None:
    stmt = update(Sesion).where(Sesion.usuario_id == usuario_id, Sesion.revoked_at.is_(None))
    if excepto:
        stmt = stmt.where(Sesion.id != excepto)
    db.execute(stmt.values(revoked_at=v.utcnow()))


def _existentes(db: Session, excepto: uuid.UUID | None = None) -> set[str]:
    stmt = select(Usuario.usuario)
    if excepto:
        stmt = stmt.where(Usuario.id != excepto)
    return set(db.scalars(stmt).all())


def _normalizar(fila: dict) -> dict:
    f = dict(fila)
    for k in ("nombre", "usuario", "direccion", "telefono", "email"):
        if isinstance(f.get(k), str):
            f[k] = f[k].strip() or None if k not in ("nombre", "usuario") else f[k].strip()
    if isinstance(f.get("tipo"), str):
        f["tipo"] = f["tipo"].strip().lower()
    return f


def _nuevo(actor: ActorCtx, f: dict, password: str) -> Usuario:
    return Usuario(
        id=uuid.uuid4(), municipio_id=actor.municipio_id, usuario=f["usuario"],
        password_encrypted=encrypt_password(password), tipo=TipoUsuario(f["tipo"]), nombre=f["nombre"],
        activo=f.get("activo", True) is not False, debe_cambiar_password=True,  # solo informativo
        direccion=f.get("direccion"), telefono=f.get("telefono"), email=f.get("email"),
        anios_acceso=sorted(set(f.get("anios_acceso") or [])),
        meses_acceso=sorted(set(f.get("meses_acceso") or [])))


def crear(db: Session, actor: ActorCtx, datos: dict) -> tuple[Usuario, str | None]:
    """Devuelve (usuario, password_generada|None). No hace commit."""
    f = _normalizar(datos)
    vu.levantar_si_errores(vu.validar_fila_usuario(f, _existentes(db)))
    generada = not f.get("password")
    password = f.get("password") or generar_password()
    u = _nuevo(actor, f, password)
    db.add(u)
    try:
        db.flush()
    except IntegrityError:  # carrera con otro alta del mismo usuario
        db.rollback()
        raise ApiError(409, "USUARIO_EXISTE", "El usuario ya existe en el municipio",
                       {"usuario": "El usuario ya existe en el municipio"})
    if f.get("programa_ids"):
        reemplazar_programas(db, actor, u, f["programa_ids"], registrar_bitacora=False)
    registrar(db, actor_tipo=actor.actor_tipo, actor_id=actor.actor_id, accion="usuario.crear",
              entidad="usuario", entidad_id=u.id, municipio_id=actor.municipio_id,
              detalle={"usuario": u.usuario, "tipo": u.tipo.value})
    return u, (password if generada else None)


def crear_masivo(db: Session, actor: ActorCtx, filas: list[dict]) -> dict:
    """Fila por fila, mismas validaciones que el alta individual; una inválida no bloquea al resto."""
    if len(filas) > 500:
        raise ApiError(422, "LOTE_MUY_GRANDE", "Máximo 500 filas por lote")
    existentes, vistos = _existentes(db), set()
    creados, errores = [], []
    for i, fila in enumerate(filas):
        f = _normalizar(fila)
        errs = vu.validar_fila_usuario(f, existentes, vistos)
        if errs:
            errores.append({"fila": i, "campos": errs})
            continue
        generada = not f.get("password")
        password = f.get("password") or generar_password()
        u = _nuevo(actor, f, password)
        db.add(u)
        vistos.add(u.usuario)
        creados.append((i, u, password if generada else None))
    db.flush()
    registrar(db, actor_tipo=actor.actor_tipo, actor_id=actor.actor_id, accion="usuario.crear_masivo",
              entidad="usuario", municipio_id=actor.municipio_id,
              detalle={"creados": len(creados), "con_error": len(errores)})
    return {"creados": [{"fila": i, "id": u.id, "usuario": u.usuario, "password_generada": pw}
                        for i, u, pw in creados], "errores": errores}


def editar(db: Session, actor: ActorCtx, u: Usuario, cambios: dict) -> Usuario:
    cambios = {k: val for k, val in _normalizar(cambios).items()
               if k in CAMPOS_EDITABLES | {"password", "programa_ids"}}
    for k in ("nombre", "usuario", "tipo", "activo"):  # no admiten null
        if k in cambios and cambios[k] is None:
            del cambios[k]
    vu.validar_no_autobloqueo(actor.usuario_id, u.id, u.tipo.value, cambios)
    actual = {"nombre": u.nombre, "usuario": u.usuario, "tipo": u.tipo.value, "email": u.email,
              "anios_acceso": u.anios_acceso, "meses_acceso": u.meses_acceso}
    vu.levantar_si_errores(vu.validar_fila_usuario({**actual, **cambios}, _existentes(db, u.id)))
    estaba_activo = u.activo
    for k in CAMPOS_EDITABLES & cambios.keys():
        val = cambios[k]
        if k == "tipo":
            val = TipoUsuario(val)  # no toca programas: tipo y programas son independientes
        if k in ("anios_acceso", "meses_acceso"):
            val = sorted(set(val or []))
        setattr(u, k, val)
    if cambios.get("password"):
        u.password_encrypted = encrypt_password(cambios["password"])
        u.debe_cambiar_password = True
        revocar_sesiones(db, u.id)
    if estaba_activo and not u.activo:
        revocar_sesiones(db, u.id)  # caso 10: pierde el acceso de inmediato
    if "programa_ids" in cambios and cambios["programa_ids"] is not None:
        reemplazar_programas(db, actor, u, cambios["programa_ids"])
    registrar(db, actor_tipo=actor.actor_tipo, actor_id=actor.actor_id,
              accion="usuario.deshabilitar" if estaba_activo and not u.activo else "usuario.editar",
              entidad="usuario", entidad_id=u.id, municipio_id=actor.municipio_id,
              detalle={"campos": sorted(k for k in cambios if k not in ("password",))})
    return u


def ver_password(db: Session, actor: ActorCtx, u: Usuario) -> str:
    registrar(db, actor_tipo=actor.actor_tipo, actor_id=actor.actor_id, accion="usuario.ver_password",
              entidad="usuario", entidad_id=u.id, municipio_id=actor.municipio_id,
              detalle={"usuario": u.usuario})
    return decrypt_password(u.password_encrypted)


def forzar_password(db: Session, actor: ActorCtx, u: Usuario) -> str:
    nueva = generar_password()
    u.password_encrypted = encrypt_password(nueva)
    u.debe_cambiar_password = True  # informativo; no obliga a nada en el login
    revocar_sesiones(db, u.id)
    registrar(db, actor_tipo=actor.actor_tipo, actor_id=actor.actor_id, accion="usuario.forzar_password",
              entidad="usuario", entidad_id=u.id, municipio_id=actor.municipio_id,
              detalle={"usuario": u.usuario})
    return nueva


def programas_de(db: Session, usuario_id: uuid.UUID) -> list[uuid.UUID]:
    return list(db.scalars(select(UsuarioPrograma.programa_id).where(
        UsuarioPrograma.usuario_id == usuario_id)).all())


def aplicar_cambios_asignacion(db: Session, actor: ActorCtx, altas: list, bajas: list) -> tuple[int, int]:
    """Núcleo compartido por la matriz y el selector del modal: valida que usuarios y programas
    sean del municipio, depura contra lo existente y aplica todo en la transacción en curso."""
    pares = set(altas) | set(bajas)
    vu.validar_ids_del_municipio({u for u, _ in pares}, db.scalars(select(Usuario.id).where(
        Usuario.id.in_({u for u, _ in pares}))).all(), "usuario")
    vu.validar_ids_del_municipio({p for _, p in pares}, db.scalars(select(Programa.id).where(
        Programa.id.in_({p for _, p in pares}))).all(), "programa")
    actuales = {(r.usuario_id, r.programa_id) for r in db.scalars(select(UsuarioPrograma).where(
        UsuarioPrograma.usuario_id.in_({u for u, _ in pares}),
        UsuarioPrograma.programa_id.in_({p for _, p in pares})))}
    insertar, borrar = vu.calcular_cambios_matriz(actuales, altas, bajas)
    for uid, pid in insertar:
        db.add(UsuarioPrograma(usuario_id=uid, programa_id=pid, municipio_id=actor.municipio_id))
    for uid, pid in borrar:
        db.delete(db.get(UsuarioPrograma, (uid, pid)))
    return len(insertar), len(borrar)


def reemplazar_programas(db: Session, actor: ActorCtx, u: Usuario, programa_ids: list,
                         registrar_bitacora: bool = True) -> tuple[int, int]:
    deseados = set(programa_ids)
    actuales = set(programas_de(db, u.id))
    a, b = aplicar_cambios_asignacion(
        db, actor, [(u.id, p) for p in deseados - actuales], [(u.id, p) for p in actuales - deseados])
    if registrar_bitacora and (a or b):
        registrar(db, actor_tipo=actor.actor_tipo, actor_id=actor.actor_id, accion="matriz.guardar",
                  entidad="usuario_programa", entidad_id=u.id, municipio_id=actor.municipio_id,
                  detalle={"resumen": vu.resumen_matriz(a, b), "altas": a, "bajas": b, "usuario": u.usuario})
    return a, b
