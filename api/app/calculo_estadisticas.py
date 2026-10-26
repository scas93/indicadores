"""Fase 3 — reglas puras de las estadísticas (sin base de datos).

Reutiliza `app.calculo` (Fase 2) tal cual: aquí solo se decide QUÉ valor se compara contra los rangos
de color según el modo, y cómo se cuentan los colores. Lo que Fase 2 llama `sin_color` (resultado
fuera de los tres rangos) se cuenta y se pinta como GRIS en estos reportes, de modo que siempre
verde + amarillo + rojo + gris = total.
"""
from decimal import Decimal
from typing import Iterable

from . import calculo
from .calculo import AMARILLO, GRIS, ROJO, SIN_COLOR, VERDE, Rango, Resultado

OBTENIDO = "obtenido"  # "Cumplimiento Obtenido": el resultado de la fórmula tal cual
CO_CE = "co_ce"        # "(C.O / C.E) * 100": resultado de la fórmula ÷ meta anual numérica × 100
MODOS = (OBTENIDO, CO_CE)
COLORES = (VERDE, AMARILLO, ROJO, GRIS)
_CIEN = Decimal(100)


def meta_numerica(algoritmo: str | None, a_programado: Decimal | None,
                  b_programado: Decimal | None) -> Decimal | None:
    """Meta anual numérica = el mismo algoritmo aplicado a lo programado (A y B del año).
    Es independiente del texto descriptivo de la meta. None = no calculable."""
    return calculo.cumplimiento_bruto(algoritmo, a_programado, b_programado)


def valor_y_color(modo: str, resultado: Resultado, meta: Decimal | None,
                  verde: Rango, amarillo: Rango, rojo: Rango) -> tuple[Decimal | None, str]:
    """(valor evaluado, color) del indicador en el modo dado. Color siempre en COLORES.

    - obtenido: valor = cumplimiento de Fase 2; el color ya viene calculado.
    - co_ce: valor = cumplimiento ÷ meta × 100 (2 decimales, ROUND_HALF_UP); meta nula o 0 → gris.
    TODO(pendiente de verificación con datos de año en curso): no se prorratea la meta; se usa
    siempre la meta anual completa.
    """
    if modo not in MODOS:
        raise ValueError(f"modo de cumplimiento desconocido: {modo}")
    if modo == OBTENIDO:
        return resultado.cumplimiento, _a_gris(resultado.color)
    if resultado.cumplimiento is None or meta is None or meta == 0:
        return None, GRIS
    valor = calculo.redondear(resultado.cumplimiento / meta * _CIEN)
    return valor, _a_gris(calculo.color_por_rango(valor, verde, amarillo, rojo))


def _a_gris(color: str) -> str:
    return GRIS if color == SIN_COLOR else color


def conteo_vacio() -> dict[str, int]:
    return {**{c: 0 for c in COLORES}, "total": 0}


def contar(colores: Iterable[str]) -> dict[str, int]:
    """{'verde','amarillo','rojo','gris','total'}; cualquier color fuera de COLORES cuenta como gris."""
    out = conteo_vacio()
    for c in colores:
        out[c if c in COLORES else GRIS] += 1
        out["total"] += 1
    return out


def sumar(conteos: Iterable[dict[str, int]]) -> dict[str, int]:
    out = conteo_vacio()
    for c in conteos:
        for k in out:
            out[k] += c[k]
    return out


def indicador_con_datos(meta_a: Decimal | None, avances: Iterable[tuple[Decimal | None, Decimal | None]]
                        ) -> bool:
    """Un indicador entra al conteo del año solo con meta anual programada Y al menos un mes con
    algún valor capturado. (Verificado solo para un año sin ningún dato: 0/0/0/0. El caso "con meta
    pero sin capturas" queda fuera del conteo PENDIENTE DE VERIFICACIÓN contra el sistema de
    referencia.)"""
    return meta_a is not None and any(a is not None or b is not None for a, b in avances)


def formula_con_descripciones(algoritmo: str | None, descripcion_a: str | None, descripcion_b: str | None) -> str:
    """La fórmula con la descripción de cada variable, con el formato de la referencia, p. ej.
    "((A: NÚMERO DE AFILIADOS AL IMSS, AÑO ACTUAL. / B: NÚMERO DE AFILIADO AL IMSS, AÑO ANTERIOR.) - 1) * 100".
    Con "solo A": "A: <descripción>". Sin algoritmo, vacío."""
    a, b = f"A: {descripcion_a or ''}", f"B: {descripcion_b or ''}"
    return {"a": a, "a_sobre_b_pct": f"({a} / {b}) * 100", "a_sobre_b_menos1_pct": f"(({a} / {b}) - 1) * 100",
            "a_sobre_b": f"{a} / {b}"}.get(algoritmo or "", "")
