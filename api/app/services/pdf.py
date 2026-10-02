"""Render de los PDF de la fase (ReportLab). Reciben diccionarios ya armados por los servicios:
aquí no hay consultas ni reglas de negocio, solo presentación. La estructura de FN y FA y el
detalle de los 5 PDF de módulo están pendientes de verificación visual contra el sistema de
referencia (sin acceso de administrador): se construyeron siguiendo la especificación."""
import html
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ALGORITMO_TEXTO = {
    "a_sobre_b_pct": "(A / B) × 100", "a_sobre_b_menos1_pct": "((A / B) - 1) × 100",
    "a_sobre_b": "A / B", "a": "Solo A",
}
NIVEL_TEXTO = {"fin": "Fin", "proposito": "Propósito", "componente": "Componente", "actividad": "Actividad"}
COLOR_TEXTO = {"verde": "Verde", "amarillo": "Amarillo", "rojo": "Rojo", "gris": "Sin datos", "sin_color": "Fuera de rango"}
COLOR_FONDO = {"verde": "#5CC691", "amarillo": "#F1C500", "rojo": "#E55957", "gris": "#BDBDBD", "sin_color": "#FFFFFF"}
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

_base = getSampleStyleSheet()
H1 = ParagraphStyle("h1", parent=_base["Title"], fontSize=15, spaceAfter=4)
SUB = ParagraphStyle("sub", parent=_base["Normal"], fontSize=9, textColor=colors.HexColor("#555555"), alignment=1)
H2 = ParagraphStyle("h2", parent=_base["Heading3"], fontSize=11, spaceBefore=8, spaceAfter=4)
CEL = ParagraphStyle("cel", parent=_base["Normal"], fontSize=8, leading=10)
CELH = ParagraphStyle("celh", parent=CEL, fontName="Helvetica-Bold", textColor=colors.white)
CELB = ParagraphStyle("celb", parent=CEL, fontName="Helvetica-Bold")


def _p(texto, estilo=CEL) -> Paragraph:
    t = "" if texto is None else str(texto)
    return Paragraph(html.escape(t).replace("\n", "<br/>"), estilo)


def _num(v, dec=2) -> str:
    if v is None:
        return "—"
    return f"{v:,.{dec}f}".rstrip("0").rstrip(".") if isinstance(v, float) and dec > 2 else f"{v:,.{dec}f}"


def _tabla(filas, anchos, cabecera=True, extra=None) -> Table:
    t = Table(filas, colWidths=anchos, repeatRows=1 if cabecera else 0)
    est = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
           ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
    if cabecera:
        est += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#454545"))]
    t.setStyle(TableStyle(est + (extra or [])))
    return t


def _construir(titulo: str, programa: dict, story: list, pie: str = "") -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(letter), leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                            topMargin=1.5 * cm, bottomMargin=1.5 * cm, title=titulo, author="Indicadores")
    encabezado = [_p(titulo, H1),
                  _p(f"{programa['clave']} — {programa['nombre']}   |   Ejercicio {programa['ejercicio_fiscal']}", SUB),
                  _p(" · ".join(x for x in (programa.get("centro_gestor"), programa.get("eje"),
                                             programa.get("subtema"), programa.get("estrategia")) if x), SUB),
                  Spacer(1, 8)]

    def pagina(canvas, d):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.drawRightString(landscape(letter)[0] - 1.5 * cm, 0.8 * cm, f"{pie}  Página {d.page}".strip())
        canvas.restoreState()

    doc.build(encabezado + story, onFirstPage=pagina, onLaterPages=pagina)
    return buf.getvalue()


ANCHO = landscape(letter)[0] - 3 * cm


# --------------------------------------------------------------------------- árbol
def _planos(nodos: list[dict], profundidad: int = 0) -> list[tuple[dict, int]]:
    out = []
    for n in nodos:
        out.append((n, profundidad))
        out += _planos(n["hijos"], profundidad + 1)
    return out


def arbol_pdf(arbol: dict, tipo: str) -> bytes:
    """tipo: completo (problema y objetivo lado a lado) | problemas | objetivos."""
    enc = arbol["encabezado"]
    story: list = []
    cabecera = []
    if tipo in ("completo", "problemas"):
        cabecera.append([_p("Situación no deseada (problema)", CELB), _p(enc.get("problema") or "—")])
    if tipo in ("completo", "objetivos"):
        cabecera.append([_p("Objetivo", CELB), _p(enc.get("objetivo") or "—")])
    story.append(_tabla(cabecera, [5 * cm, ANCHO - 5 * cm], cabecera=False))
    for titulo, clave, ca, ob, etiqueta_ca, etiqueta_ob in (
            ("Efectos y fines", "efectos", "texto_efecto", "texto_fin", "Efecto", "Fin"),
            ("Causas y medios", "causas", "texto_causa", "texto_medio", "Causa", "Medio")):
        story.append(_p(titulo if tipo == "completo" else
                        (etiqueta_ca + "s" if tipo == "problemas" else etiqueta_ob + "s"), H2))
        filas = [[_p("No.", CELH)] + ([_p(etiqueta_ca, CELH)] if tipo != "objetivos" else [])
                 + ([_p(etiqueta_ob, CELH)] if tipo != "problemas" else [])]
        planos = _planos(arbol[clave])
        for n, prof in planos:
            sangria = "&nbsp;" * 4 * prof
            fila = [_p(n["numero"])]
            if tipo != "objetivos":
                fila.append(Paragraph(sangria + html.escape(n[ca] or "").replace("\n", "<br/>"), CEL))
            if tipo != "problemas":
                fila.append(Paragraph(sangria + html.escape(n[ob] or "").replace("\n", "<br/>"), CEL))
            filas.append(fila)
        if not planos:
            filas.append([_p("")] + [_p("Sin registros")] * (len(filas[0]) - 1))
        ncols = len(filas[0]) - 1
        story.append(_tabla(filas, [1.6 * cm] + [(ANCHO - 1.6 * cm) / ncols] * ncols))
    titulo_doc = {"completo": "Árbol de problemas y objetivos", "problemas": "Árbol de problemas",
                  "objetivos": "Árbol de objetivos"}[tipo]
    return _construir(titulo_doc, arbol["programa"], story)


# --------------------------------------------------------------------------- matriz
def _filas_matriz(matriz: dict) -> list[dict]:
    """Aplana la matriz en el orden de lectura: fin, propósito, cada componente y sus actividades."""
    filas = [matriz["fin"], matriz["proposito"]]
    for c in matriz["componentes"]:
        filas.append(c)
        filas += c["actividades"]
    return [f for f in filas if f]


def _etiqueta_nivel(e: dict) -> str:
    return (NIVEL_TEXTO[e["nivel"]] + (f" {e['numero']}" if e["numero"] else "")).strip()


def _texto_indicador(ind: dict, frecuencias: dict) -> str:
    f = ind["ficha"]
    partes = [f["nombre"] or "(sin nombre)"]
    if f["algoritmo"]:
        partes.append(f"Fórmula: {ALGORITMO_TEXTO[f['algoritmo']]}")
    if f["frecuencia_id"] and str(f["frecuencia_id"]) in frecuencias:
        partes.append(f"Frecuencia: {frecuencias[str(f['frecuencia_id'])]}")
    return "\n".join(partes)


def matriz_resultados_pdf(matriz: dict, frecuencias: dict) -> bytes:
    filas = [[_p(h, CELH) for h in ("Nivel", "Resumen narrativo", "Indicador", "Medios de verificación", "Supuestos")]]
    for e in _filas_matriz(matriz):
        indicadores = "\n\n".join(_texto_indicador(i, frecuencias) for i in e["indicadores"]) or "—"
        filas.append([_p(_etiqueta_nivel(e), CELB), _p(e["resumen_narrativo"]), _p(indicadores),
                      _p(e["medios_verificacion"]), _p(e["supuestos"])])
    w = ANCHO
    return _construir("Matriz de Indicadores de Resultados", matriz["programa"],
                      [_tabla(filas, [2.4 * cm, w * .24, w * .26, w * .22, w - 2.4 * cm - w * .72])])


def matriz_cumplimiento_pdf(matriz: dict, resultados: dict, anio: int, frecuencias: dict) -> bytes:
    """`resultados`: {indicador_id: {sumatoria_a, sumatoria_b, cumplimiento, color, meta_a, meta_b}}."""
    cab = ("Nivel", "Indicador", "Fórmula", "Meta A", "Meta B", "Σ A", "Σ B", "Cumplimiento", "Semáforo")
    filas = [[_p(h, CELH) for h in cab]]
    extra = []
    for e in _filas_matriz(matriz):
        for ind in e["indicadores"]:
            r = resultados.get(ind["id"]) or {}
            color = r.get("color", "gris")
            filas.append([_p(_etiqueta_nivel(e), CELB), _p(ind["ficha"]["nombre"]),
                          _p(ALGORITMO_TEXTO.get(ind["ficha"]["algoritmo"] or "", "—")),
                          _p(_num(r.get("meta_a"))), _p(_num(r.get("meta_b"))),
                          _p(_num(r.get("sumatoria_a"))), _p(_num(r.get("sumatoria_b"))),
                          _p(_num(r.get("cumplimiento"))), _p(COLOR_TEXTO[color])])
            extra.append(("BACKGROUND", (8, len(filas) - 1), (8, len(filas) - 1), colors.HexColor(COLOR_FONDO[color])))
    if len(filas) == 1:
        filas.append([_p("Sin indicadores registrados")] + [_p("")] * (len(cab) - 1))
    w = ANCHO
    anchos = [2.4 * cm, w * .27, 2.8 * cm, 1.8 * cm, 1.8 * cm, 1.8 * cm, 1.8 * cm, 2.4 * cm]
    anchos.append(w - sum(anchos))
    return _construir(f"Matriz de Cumplimiento de Indicadores — {anio}", matriz["programa"],
                      [_tabla(filas, anchos, extra=extra)])


# --------------------------------------------------------------------------- fichas por indicador
def _rangos_texto(rangos: dict) -> str:
    def t(c):
        r = rangos[c]
        return "—" if r["desde"] is None or r["hasta"] is None else f"{_num(r['desde'])} a {_num(r['hasta'])}"
    return f"Verde: {t('verde')}   Amarillo: {t('amarillo')}   Rojo: {t('rojo')}"


def ficha_narrativa_pdf(programa: dict, elemento: dict, indicador: dict, frecuencias: dict) -> bytes:
    """Ficha Narrativa: resumen del indicador + MIR del elemento al que pertenece."""
    f, m = indicador["ficha"], indicador["metas"]
    freq = frecuencias.get(str(f["frecuencia_id"]), "—") if f["frecuencia_id"] else "—"
    mir = [[_p("Nivel", CELB), _p(_etiqueta_nivel(elemento))],
           [_p("Resumen narrativo", CELB), _p(elemento["resumen_narrativo"])],
           [_p("Medios de verificación", CELB), _p(elemento["medios_verificacion"])],
           [_p("Supuestos", CELB), _p(elemento["supuestos"])],
           [_p("Evidencia", CELB), _p(elemento["evidencia"])]]
    ficha = [[_p("Indicador", CELB), _p(f["nombre"])],
             [_p("Interpretación", CELB), _p(f["interpretacion"])],
             [_p("Tipo", CELB), _p(f"{f['tipo'].capitalize()}{' (prioritario)' if f['prioritario'] else ''}")],
             [_p("Dimensión", CELB), _p((f["dimension"] or "—").capitalize())],
             [_p("Frecuencia", CELB), _p(freq)],
             [_p("Unidad de medida", CELB), _p(f["unidad_medida"])],
             [_p("Algoritmo", CELB), _p(ALGORITMO_TEXTO.get(f["algoritmo"] or "", "—"))],
             [_p("Variable A", CELB), _p(f["unidad_a"])]]
    if f["algoritmo"] != "a":
        ficha.append([_p("Variable B", CELB), _p(f["unidad_b"])])
    ficha += [[_p("Año base", CELB), _p(m["anio_base"] if m["anio_base"] is not None else "—")],
              [_p("Meta de la administración", CELB), _p(_num(m["meta_administracion"]))],
              [_p("Semáforo", CELB), _p(_rangos_texto(indicador["rangos"]))]]
    w = [5.5 * cm, ANCHO - 5.5 * cm]
    return _construir("Ficha Narrativa", programa,
                      [_p("Matriz de indicadores", H2), _tabla(mir, w, cabecera=False),
                       _p("Ficha técnica del indicador", H2), _tabla(ficha, w, cabecera=False)])


def ficha_avance_pdf(programa: dict, elemento: dict, rejilla: dict) -> bytes:
    """Ficha de Avance: metas + rejilla de 12 meses + sumatoria y cumplimiento del año."""
    ind = rejilla["indicador"]
    usa_b = ind["usa_b"]
    meta = rejilla["meta"] or {}
    cab = [_p("", CELH)] + [_p(m, CELH) for m in MESES] + [_p("Σ", CELH)]
    filas = [cab, [_p("Variable A", CELB)] + [_p(_num(x["valor_a"])) for x in rejilla["meses"]]
             + [_p(_num(rejilla["sumatoria_a"]))]]
    if usa_b:
        filas.append([_p("Variable B", CELB)] + [_p(_num(x["valor_b"])) for x in rejilla["meses"]]
                     + [_p(_num(rejilla["sumatoria_b"]))])
    anchos = [2.2 * cm] + [(ANCHO - 4.4 * cm) / 12] * 12 + [2.2 * cm]
    resumen = [[_p("Indicador", CELB), _p(ind["nombre"])],
               [_p("Nivel", CELB), _p(_etiqueta_nivel({"nivel": ind["nivel"], "numero": ind["numero"]}))],
               [_p("Fórmula", CELB), _p(ALGORITMO_TEXTO.get(ind["algoritmo"] or "", "—"))],
               [_p("Línea base / meta administración", CELB),
                _p(f"{ind['anio_base'] if ind['anio_base'] is not None else '—'} / {_num(ind['meta_administracion'])}")],
               [_p(f"Meta {rejilla['anio']}", CELB),
                _p(f"A: {_num(meta.get('valor_a_programado'))}" + (f"   B: {_num(meta.get('valor_b_programado'))}" if usa_b else ""))],
               [_p("Semáforo", CELB), _p(_rangos_texto(rejilla["rangos"]))]]
    color = rejilla["color"]
    resultado = [[_p("Cumplimiento", CELB), _p(_num(rejilla["cumplimiento"])), _p("Semáforo", CELB), _p(COLOR_TEXTO[color])]]
    w = [5.5 * cm, ANCHO - 5.5 * cm]
    return _construir(f"Ficha de Avance — {rejilla['anio']}", programa, [
        _tabla(resumen, w, cabecera=False), _p("Avance mensual", H2), _tabla(filas, anchos),
        Spacer(1, 8),
        _tabla(resultado, [4 * cm, 4 * cm, 4 * cm, 4 * cm], cabecera=False,
               extra=[("BACKGROUND", (3, 0), (3, 0), colors.HexColor(COLOR_FONDO[color]))])])
