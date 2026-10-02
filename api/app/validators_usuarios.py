"""Reglas de negocio de usuarios, permisos por tipo, matriz y configuración (funciones puras)."""
import re
import uuid
from typing import Iterable, Mapping

from .errors import ApiError
from .models import TipoUsuario

TIPOS = frozenset(t.value for t in TipoUsuario)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

ADMIN = "administrador"
# Qué tipos pueden llamar cada grupo de endpoints. El menú del front solo oculta: esto es lo que
# realmente niega (403) el acceso directo por URL.
PERMISOS: dict[str, frozenset[str]] = {
    # Usuarios: el listado lo ven los 5 tipos que tienen el item en el menú; todo lo demás
    # (alta, edición, contraseña, forzar, masivo, matriz) es solo del administrador.
    "usuarios_ver": frozenset({"informes", "padron", "presupuestacion", "indicadores", "alcalde", ADMIN}),
    "usuarios_gestion": frozenset({ADMIN}),
    # Planeación
    "planeacion_ver": frozenset({"informes", "presupuestacion", "control_presupuestal",
                                 "indicadores", "alcalde", ADMIN}),
    "planeacion_editar": frozenset({"alcalde", ADMIN}),
    "programas_editar": frozenset({"alcalde", "presupuestacion", ADMIN}),
    # Configuración
    "config_ver": frozenset({"informes", "alcalde", ADMIN}),
}
# Quién edita cada campo de configuración (meses/tolerancia: solo administrador y alcalde)
CONFIG_CAMPOS_EDITABLES: dict[str, frozenset[str]] = {
    "imagen_login_url": frozenset({"informes", ADMIN}),
    "color_boton": frozenset({"informes", ADMIN}),
    "mostrar_logos": frozenset({"informes", ADMIN}),
    "meses_avance_activos": frozenset({"alcalde", ADMIN}),
    "tolerancia_semaforo": frozenset({"alcalde", ADMIN}),
}
# Tipos que, además de por tipo, ven solo los programas de su matriz (administrador y alcalde ven todos)
TIPOS_SIN_FILTRO_PROGRAMAS = frozenset({"administrador", "alcalde"})


def tipo_permitido(grupo: str, tipo: str | None) -> bool:
    return tipo in PERMISOS[grupo]


def validar_tipo_permitido(grupo: str, tipo: str | None) -> None:
    if not tipo_permitido(grupo, tipo):
        raise ApiError(403, "TIPO_NO_PERMITIDO", "Tu tipo de usuario no puede usar este módulo")


def validar_campos_config(tipo: str | None, campos: Iterable[str]) -> None:
    for c in campos:
        if tipo not in CONFIG_CAMPOS_EDITABLES.get(c, frozenset()):
            raise ApiError(403, "TIPO_NO_PERMITIDO", f"Tu tipo de usuario no puede editar {c}",
                           {c: "No permitido"})


def programas_visibles(tipo: str | None, asignados: Iterable[uuid.UUID]) -> frozenset[uuid.UUID] | None:
    """None = sin restricción; si no, el conjunto de programas que el usuario puede ver/usar.
    Dos usuarios del mismo tipo pueden tener conjuntos distintos."""
    if tipo in TIPOS_SIN_FILTRO_PROGRAMAS:
        return None
    return frozenset(asignados)


# --- datos del usuario -------------------------------------------------------
def email_valido(email: str | None) -> bool:
    return email is None or email.strip() == "" or bool(EMAIL_RE.match(email.strip()))


def validar_anios_meses(anios: Iterable[int] | None, meses: Iterable[int] | None) -> dict[str, str]:
    errores: dict[str, str] = {}
    if anios is not None and any(not isinstance(a, int) or a < 2000 or a > 2100 for a in anios):
        errores["anios_acceso"] = "Años fuera de rango (2000-2100)"
    if meses is not None and any(not isinstance(m, int) or m < 1 or m > 12 for m in meses):
        errores["meses_acceso"] = "Los meses deben ser de 1 a 12"
    return errores


def validar_fila_usuario(fila: Mapping, existentes: Iterable[str], vistos: Iterable[str] = ()) -> dict[str, str]:
    """Validaciones del alta (individual y masiva, mismas reglas). Devuelve {campo: mensaje};
    vacío = fila válida. `existentes`: usuarios ya dados de alta en el municipio; `vistos`: los
    de filas anteriores del mismo lote. Sin reglas de complejidad de contraseña (decisión del cliente)."""
    errores: dict[str, str] = {}
    usuario = (fila.get("usuario") or "").strip()
    if not (fila.get("nombre") or "").strip():
        errores["nombre"] = "El nombre es obligatorio"
    if not usuario:
        errores["usuario"] = "El usuario es obligatorio"
    elif len(usuario) > 100:
        errores["usuario"] = "Máximo 100 caracteres"
    elif usuario in set(existentes) or usuario in set(vistos):
        errores["usuario"] = "El usuario ya existe en el municipio"
    if not email_valido(fila.get("email")):
        errores["email"] = "Email con formato inválido"
    if fila.get("tipo") not in TIPOS:
        errores["tipo"] = "Tipo de usuario inválido"
    errores.update(validar_anios_meses(fila.get("anios_acceso"), fila.get("meses_acceso")))
    return errores


def levantar_si_errores(errores: dict[str, str]) -> None:
    if errores:
        dup = errores.get("usuario") == "El usuario ya existe en el municipio"
        raise ApiError(409 if dup else 422, "USUARIO_EXISTE" if dup else "VALIDACION",
                       errores.get("usuario") if dup else "Datos inválidos", errores)


def validar_no_autobloqueo(actor_id: uuid.UUID | None, objetivo_id: uuid.UUID,
                           tipo_actual: str, cambios: Mapping) -> None:
    """Un administrador no puede deshabilitarse ni quitarse el tipo a sí mismo (quedaría sin acceso)."""
    if actor_id != objetivo_id:
        return
    if cambios.get("activo") is False or ("tipo" in cambios and cambios["tipo"] != tipo_actual):
        raise ApiError(409, "AUTOBLOQUEO", "No puedes deshabilitarte ni cambiar tu propio tipo")


# --- matriz usuarios × programas --------------------------------------------
Par = tuple[uuid.UUID, uuid.UUID]  # (usuario_id, programa_id)


def calcular_cambios_matriz(actuales: Iterable[Par], altas: Iterable[Par], bajas: Iterable[Par]
                            ) -> tuple[set[Par], set[Par]]:
    """Devuelve (a_insertar, a_borrar) ya depurados contra lo que existe: un alta de algo que ya
    está asignado, o una baja de algo que no lo está, no cuenta. Un mismo par en altas y bajas es
    un error (el resumen mostrado no coincidiría con lo guardado)."""
    actuales, altas, bajas = set(actuales), set(altas), set(bajas)
    if altas & bajas:
        raise ApiError(422, "MATRIZ_CONFLICTO", "Una celda aparece como alta y baja a la vez")
    return altas - actuales, bajas & actuales


def resumen_matriz(altas: int, bajas: int) -> str:
    def plural(n: int, uno: str, varios: str) -> str:
        return f"{n} {uno if n == 1 else varios}"
    return f"{plural(altas, 'asignación nueva', 'asignaciones nuevas')}, {plural(bajas, 'retirada', 'retiradas')}"


def validar_ids_del_municipio(solicitados: Iterable[uuid.UUID], encontrados: Iterable[uuid.UUID],
                              entidad: str) -> None:
    """Regla de aislamiento en el servidor: lo que no se encontró dentro del municipio (la Session
    ya filtra por `municipio_id`) es de otro municipio o no existe."""
    faltan = set(solicitados) - set(encontrados)
    if faltan:
        raise ApiError(422, f"{entidad.upper()}_INVALIDO",
                       f"{entidad} inexistente o de otro municipio", {entidad: f"{len(faltan)} inválido(s)"})


# --- configuración -----------------------------------------------------------
def validar_meses_avance(meses: Iterable[int]) -> list[int]:
    meses = list(meses)
    if any(not isinstance(m, int) or isinstance(m, bool) or m < 1 or m > 12 for m in meses):
        raise ApiError(422, "MESES_INVALIDOS", "Los meses deben ser de 1 a 12",
                       {"meses_avance_activos": "Meses de 1 a 12"})
    return sorted(set(meses))


def validar_tolerancia(dias: int) -> int:
    if not isinstance(dias, int) or isinstance(dias, bool) or dias < 0 or dias > 365:
        raise ApiError(422, "TOLERANCIA_INVALIDA", "La tolerancia debe ser de 0 a 365 días",
                       {"tolerancia_semaforo": "De 0 a 365"})
    return dias
