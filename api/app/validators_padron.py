"""Reglas de negocio de los catálogos del Padrón (Fase 5, parte 1). Funciones puras: sin base de datos."""
import re
import unicodedata
import uuid
from datetime import date, timedelta, timezone
from typing import Iterable, Mapping, Sequence

from .errors import ApiError

EDAD_MAX_PERMITIDA = 150
Rango = tuple[uuid.UUID | None, int, int | None]  # (id, edad mínima, edad máxima; None = sin tope)


def clave_desde_nombre(nombre: str) -> str:
    """Clave automática de los catálogos que no la capturan (niveles socioeconómicos): 'Muy bajo' -> 'muy_bajo'."""
    ascii_ = unicodedata.normalize("NFD", nombre or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", ascii_.lower()).strip("_")[:32]


def clave_de_rango(edad_min: int, edad_max: int | None) -> str:
    """Misma convención que la plantilla: '0-11', '60+'."""
    return f"{edad_min}+" if edad_max is None else f"{edad_min}-{edad_max}"


def validar_nombre(nombre: str | None, campo: str = "nombre") -> str:
    nombre = (nombre or "").strip()
    if not nombre:
        raise ApiError(422, "VALIDACION", "Datos inválidos", {campo: "Obligatorio"})
    return nombre


def clave_repetida(clave: str, existentes: Iterable[str]) -> bool:
    """Las claves se comparan sin importar mayúsculas ni espacios en los extremos."""
    return clave.strip().lower() in {c.strip().lower() for c in existentes}


def levantar_si_clave_repetida(clave: str, existentes: Iterable[str], campo: str = "clave") -> None:
    if clave_repetida(clave, existentes):
        raise ApiError(409, "CLAVE_DUPLICADA", "Ya existe un registro con esa clave", {campo: "Ya existe"})


# --- grupos de edad -----------------------------------------------------------------------------
def _entero(valor, campo: str, errores: dict[str, str]) -> int | None:
    if valor is None or valor == "":
        return None
    if isinstance(valor, bool) or not isinstance(valor, int):
        errores[campo] = "Debe ser un número entero"
        return None
    return valor


def validar_rango_edad(edad_min, edad_max) -> tuple[int, int | None]:
    """Mínimo obligatorio (>= 0); máximo opcional (sin máximo = abierto hacia arriba) y nunca menor al mínimo."""
    errores: dict[str, str] = {}
    mn, mx = _entero(edad_min, "edad_min", errores), _entero(edad_max, "edad_max", errores)
    if "edad_min" not in errores and mn is None:
        errores["edad_min"] = "La edad mínima es obligatoria"
    if mn is not None and (mn < 0 or mn > EDAD_MAX_PERMITIDA):
        errores["edad_min"] = f"Debe estar entre 0 y {EDAD_MAX_PERMITIDA}"
    if mx is not None and mx > EDAD_MAX_PERMITIDA:
        errores["edad_max"] = f"Debe ser como máximo {EDAD_MAX_PERMITIDA}"
    elif mn is not None and mx is not None and "edad_min" not in errores and mx < mn:
        errores["edad_max"] = "El máximo no puede ser menor al mínimo (rango invertido)"
    if errores:
        raise ApiError(422, "RANGO_INVALIDO", "Rango de edad inválido", errores)
    return mn, mx


def _tope(mx: int | None) -> float:
    return float("inf") if mx is None else mx


def rangos_traslapan(a: tuple[int, int | None], b: tuple[int, int | None]) -> bool:
    """Los extremos cuentan: 0-11 y 11-17 se traslapan (la edad 11 caería en dos grupos)."""
    return a[0] <= _tope(b[1]) and b[0] <= _tope(a[1])


def validar_sin_traslape(nuevo: tuple[int, int | None], existentes: Iterable[Rango],
                         excepto: uuid.UUID | None = None) -> None:
    for id_, mn, mx in existentes:
        if id_ is not None and id_ == excepto:
            continue
        if rangos_traslapan(nuevo, (mn, mx)):
            raise ApiError(409, "RANGO_TRASLAPADO", f"El rango se traslapa con el grupo {clave_de_rango(mn, mx)}",
                           {"edad_min": "Se traslapa con otro grupo de edad"})


# --- pertenencia entre catálogos ----------------------------------------------------------------
def validar_programa_asignado(programa_existe: bool, programa_activo: bool,
                              visibles: frozenset[uuid.UUID] | None, programa_id: uuid.UUID | None) -> None:
    """Un Apoyo solo se asocia a un programa existente, activo y asignado al usuario (`visibles` None = todos)."""
    if programa_id is None or not programa_existe:
        raise ApiError(422, "JERARQUIA_INVALIDA", "Programa inexistente o de otro municipio",
                       {"programa_id": "Programa inválido"})
    if visibles is not None and programa_id not in visibles:
        raise ApiError(422, "PROGRAMA_NO_ASIGNADO", "El programa no está asignado a tu usuario",
                       {"programa_id": "Programa no asignado"})
    if not programa_activo:
        raise ApiError(422, "JERARQUIA_INVALIDA", "El programa está deshabilitado", {"programa_id": "Deshabilitado"})


def validar_apoyo_existente(apoyo_existe: bool, apoyo_visible: bool, apoyo_id: uuid.UUID | None) -> None:
    """Una Descripción de apoyo solo cuelga de un Apoyo que existe en el municipio y que el usuario puede ver."""
    if apoyo_id is None or not apoyo_existe or not apoyo_visible:
        raise ApiError(422, "JERARQUIA_INVALIDA", "Apoyo inexistente o no disponible", {"apoyo_id": "Apoyo inválido"})


def validar_municipio_de_estado(estado_del_municipio: uuid.UUID | None, estado_id: uuid.UUID | None,
                                municipio_existe: bool) -> None:
    """Colonia: el municipio debe existir y pertenecer al estado elegido."""
    if not municipio_existe:
        raise ApiError(422, "JERARQUIA_INVALIDA", "Municipio inexistente", {"municipio_id": "Municipio inválido"})
    if estado_id is None or estado_del_municipio != estado_id:
        raise ApiError(422, "JERARQUIA_INVALIDA", "El municipio no pertenece al estado",
                       {"municipio_id": "No pertenece al estado elegido"})


# --- borrado ------------------------------------------------------------------------------------
def validar_borrable(usos: Mapping[str, int]) -> None:
    """Un registro solo se borra si nada lo usa. `usos`: {qué lo usa: cuántos}. Cuando existan las
    entregas (Fase 5, parte 2), basta con registrar su conteo en el servicio."""
    en_uso = {k: n for k, n in usos.items() if n > 0}
    if en_uso:
        detalle = ", ".join(f"{n} {k}" for k, n in en_uso.items())
        raise ApiError(409, "REGISTRO_EN_USO", f"No se puede eliminar: lo usa {detalle}", {"usos": detalle})


def ids_unicos(ids: Sequence[uuid.UUID]) -> list[uuid.UUID]:
    """Para el borrado en lote: sin repetidos y respetando el orden."""
    return list(dict.fromkeys(ids))


# --- beneficiarios y captura (Fase 4.2) -----------------------------------------------------------
GENEROS = {"F": "Femenino", "M": "Masculino"}
_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ZONA_MEXICO = timezone(timedelta(hours=-6))  # sin horario de verano desde 2022


def normalizar_curp(curp: str | None) -> str:
    """Recortada y en mayúsculas. NO se valida el formato: la referencia acepta CURPs irregulares;
    solo importa que no esté vacía y que no se repita."""
    curp = (curp or "").strip().upper()
    if not curp:
        raise ApiError(422, "VALIDACION", "Datos inválidos", {"curp": "La CURP es obligatoria"})
    if len(curp) > 32:
        raise ApiError(422, "VALIDACION", "Datos inválidos", {"curp": "Máximo 32 caracteres"})
    return curp


def levantar_si_curp_repetida(curp: str, existentes: Iterable[str]) -> None:
    if curp in {c.strip().upper() for c in existentes}:
        raise ApiError(409, "CURP_DUPLICADA", "Ya existe un beneficiario con esa CURP", {"curp": "Ya existe"})


def validar_fecha_nacimiento(nacimiento: date | None, hoy: date) -> date | None:
    if nacimiento is None:
        return None
    if nacimiento > hoy:
        raise ApiError(422, "VALIDACION", "Datos inválidos", {"fecha_nacimiento": "No puede ser futura"})
    if calcular_edad(nacimiento, hoy) > EDAD_MAX_PERMITIDA:
        raise ApiError(422, "VALIDACION", "Datos inválidos", {"fecha_nacimiento": "Fecha inválida"})
    return nacimiento


def validar_genero(genero: str | None) -> str | None:
    genero = (genero or "").strip().upper() or None
    if genero is not None and genero not in GENEROS:
        raise ApiError(422, "VALIDACION", "Datos inválidos", {"genero": "Femenino o Masculino"})
    return genero


def validar_correo(correo: str | None) -> str | None:
    correo = (correo or "").strip() or None
    if correo is not None and not _CORREO.match(correo):
        raise ApiError(422, "VALIDACION", "Datos inválidos", {"correo": "Correo inválido"})
    return correo


def validar_cascada_geografica(estado_id, estado_del_municipio, municipio_id, municipio_del_localidad, localidad_id) -> None:
    """Estado -> Municipio -> Localidad: cada nivel solo se acepta si el de arriba está y es su padre."""
    if municipio_id is not None and (estado_id is None or estado_del_municipio != estado_id):
        raise ApiError(422, "JERARQUIA_INVALIDA", "El municipio no pertenece al estado",
                       {"municipio_id": "No pertenece al estado elegido"})
    if localidad_id is not None and (municipio_id is None or municipio_del_localidad != municipio_id):
        raise ApiError(422, "JERARQUIA_INVALIDA", "La localidad no pertenece al municipio",
                       {"localidad_id": "No pertenece al municipio elegido"})


def calcular_edad(nacimiento: date, a_la_fecha: date) -> int:
    """Años cumplidos a esa fecha."""
    return a_la_fecha.year - nacimiento.year - ((a_la_fecha.month, a_la_fecha.day) < (nacimiento.month, nacimiento.day))


def grupo_de_edad(edad: int | None, grupos: Iterable[Rango]) -> uuid.UUID | None:
    """El grupo de edad (id, mín, máx) que contiene la edad; None si ninguno la cubre (p. ej. 1 año o 85)."""
    if edad is None:
        return None
    for id_, mn, mx in grupos:
        if mn <= edad <= _tope(mx):
            return id_
    return None


def validar_cantidad(cantidad) -> int:
    if cantidad is None or isinstance(cantidad, bool) or not isinstance(cantidad, int) or cantidad < 1:
        raise ApiError(422, "VALIDACION", "Datos inválidos", {"cantidad": "Debe ser un entero de 1 o más"})
    return cantidad


def validar_apoyo_del_programa(apoyo_programa_id: uuid.UUID | None, programa_id: uuid.UUID) -> None:
    if apoyo_programa_id != programa_id:
        raise ApiError(422, "JERARQUIA_INVALIDA", "El apoyo no pertenece al programa", {"apoyo_id": "No es del programa"})


def validar_descripcion_del_apoyo(descripcion_apoyo_id: uuid.UUID | None, apoyo_id: uuid.UUID) -> None:
    if descripcion_apoyo_id != apoyo_id:
        raise ApiError(422, "JERARQUIA_INVALIDA", "La descripción no pertenece al apoyo",
                       {"descripcion_apoyo_id": "No es del apoyo elegido"})
