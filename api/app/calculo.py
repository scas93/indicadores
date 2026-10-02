"""Cálculo de cumplimiento y semáforo de un indicador (funciones puras, sin base de datos).

Es EL cálculo del sistema: sumatoria mensual → algoritmo → rango → color. Fase 3 (estadísticas,
Cuenta Pública, Transparencia) lo importa de aquí; nada se recalcula distinto en otro lado y
nada de esto se guarda en la base.

Colores: "verde" | "amarillo" | "rojo" (primer rango que contiene el cumplimiento),
"gris" (ausencia de resultado: sin meses capturados, o sumatoria_b = 0 / vacía con un algoritmo
que divide) y "sin_color" (hay resultado, pero cae fuera de los tres rangos configurados).
"gris" nunca sale de un rango configurable.
"""
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable, Mapping

VERDE, AMARILLO, ROJO, GRIS, SIN_COLOR = "verde", "amarillo", "rojo", "gris", "sin_color"

ALGORITMOS_QUE_DIVIDEN = frozenset({"a_sobre_b_pct", "a_sobre_b_menos1_pct", "a_sobre_b"})
ALGORITMOS = ALGORITMOS_QUE_DIVIDEN | {"a"}

Rango = tuple[Decimal | None, Decimal | None]  # (desde, hasta), ambos inclusivos
_DOS_DECIMALES = Decimal("0.01")


@dataclass(frozen=True)
class Resultado:
    sumatoria_a: Decimal | None
    sumatoria_b: Decimal | None  # siempre None con algoritmo "a": la variable B está bloqueada
    cumplimiento: Decimal | None  # redondeado a 2 decimales; None = no calculable
    color: str


def sumatoria(valores: Iterable[Decimal | None]) -> Decimal | None:
    """Suma solo los meses capturados: un mes sin captura (None) no cuenta ni como cero.
    Sin ningún mes capturado devuelve None (no 0)."""
    capturados = [v for v in valores if v is not None]
    return sum(capturados, Decimal(0)) if capturados else None


def cumplimiento_bruto(algoritmo: str | None, suma_a: Decimal | None,
                       suma_b: Decimal | None) -> Decimal | None:
    """Aplica el algoritmo a las sumatorias. None = no calculable (sin A, sin algoritmo, o el
    algoritmo divide y sumatoria_b es 0/vacía): nunca lanza ZeroDivisionError."""
    if algoritmo not in ALGORITMOS or suma_a is None:
        return None
    if algoritmo == "a":
        return suma_a
    if suma_b is None or suma_b == 0:
        return None
    razon = suma_a / suma_b
    if algoritmo == "a_sobre_b_pct":
        return razon * 100
    if algoritmo == "a_sobre_b_menos1_pct":
        return (razon - 1) * 100
    return razon


def redondear(valor: Decimal | None) -> Decimal | None:
    return None if valor is None else valor.quantize(_DOS_DECIMALES, rounding=ROUND_HALF_UP)


def color_por_rango(valor: Decimal, verde: Rango, amarillo: Rango, rojo: Rango) -> str:
    """Primer rango (verde, amarillo, rojo) que contiene el valor; límites inclusivos. Un rango
    sin configurar (None) no contiene nada. Fuera de los tres → SIN_COLOR (no gris)."""
    for nombre, (desde, hasta) in ((VERDE, verde), (AMARILLO, amarillo), (ROJO, rojo)):
        if desde is not None and hasta is not None and desde <= valor <= hasta:
            return nombre
    return SIN_COLOR


def evaluar(algoritmo: str | None, avances: Iterable[tuple[Decimal | None, Decimal | None]],
            verde: Rango = (None, None), amarillo: Rango = (None, None),
            rojo: Rango = (None, None)) -> Resultado:
    """`avances`: pares (valor_a, valor_b) de los meses del año (None = sin captura).
    El cumplimiento se redondea a 2 decimales y el color se decide sobre ese valor redondeado,
    que es el que ve el usuario."""
    pares = list(avances)
    suma_a = sumatoria(a for a, _ in pares)
    # Con "solo A" la variable B no existe: aunque haya B guardado de antes, se ignora.
    suma_b = None if algoritmo == "a" else sumatoria(b for _, b in pares)
    valor = redondear(cumplimiento_bruto(algoritmo, suma_a, suma_b))
    if valor is None:
        return Resultado(suma_a, suma_b, None, GRIS)
    return Resultado(suma_a, suma_b, valor, color_por_rango(valor, verde, amarillo, rojo))


def rangos_de(fila: Mapping | object) -> tuple[Rango, Rango, Rango]:
    """Extrae (verde, amarillo, rojo) de un Indicador o de un dict con las columnas rango_*."""
    def g(k):
        return fila.get(k) if isinstance(fila, Mapping) else getattr(fila, k)
    return tuple((g(f"rango_{c}_desde"), g(f"rango_{c}_hasta"))  # type: ignore[return-value]
                 for c in ("verde", "amarillo", "rojo"))
