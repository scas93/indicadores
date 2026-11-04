"""Reglas de las Estadísticas del Padrón (Fase 4.3a). Funciones puras: sin base de datos.

Regla general de conteo: "número de apoyos" = número de CAPTURAS registradas (no beneficiarios distintos ni la suma de
`cantidad`)."""
from collections import Counter
from datetime import date
from typing import Iterable, Mapping, Sequence

from .errors import ApiError

SIN_GRUPO = "Sin grupo"
SIN_NIVEL = "Sin nivel"
SIN_LOCALIDAD = "Sin localidad"
ANIO_MINIMO = 2021
TOP = 5
MSG_CONCENTRADO = "Para Generar Tipo Concentrado debe tener un CURP valido"


def contar(etiquetas: Iterable[str | None], sin: str) -> list[tuple[str, int]]:
    """Capturas por etiqueta, de mayor a menor (empate: por nombre). Lo que no tiene etiqueta cuenta como `sin`,
    así los totales de cada gráfica suman lo mismo que el resto."""
    c = Counter((e if e else sin) for e in etiquetas)
    return sorted(c.items(), key=lambda kv: (-kv[1], kv[0].lower()))


def top_n(conteos: Sequence[tuple[str, int]] | Mapping[str, int], n: int = TOP,
          excluir: Iterable[str] = ()) -> list[tuple[str, int]]:
    """Las `n` etiquetas con más capturas (empate: por nombre). `excluir` deja fuera, p. ej., "Sin localidad"."""
    items = conteos.items() if isinstance(conteos, Mapping) else conteos
    fuera = set(excluir)
    return sorted(((k, v) for k, v in items if k not in fuera), key=lambda kv: (-kv[1], kv[0].lower()))[:n]


def porcentaje(parte: int, total: int) -> float:
    return round(parte * 100 / total, 1) if total else 0.0


def conteo_genero(generos: Iterable[str | None]) -> dict:
    """Femenino / Masculino sobre el TOTAL de apoyos (los que no tienen género cuentan en el total, en ninguno de los dos)."""
    g = list(generos)
    total, f, m = len(g), sum(x == "F" for x in g), sum(x == "M" for x in g)
    return {"femenino": f, "masculino": m, "sin_dato": total - f - m, "total": total,
            "pct_femenino": porcentaje(f, total), "pct_masculino": porcentaje(m, total)}


def anios_del_rango(ini: int, fin: int) -> list[int]:
    return list(range(ini, fin + 1))


def validar_rango_anios(ini: int | None, fin: int | None, actual: int) -> tuple[int, int]:
    """Años entre 2021 y el actual; el inicial no puede ser mayor que el final."""
    ini, fin = actual if ini is None else ini, actual if fin is None else fin
    errores = {}
    for campo, v in (("anio_ini", ini), ("anio_fin", fin)):
        if not ANIO_MINIMO <= v <= actual:
            errores[campo] = f"Debe estar entre {ANIO_MINIMO} y {actual}"
    if not errores and ini > fin:
        errores["anio_fin"] = "No puede ser menor al año inicial"
    if errores:
        raise ApiError(422, "RANGO_INVALIDO", "Rango de años inválido", errores)
    return ini, fin


def validar_rango_fechas(ini: date | None, fin: date | None, hoy: date) -> tuple[date, date]:
    """Ambas por defecto hoy; la inicial no puede ser posterior a la final."""
    ini, fin = ini or hoy, fin or hoy
    if ini > fin:
        raise ApiError(422, "RANGO_INVALIDO", "Rango de fechas inválido", {"fecha_fin": "No puede ser anterior a la inicial"})
    return ini, fin


def validar_curp_concentrado(curp: str | None, existe: bool | None = None) -> str:
    """El Concentrado es la ficha de UN beneficiario: exige una CURP (y que exista, cuando ya se consultó)."""
    curp = (curp or "").strip().upper()
    if not curp or existe is False:
        raise ApiError(422, "CURP_INVALIDA", MSG_CONCENTRADO, {"curp": MSG_CONCENTRADO})
    return curp


def etiqueta_colonia(clave: str | None, nombre: str | None, texto_libre: str | None) -> str:
    """Una colonia del catálogo se muestra como "[clave]Nombre"; una escrita a mano, tal cual."""
    if clave is not None and nombre:
        return f"[{clave}]{nombre}"
    return (texto_libre or "").strip()


def apoyos_por_anio(filas: Iterable[tuple[str, int]], anios: Sequence[int]) -> dict[str, dict[int, int]]:
    """(etiqueta, año) -> {etiqueta: {año: capturas}}, con todos los años del rango (0 si no hubo)."""
    r: dict[str, dict[int, int]] = {}
    for etiqueta, anio in filas:
        r.setdefault(etiqueta, {a: 0 for a in anios})
        if anio in r[etiqueta]:
            r[etiqueta][anio] += 1
    return r


def comparativo_top(filas: Iterable[tuple[str | None, int]], anios: Sequence[int], n: int = TOP) -> list[dict]:
    """Top `n` localidades según el total del RANGO completo, con su conteo por año. Las capturas sin localidad
    no compiten por un lugar del top."""
    por = apoyos_por_anio(((l, a) for l, a in filas if l), anios)
    totales = {k: sum(v.values()) for k, v in por.items()}
    return [{"nombre": k, "total": t, "anios": por[k]} for k, t in top_n(totales, n)]
