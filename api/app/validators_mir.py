"""Reglas de negocio de la MIR y la captura de avances (funciones puras, sin base de datos)."""
import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable, Mapping

from .errors import ApiError

NIVELES_UNICOS = frozenset({"fin", "proposito"})


def normalizar_valor(valor, campo: str) -> Decimal | None:
    """Valor numérico de captura (A/B, metas, rangos): 4 decimales como la columna Numeric(18,4)."""
    if valor is None:
        return None
    try:
        d = Decimal(str(valor)) if not isinstance(valor, Decimal) else valor
        if not d.is_finite() or abs(d) >= Decimal(10) ** 13:
            raise ValueError
    except (ArithmeticError, ValueError):
        raise ApiError(422, "VALOR_INVALIDO", "Valor numérico inválido", {campo: "Número inválido o fuera de rango"})
    return d.quantize(Decimal("0.0001"))


def usa_b(algoritmo: str | None) -> bool:
    """La variable B existe salvo con "solo A" (sin algoritmo aún, todavía no se bloquea)."""
    return algoritmo != "a"


# --- matriz --------------------------------------------------------------------
def validar_alta_nivel_unico(nivel: str, niveles_existentes: Iterable[str]) -> None:
    """Fin y Propósito son únicos por programa: se rechaza un segundo alta."""
    if nivel in NIVELES_UNICOS and nivel in set(niveles_existentes):
        raise ApiError(409, "NIVEL_UNICO", f"El programa ya tiene {nivel.replace('proposito', 'propósito')}",
                       {"nivel": "Solo puede haber uno por programa"})


def validar_eliminable(nivel: str) -> None:
    if nivel in NIVELES_UNICOS:
        raise ApiError(409, "NIVEL_NO_ELIMINABLE", "El Fin y el Propósito no se pueden eliminar")


# --- rangos del semáforo -------------------------------------------------------
Rango = tuple[Decimal | None, Decimal | None]


def validar_rangos(verde: Rango, amarillo: Rango, rojo: Rango) -> None:
    """Cada rango se captura completo (desde y hasta) o vacío, con desde <= hasta, y los tres
    configurados no se traslapan (intervalos cerrados: tocarse en un extremo también traslapa).
    No se exige que cubran todo el eje numérico."""
    err: dict[str, str] = {}
    activos: list[tuple[str, Decimal, Decimal]] = []
    for nombre, (d, h) in (("verde", verde), ("amarillo", amarillo), ("rojo", rojo)):
        if d is None and h is None:
            continue
        if d is None or h is None:
            err[f"rango_{nombre}"] = "Captura desde y hasta"
        elif d > h:
            err[f"rango_{nombre}"] = "«Desde» no puede ser mayor que «hasta»"
        else:
            activos.append((nombre, d, h))
    for i, (n1, d1, h1) in enumerate(activos):
        for n2, d2, h2 in activos[i + 1:]:
            if max(d1, d2) <= min(h1, h2):
                err[f"rango_{n2}"] = f"Se traslapa con el rango {n1}"
    if err:
        raise ApiError(422, "RANGOS_INVALIDOS", "Los rangos del semáforo son inválidos", err)


# --- metas ---------------------------------------------------------------------
def validar_metas_permitidas(algoritmo: str | None, frecuencia_id) -> None:
    """No se guarda una meta anual sin algoritmo y frecuencia definidos (422 con lo que falta)."""
    faltan = {}
    if not algoritmo:
        faltan["algoritmo"] = "Elige el algoritmo en Ficha técnica"
    if not frecuencia_id:
        faltan["frecuencia_id"] = "Elige la frecuencia en Ficha técnica"
    if faltan:
        nombres = {"algoritmo": "el algoritmo", "frecuencia_id": "la frecuencia"}
        raise ApiError(422, "FICHA_INCOMPLETA",
                       "Para guardar metas primero define " + " y ".join(nombres[k] for k in faltan), faltan)


def validar_anio(anio) -> int:
    if not isinstance(anio, int) or isinstance(anio, bool) or anio < 2000 or anio > 2100:
        raise ApiError(422, "ANIO_INVALIDO", "Año fuera de rango (2000-2100)", {"anio": "2000-2100"})
    return anio


def validar_metas_anuales(algoritmo: str | None, metas: list[Mapping]) -> None:
    """Años únicos y válidos, a lo más un año fiscal vigente y B bloqueada con "solo A"."""
    anios = [validar_anio(m.get("anio")) for m in metas]
    if len(set(anios)) != len(anios):
        raise ApiError(422, "ANIO_REPETIDO", "Hay años repetidos en las metas", {"metas": "Años repetidos"})
    if sum(1 for m in metas if m.get("es_ejercicio_fiscal")) > 1:
        raise ApiError(422, "EJERCICIO_FISCAL_MULTIPLE", "Solo un año puede ser el ejercicio fiscal vigente",
                       {"metas": "Marca un solo año fiscal"})
    if not usa_b(algoritmo) and any(m.get("valor_b_programado") is not None for m in metas):
        raise ApiError(422, "VARIABLE_B_BLOQUEADA", "Con el algoritmo «Solo A» la variable B no se captura",
                       {"valor_b_programado": "Bloqueada"})


# --- avances -------------------------------------------------------------------
def validar_mes(mes) -> int:
    if not isinstance(mes, int) or isinstance(mes, bool) or mes < 1 or mes > 12:
        raise ApiError(422, "MES_INVALIDO", "El mes debe ser de 1 a 12", {"mes": "1-12"})
    return mes


def mes_capturable(anio: int, mes: int, hoy: date, activos: Iterable[int], tolerancia_dias: int) -> bool:
    """Un mes M es capturable si está en los meses activos del municipio, o si todavía estamos
    dentro de la ventana de gracia: hoy <= último día de M + tolerancia (días).
    Lista de activos vacía = automático: los 12 meses activos, sin tolerancia."""
    activos = set(activos)
    if not activos or mes in activos:
        return True
    ultimo = date(anio, mes, calendar.monthrange(anio, mes)[1])
    return hoy <= ultimo + timedelta(days=tolerancia_dias)


def validar_avances_b(algoritmo: str | None, meses: Iterable[Mapping]) -> None:
    """Con "solo A" el servidor rechaza cualquier valor de B (no solo lo oculta el front)."""
    if usa_b(algoritmo):
        return
    mal = sorted(m["mes"] for m in meses if m.get("valor_b") is not None)
    if mal:
        raise ApiError(422, "VARIABLE_B_BLOQUEADA", "Con el algoritmo «Solo A» la variable B no se captura",
                       {f"mes_{x}": "Variable B bloqueada" for x in mal})


@dataclass(frozen=True)
class MesRechazado:
    mes: int
    codigo: str
    mensaje: str


def clasificar_meses(anio: int, entrantes: list[Mapping],
                     vigentes: Mapping[int, tuple[Decimal | None, Decimal | None]], hoy: date,
                     activos: Iterable[int], tolerancia_dias: int
                     ) -> tuple[list[Mapping], list[MesRechazado]]:
    """Separa los meses a escribir de los rechazados. Un mes sin cambios respecto a lo ya guardado
    se omite sin error (el front manda los 12 meses, incluidos los bloqueados); uno que cambia y
    no es capturable se rechaza con detalle sin bloquear a los demás."""
    activos = list(activos)
    aceptados: list[Mapping] = []
    rechazados: list[MesRechazado] = []
    for m in entrantes:
        mes = validar_mes(m.get("mes"))
        if (m.get("valor_a"), m.get("valor_b")) == tuple(vigentes.get(mes, (None, None))):
            continue
        if mes_capturable(anio, mes, hoy, activos, tolerancia_dias):
            aceptados.append(m)
        else:
            rechazados.append(MesRechazado(
                mes, "MES_NO_CAPTURABLE", "El mes está fuera de los meses activos y de los días de tolerancia"))
    return aceptados, rechazados
