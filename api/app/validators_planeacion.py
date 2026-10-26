"""Reglas de negocio de los catálogos de planeación y programas (funciones puras)."""
import uuid
from dataclasses import dataclass

from .errors import ApiError


def validar_clave_nombre(clave: str | None, nombre: str | None) -> tuple[str, str]:
    errores = {}
    clave, nombre = (clave or "").strip(), (nombre or "").strip()
    if not clave:
        errores["clave"] = "La clave es obligatoria"
    elif len(clave) > 32:
        errores["clave"] = "Máximo 32 caracteres"
    if not nombre:
        errores["nombre"] = "El nombre es obligatorio"
    if errores:
        raise ApiError(422, "VALIDACION", "Datos inválidos", errores)
    return clave, nombre


def validar_ejercicio(valor: int) -> int:
    if not isinstance(valor, int) or isinstance(valor, bool) or valor < 2000 or valor > 2100:
        raise ApiError(422, "EJERCICIO_INVALIDO", "Ejercicio fiscal inválido (2000-2100)",
                       {"ejercicio_fiscal": "Fuera de rango"})
    return valor


@dataclass(frozen=True)
class Ref:
    """Lo mínimo que la jerarquía necesita saber de un registro ya cargado."""
    id: uuid.UUID
    activo: bool
    padre_id: uuid.UUID | None = None      # subtema->eje; estrategia->subtema (eje y centro gestor no tienen padre)


def validar_referencias_programa(centro: Ref | None, subtema: Ref | None, estrategia: Ref | None,
                                 subtema_pedido: bool = False, estrategia_pedida: bool = False,
                                 eje: Ref | None = None, eje_pedido: bool = False) -> None:
    """Dos ramas independientes: (1) eje → subtema → estrategia, y (2) centro gestor. El centro gestor
    solo debe existir y estar activo; el eje (si se indica), el subtema y la estrategia deben existir,
    estar activos y colgar del anterior (subtema del eje, estrategia del subtema). Lo deshabilitado
    sale de los selectores."""
    err = {}
    if centro is None:
        err["centro_gestor_id"] = "Centro gestor inválido"
    elif not centro.activo:
        err["centro_gestor_id"] = "Centro gestor deshabilitado"
    if eje_pedido:
        if eje is None:
            err["eje_id"] = "Eje inválido"
        elif not eje.activo:
            err["eje_id"] = "Eje deshabilitado"
    if subtema_pedido:
        if subtema is None:
            err["subtema_id"] = "Subtema inválido"
        elif not subtema.activo:
            err["subtema_id"] = "Subtema deshabilitado"
        elif eje_pedido and eje is not None and subtema.padre_id != eje.id:
            err["subtema_id"] = "El subtema no pertenece al eje"
    if estrategia_pedida:
        if estrategia is None:
            err["estrategia_id"] = "Estrategia inválida"
        elif not estrategia.activo:
            err["estrategia_id"] = "Estrategia deshabilitada"
        elif subtema is None or estrategia.padre_id != subtema.id:
            err["estrategia_id"] = "La estrategia no pertenece al subtema"
    if err:
        raise ApiError(422, "JERARQUIA_INVALIDA", "Referencias de planeación inválidas", err)


def validar_duplicado_programa(origen_ejercicio: int, origen_clave: str, destino_ejercicio: int,
                               clave_nueva: str, claves_en_destino: set[str]) -> None:
    """Duplicar exige clave nueva (distinta a la del origen) y libre en el ejercicio destino."""
    validar_ejercicio(destino_ejercicio)
    clave_nueva = (clave_nueva or "").strip()
    if not clave_nueva:
        raise ApiError(422, "VALIDACION", "La clave nueva es obligatoria", {"clave": "Obligatoria"})
    if clave_nueva == origen_clave:
        raise ApiError(422, "CLAVE_REPETIDA", "Captura una clave nueva (no la del programa origen)",
                       {"clave": "Debe ser distinta a la del origen"})
    if clave_nueva in claves_en_destino:
        raise ApiError(409, "CLAVE_DUPLICADA", "La clave ya existe en el ejercicio destino",
                       {"clave": "Ya existe en ese ejercicio"})
