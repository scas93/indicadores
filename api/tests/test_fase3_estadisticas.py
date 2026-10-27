"""Fase 3 — Estadísticas vía API: casos de aceptación 1, 2, 3, 6 y 7 (alcance, conteos, equivalencias).
Los casos 4 y 5 (estructura exacta de columnas de las exportaciones) son verificación manual contra el
sistema de referencia; aquí solo hay un humo de que existen y tienen 38 / 26 columnas.

Datos reales: los 19 indicadores del programa 1014 (ECONÓMICO) 2025 salen del export de Cuenta Pública
del sistema de referencia (A/B mensuales, resultado alcanzado y avance/programado). Los rangos de color
NO vienen en el export (solo los del 410): son INFERIDOS para reproducir los conteos verificados en vivo
— RANGOS INFERIDOS, PENDIENTES DE VERIFICACIÓN."""
import pytest

from .test_fase1_flujos import m  # noqa: F401  (fixture `m`)
from .test_fase2_flujos import Ctx, hoy_fijo, usuario_con  # noqa: F401  (hoy_fijo es autouse)
from seed_data import economico_2025 as datos

ESPERADO = datos.CONTEOS_2025


def meses(valores):
    return [{"mes": i, "valor_a": v, "valor_b": None} for i, v in enumerate(valores, 1) if v is not None]


def _crear(ctx: Ctx, ind: dict, anio=2025) -> dict:
    """Crea un indicador del dataset real con su meta, rangos (reales/inferidos) y avances del año."""
    nuevo = ctx.nuevo_indicador(algoritmo=ind["algoritmo"], nombre=ind["ref"], rangos=datos.rangos_de(ind), anuales=[
        {"anio": anio, "valor_a_programado": ind["meta_a"], "valor_b_programado": ind["meta_b"], "es_ejercicio_fiscal": True}])
    pares = [{"mes": i, "valor_a": a, "valor_b": b if ind["algoritmo"] != "a" else None}
             for i, (a, b) in enumerate(zip(ind["A"], ind["B"]), 1) if a is not None or b is not None]
    r = ctx.put(nuevo, pares, anio=anio)
    assert r.status_code == 200, r.text
    return nuevo


def cargar_2025(ctx: Ctx, anio=2025) -> dict[str, dict]:
    """Crea los 19 indicadores con sus metas, rangos y avances 2025; devuelve {id_ref: indicador}."""
    return {ind["ref"]: _crear(ctx, ind, anio) for ind in datos.INDICADORES}


def stats(m, c, ruta, **params):
    return m.get(c, f"/api/estadisticas/{ruta}", params=params)


def totales(grupos):
    return {k: sum(g[k] for g in grupos) for k in ("verde", "amarillo", "rojo", "gris", "total")}


# =========================================================== API: criterios 1, 2, 6, 7
@pytest.fixture()
def eco(m):
    """ECONÓMICO 2025: 19 indicadores en un programa, visibles para un usuario de Informes."""
    ctx = Ctx(m)
    cargar_2025(ctx)
    sub = m.get(m.admin, "/api/subtemas").json()[0]["id"]  # el programa cuelga de Eje → Subtema
    assert m.patch(m.admin, f"/api/programas/{ctx.pid}", {"subtema_id": sub}).status_code == 200
    return ctx, usuario_con(m, [ctx.pid], "info1", tipo="informes")


@pytest.mark.parametrize("modo", ["obtenido", "co_ce"])
def test_caso2_dependencias_reproduce_los_conteos_de_la_referencia(m, eco, modo):
    ctx, u = eco
    g = stats(m, u, "dependencias", anio=2025, tipo_cumplimiento=modo).json()["grupos"]
    assert len(g) == 1 and g[0]["id"] == ctx.cg["id"]
    assert {k: g[0][k] for k in ESPERADO[modo]} == ESPERADO[modo]


def test_caso2_eje_economico_2025_14_0_4_1_y_criterio1_mismo_total_en_los_4_reportes(m, eco):
    ctx, u = eco
    base = dict(anio=2025, tipo_cumplimiento="co_ce")
    ejes = stats(m, u, "ejes", **base).json()["grupos"]
    assert ejes[0]["nombre"] == "Eje" and {k: ejes[0][k] for k in ESPERADO["co_ce"]} == ESPERADO["co_ce"]
    reportes = {
        "dependencias": stats(m, u, "dependencias", **base).json()["grupos"],
        "ejes": ejes,
        "consolidado": stats(m, u, "consolidado", **base).json()["grupos"],
        "cumplimiento-metas": stats(m, u, "cumplimiento-metas", centro_gestor_id=ctx.cg["id"], **base).json()["grupos"],
    }
    for nombre, grupos in reportes.items():
        t = totales(grupos)
        assert t["verde"] + t["amarillo"] + t["rojo"] + t["gris"] == t["total"] == 19, nombre
        assert t == totales(reportes["dependencias"]), nombre


def test_detalle_clic_en_color_muestra_valores_del_modo_activo(m, eco):
    ctx, u = eco
    gris = stats(m, u, "indicadores", anio=2025, tipo_cumplimiento="co_ce", color="gris").json()["indicadores"]
    assert [i["nombre"] for i in gris] == ["410"] and gris[0]["cumplimiento"] == 99.9
    assert gris[0]["cumplimiento_obtenido"] == 9.99 and gris[0]["meta_anual"] == 10.0
    amar = stats(m, u, "indicadores", anio=2025, tipo_cumplimiento="obtenido", color="amarillo").json()["indicadores"]
    esperado = [i for i in datos.INDICADORES if i["color_obtenido"] == "amarillo"]  # colores inferidos (ver el dataset)
    assert [i["nombre"] for i in amar] == [e["ref"] for e in esperado] and amar[0]["cumplimiento"] == esperado[0]["alcanzada"]
    todos = stats(m, u, "indicadores", anio=2025, tipo_cumplimiento="obtenido").json()["indicadores"]
    assert len(todos) == 19 and {"programa", "dependencia", "eje", "algoritmo", "sumatoria_a", "color"} <= set(todos[0])
    eje_id = stats(m, u, "opciones").json()["ejes"][0]["id"]
    assert len(stats(m, u, "indicadores", anio=2025, eje_id=eje_id).json()["indicadores"]) == 19


def test_anio_sin_datos_da_cero_y_no_error(m, eco):
    _, u = eco
    g = stats(m, u, "dependencias", anio=2026).json()["grupos"]
    assert g[0]["total"] == 0 and g[0]["gris"] == 0  # no todo gris: el indicador sin año no entra


def test_modo_invalido_es_422(m, eco):
    _, u = eco
    r = stats(m, u, "dependencias", anio=2025, tipo_cumplimiento="otro")
    assert r.status_code == 422 and r.json()["campos"]["tipo_cumplimiento"]


def test_caso6_solo_programas_asignados_a_tipos_distintos_de_administrador_y_alcalde(m):
    ctx = Ctx(m)
    cargar_2025(ctx)
    otro = m.programa("P2", ctx.cg)  # mismo centro gestor, programa NO asignado al usuario
    ctx2 = Ctx.__new__(Ctx)
    ctx2.m, ctx2.cg, ctx2.prog, ctx2.pid, ctx2.frec = m, ctx.cg, otro, otro["id"], ctx.frec
    ctx2.mat = m.get(m.admin, f"/api/programas/{otro['id']}/matriz").json()
    ajeno = ctx2.nuevo_indicador(algoritmo="a", nombre="ajeno", rangos={"verde": {"desde": 0, "hasta": 100}}, anuales=[
        {"anio": 2025, "valor_a_programado": 10, "valor_b_programado": None, "es_ejercicio_fiscal": True}])
    ctx2.put(ajeno, meses([10]), anio=2025)  # con meta y captura: SÍ entraría si estuviera en el alcance
    ind = ctx2.mat["fin"]["id"]  # captura para que el ajeno califique como "con datos"
    # (el indicador ajeno se crea con meta; su avance se captura como administrador)
    from app.models import Indicador
    nuevo = [i for i in m.get(m.admin, f"/api/elementos-matriz/{ind}/indicadores").json()] \
        if False else None  # noqa: F841
    u = usuario_con(m, [ctx.pid], "info1", tipo="informes")
    g = stats(m, u, "dependencias", anio=2025).json()["grupos"]
    assert g[0]["total"] == 19  # los del programa ajeno nunca cuentan
    assert {i["programa"] for i in stats(m, u, "indicadores", anio=2025).json()["indicadores"]} == {
        f"{ctx.prog['clave']} — {ctx.prog['nombre']}"}
    # exportar un programa fuera de alcance → 403 (en conteos sería 0)
    r = stats(m, u, "exportar/cuenta-publica", anio=2025, centro_gestor_id=ctx.cg["id"], programa_id=otro["id"])
    assert r.status_code == 403 and r.json()["codigo"] == "PROGRAMA_NO_ASIGNADO"
    r = stats(m, u, "transparencia", anio=2025, centro_gestor_id=ctx.cg["id"], programa_id=otro["id"])
    assert r.status_code == 403
    # sin programas asignados: ceros, y selectores vacíos (error nunca)
    m.usuario("sin1", "informes")
    sin = m.cliente("sin1", "pw")
    assert stats(m, sin, "dependencias", anio=2025).json()["grupos"] == []
    assert stats(m, sin, "opciones").json() == {"anios": [], "centros_gestores": [], "ejes": [], "programas": []}
    assert stats(m, sin, "dependencias", anio=2025, **{"centro_gestor_ids[]": ctx.cg["id"]}).json()["grupos"][0]["total"] == 0


def test_caso6_exportar_sin_programa_asignado_es_403_y_con_programa_asignado_es_xlsx(m):
    ctx = Ctx(m)
    cargar_2025(ctx)
    m.usuario("sin1", "informes")
    r = stats(m, m.cliente("sin1", "pw"), "exportar/transparencia", anio=2025, centro_gestor_id=ctx.cg["id"], programa_id=ctx.pid)
    assert r.status_code == 403
    u = usuario_con(m, [ctx.pid], "alc1", tipo="alcalde")
    r = stats(m, u, "exportar/transparencia", anio=2025, centro_gestor_id=ctx.cg["id"], programa_id=ctx.pid)
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert "attachment" in r.headers["content-disposition"]


def test_caso7_seleccion_multiple_equivale_a_sumar_cada_dependencia(m):
    a, b = Ctx(m, "A"), Ctx(m, "B")
    cargar_2025(a)
    for ind in datos.INDICADORES[:6]:  # un subconjunto distinto en la segunda dependencia
        _crear(b, ind)
    u = usuario_con(m, [a.pid, b.pid], "info1", tipo="informes")
    ids = [a.cg["id"], b.cg["id"]]
    multi = stats(m, u, "consolidado", anio=2025, tipo_cumplimiento="co_ce", **{"centro_gestor_ids[]": ids}).json()["grupos"]
    sueltas = [stats(m, u, "dependencias", anio=2025, tipo_cumplimiento="co_ce", **{"centro_gestor_ids[]": [i]}).json()["grupos"][0]
               for i in ids]
    assert multi == sueltas and len(multi) == 2
    assert totales(multi)["total"] == 19 + 6
    # y "ninguna seleccionada" = todas las del alcance, sin duplicados
    todas = stats(m, u, "dependencias", anio=2025, tipo_cumplimiento="co_ce").json()["grupos"]
    assert sorted(g["id"] for g in todas) == sorted(ids) and totales(todas) == totales(multi)


# =========================================================== caso 3 y exportaciones (humo)
def test_caso3_indicador_416_fin_algoritmo_a_meta_100_avance_86(m):
    """Fila real de Transparencia (programa 1017, 2025): Fin, algoritmo A, meta 100, avance 86.00."""
    ctx = Ctx(m)
    ind = ctx.nuevo_indicador(algoritmo="a", nombre="VARIACIÓN EN EL DESARROLLO HUMANO EN EL MUNICIPIO",
                              rangos={"verde": {"desde": 80, "hasta": 100}},
                              anuales=[{"anio": 2025, "valor_a_programado": 100, "valor_b_programado": None,
                                        "es_ejercicio_fiscal": True}])
    ctx.put(ind, meses([20, 20, 20, 26]), anio=2025)  # 86
    u = usuario_con(m, [ctx.pid], "info1", tipo="informes")
    t = stats(m, u, "transparencia", anio=2025, centro_gestor_id=ctx.cg["id"], programa_id=ctx.pid).json()
    assert len(t["encabezados"]) == 26 and len(t["filas"]) == 1 and all(len(f) == 26 for f in t["filas"])
    fila = dict(zip(t["encabezados"], t["filas"][0]))
    assert fila["Nivel de la MIR"] == "Fin" and fila["Algoritmo"] == "A"
    assert fila["Metas programadas del año en análisis"] == 100 and fila["Avance de las metas"] == 86
    d = stats(m, u, "indicadores", anio=2025, tipo_cumplimiento="co_ce").json()["indicadores"][0]
    assert d["cumplimiento_obtenido"] == 86 and d["cumplimiento"] == 86  # avance = alcanzada / 100 * 100


def test_cuenta_publica_38_columnas_dos_filas_por_indicador_y_xlsx_valido(m, eco):
    ctx, u = eco
    t = stats(m, u, "cuenta-publica", anio=2025, centro_gestor_id=ctx.cg["id"], programa_id=ctx.pid).json()
    assert len(t["encabezados"]) == 38 and sum(s for _, s in t["grupos"]) == 38
    assert len(t["filas"]) == 38 and all(len(f) == 38 for f in t["filas"])  # 19 indicadores × 2
    a, b = t["filas"][0], t["filas"][1]
    assert b[:24] == [None] * 24 and a[24] == "A" and b[24] == "B"
    por = {f[16]: f for f in t["filas"][::2]}
    assert por["410"][22] == 9.99 and por["410"][23] == 99.9  # alcanzada y avance/programado
    assert por["512"][22] == 2140 and por["512"][23] == 53.5
    assert t["titulo"].endswith("INDICADORES DE RESULTADOS")
    r = stats(m, u, "exportar/cuenta-publica", anio=2025, centro_gestor_id=ctx.cg["id"], programa_id=ctx.pid)
    from io import BytesIO

    from openpyxl import load_workbook
    ws = load_workbook(BytesIO(r.content)).active
    assert ws.max_column == 38 and ws.max_row == 3 + 38
    assert {str(x) for x in ws.merged_cells.ranges} >= {"A4:A5", "X4:X5"}  # 24 columnas combinadas por indicador


def test_exportaciones_sin_datos_traen_encabezados_y_programa_de_otro_centro_es_422(m):
    ctx = Ctx(m)
    u = usuario_con(m, [ctx.pid], "info1", tipo="informes")
    for ruta, n in (("cuenta-publica", 38), ("transparencia", 26)):
        t = stats(m, u, ruta, anio=2030, centro_gestor_id=ctx.cg["id"], programa_id=ctx.pid).json()
        assert len(t["encabezados"]) == n and t["filas"] == []
        r = stats(m, u, f"exportar/{ruta}", anio=2030, centro_gestor_id=ctx.cg["id"], programa_id=ctx.pid)
        assert r.status_code == 200 and len(r.content) > 0
    otro_cg = m.post(m.admin, "/api/centros-gestores", {"clave": "Z", "nombre": "Otro"}).json()
    r = stats(m, u, "transparencia", anio=2030, centro_gestor_id=otro_cg["id"], programa_id=ctx.pid)
    assert r.status_code == 422


def test_tipos_sin_acceso_reciben_403(m, eco):
    _, _ = eco
    ctx = Ctx(m, "X")
    pad = usuario_con(m, [ctx.pid], "pad1", tipo="padron")
    assert stats(m, pad, "dependencias", anio=2025).status_code == 403
    pres = usuario_con(m, [ctx.pid], "pres1", tipo="presupuestacion")
    assert stats(m, pres, "dependencias", anio=2025).status_code == 200  # Dependencias sí
    assert stats(m, pres, "ejes", anio=2025).status_code == 403  # Ejes solo informes/alcalde/admin


def test_programa_sin_subtema_cae_en_sin_eje_y_el_total_no_cambia(m):
    ctx = Ctx(m)
    cargar_2025(ctx)  # el programa de Ctx no tiene subtema
    u = usuario_con(m, [ctx.pid], "info1", tipo="informes")
    g = stats(m, u, "ejes", anio=2025).json()["grupos"]
    assert [(x["nombre"], x["total"]) for x in g] == [("Sin eje", 19)]


@pytest.mark.parametrize("tipo", ["administrador", "alcalde"])
def test_administrador_y_alcalde_ven_todos_los_programas_como_en_programas_visibles(m, tipo):
    """Misma regla de alcance que las demás fases (`programas.visibles`): sin asignaciones, ven todo el
    municipio en reportes, detalle, selectores y exportaciones; un tipo normal sin asignar no ve nada."""
    a, b = Ctx(m, "A"), Ctx(m, "B")
    cargar_2025(a)
    for ind in datos.INDICADORES[:6]:
        _crear(b, ind)
    if tipo == "administrador":
        c = m.admin  # el administrador del municipio, sin ninguna fila en usuario_programa
    else:
        m.usuario("alc1", "alcalde")
        c = m.cliente("alc1", "pw")
    g = stats(m, c, "dependencias", anio=2025, tipo_cumplimiento="co_ce").json()["grupos"]
    assert sorted(x["id"] for x in g) == sorted([a.cg["id"], b.cg["id"]]) and totales(g)["total"] == 19 + 6
    assert len(stats(m, c, "indicadores", anio=2025).json()["indicadores"]) == 25
    op = stats(m, c, "opciones").json()
    assert {p["id"] for p in op["programas"]} == {a.pid, b.pid} and len(op["centros_gestores"]) == 2
    for ctx in (a, b):  # exportar un programa que no tiene asignado
        r = stats(m, c, "exportar/cuenta-publica", anio=2025, centro_gestor_id=ctx.cg["id"], programa_id=ctx.pid)
        assert r.status_code == 200
    m.usuario("normal1", "informes")
    n = stats(m, m.cliente("normal1", "pw"), "dependencias", anio=2025).json()["grupos"]
    assert n == []


# =========================================================== campos de la ficha en los exports (indicador 411, 2025)
def _indicador_411(m, db):
    """El 411 (Propósito) del programa 1014 con los datos de la referencia: A/B de 2025, meta 15% (texto), año base 2024
    con su resultado programado 15, y medios de verificación. Su ID real (411) se fija como lo hace el seed."""
    from sqlalchemy import select

    from app.models import Indicador
    ctx = Ctx(m)
    d = next(i for i in datos.INDICADORES if i["id"] == 411)
    cuerpo = {"mir": {"medios_verificacion": "REGISTROS DE LA DIRECCIÓN DE DESARROLLO ECONÓMICO."},
              "ficha": {"tipo": "estrategico", "nombre": d["nombre"], "interpretacion": "Mide la población atendida", "dimension": "eficacia",
                        "frecuencia_id": ctx.frec, "unidad_medida": "PORCENTAJE", "algoritmo": d["algoritmo"],
                        "unidad_a": "pers", "unidad_b": "pers", "descripcion_a": "PERSONAS ATENDIDAS LABORALMENTE.",
                        "descripcion_b": "TOTAL DE PERSONAS SIN EMPLEO ECONÓMICAMENTE ACTIVOS DEL MUNICIPIO."},
              "metas": {"anio_base": 2024, "meta_administracion": d["meta_texto"], "anuales": [
                  {"anio": 2024, "valor_a_programado": 15, "valor_b_programado": 100},
                  {"anio": 2025, "valor_a_programado": d["meta_a"], "valor_b_programado": d["meta_b"], "es_ejercicio_fiscal": True}]},
              "rangos": datos.rangos_de(d)}
    r = m.post(m.admin, f"/api/elementos-matriz/{ctx.mat['proposito']['id']}/indicadores", cuerpo)
    assert r.status_code == 201, r.text
    pares = [{"mes": k, "valor_a": a, "valor_b": b} for k, (a, b) in enumerate(zip(d["A"], d["B"]), 1) if a is not None or b is not None]
    assert ctx.put(r.json(), pares, anio=2025).status_code == 200
    ind = db.scalar(select(Indicador).where(Indicador.nombre == d["nombre"]))
    ind.id_numerico = 411
    db.commit()
    return ctx, usuario_con(m, [ctx.pid], "info1", tipo="informes")


def test_transparencia_indicador_411_2025_con_los_campos_de_la_ficha(m, db):
    ctx, u = _indicador_411(m, db)
    t = stats(m, u, "transparencia", anio=2025, centro_gestor_id=ctx.cg["id"], programa_id=ctx.pid).json()
    assert len(t["filas"]) == 1
    fila = dict(zip(t["encabezados"], t["filas"][0]))
    assert fila["ID del indicador"] == 411
    assert fila["Año línea base"] == 2024 and fila["Valor línea base"] == 15  # resultado programado del año base
    assert fila["Metas programadas del año en análisis"] == 15
    assert fila["Descripción de la meta programada"] == "15% PERSONAS ATENDIDAS LABORALMENTE."
    assert fila["Avance de las metas"] == 7.98
    assert fila["Fuente de información"] == "REGISTROS DE LA DIRECCIÓN DE DESARROLLO ECONÓMICO."  # = medios de verificación
    assert fila["Definición del indicador"] == "Mide la población atendida"  # = interpretación (PENDIENTE de verificación)
    assert fila["Método de cálculo"] == ("(A: PERSONAS ATENDIDAS LABORALMENTE. / B: TOTAL DE PERSONAS SIN EMPLEO "
                                         "ECONÓMICAMENTE ACTIVOS DEL MUNICIPIO.) * 100")
    assert fila["Algoritmo"] == "(A / B) * 100" and fila["Nivel de la MIR"] == "Proposito"


def test_cuenta_publica_indicador_411_2025_con_id_formula_y_meta_en_texto(m, db):
    ctx, u = _indicador_411(m, db)
    t = stats(m, u, "cuenta-publica", anio=2025, centro_gestor_id=ctx.cg["id"], programa_id=ctx.pid).json()
    assert len(t["filas"]) == 2  # una fila por variable (A y B)
    a = dict(zip(t["encabezados"], t["filas"][0]))
    assert a["ID del indicador"] == 411
    assert a["Descripción de variables de la fórmula"].startswith("(A: PERSONAS ATENDIDAS LABORALMENTE. / B: TOTAL DE PERSONAS SIN EMPLEO")
    assert a["Meta del indicador programada"] == "15% PERSONAS ATENDIDAS LABORALMENTE."  # texto, no el número
    assert a["Meta del indicador alcanzada"] == 7.98 and a["Avance / Programado"] == 53.2


# =========================================================== formato de los exports y saltos de línea
def _celdas_xlsx(r):
    from io import BytesIO

    from openpyxl import load_workbook
    return load_workbook(BytesIO(r.content)).active


def test_xlsx_meta_alcanzada_avance_y_avance_de_las_metas_son_numericos_con_formato_0_00(m, db):
    ctx, u = _indicador_411(m, db)
    q = dict(anio=2025, centro_gestor_id=ctx.cg["id"], programa_id=ctx.pid)
    ws = _celdas_xlsx(stats(m, u, "exportar/cuenta-publica", **q))
    encab = {c.value: c.column for c in ws[3]}
    for nombre in ("Meta del indicador alcanzada", "Avance / Programado"):
        c = ws.cell(4, encab[nombre])  # fila A del 411 (las 24 primeras columnas están combinadas con la fila B)
        assert isinstance(c.value, (int, float)) and c.data_type == "n" and c.number_format == "0.00", nombre
    assert ws.cell(4, encab["Meta del indicador alcanzada"]).value == 7.98 and ws.cell(4, encab["Avance / Programado"]).value == 53.2
    assert ws.cell(4, encab["ID del indicador"]).number_format == "General"  # el formato no se extiende a otras columnas
    ws = _celdas_xlsx(stats(m, u, "exportar/transparencia", **q))
    encab = {c.value: c.column for c in ws[3]}
    c = ws.cell(4, encab["Avance de las metas"])
    assert c.value == 7.98 and c.data_type == "n" and c.number_format == "0.00"


def test_el_export_conserva_los_saltos_de_linea_del_texto_capturado(m, db):
    """Resumen narrativo y descripción de variables con saltos de línea (y líneas en blanco): el export los deja tal cual."""
    ctx = Ctx(m)
    resumen = "LINEA 1 DEL RESUMEN\nLINEA 2\n\nLINEA 4 TRAS UNA LINEA EN BLANCO"
    desc_a = "PERSONAS ATENDIDAS\nLABORALMENTE."
    desc_b = "TOTAL DE PERSONAS\n\nSIN EMPLEO."
    cuerpo = {"mir": {"resumen_narrativo": resumen},
              "ficha": {"tipo": "estrategico", "nombre": "Ind con saltos", "dimension": "eficacia", "frecuencia_id": ctx.frec,
                        "algoritmo": "a_sobre_b_pct", "descripcion_a": desc_a, "descripcion_b": desc_b},
              "metas": {"anuales": [{"anio": 2025, "valor_a_programado": 15, "valor_b_programado": 100}]}, "rangos": {}}
    r = m.post(m.admin, f"/api/elementos-matriz/{ctx.mat['proposito']['id']}/indicadores", cuerpo)
    assert r.status_code == 201, r.text
    assert ctx.put(r.json(), [{"mes": 1, "valor_a": 10, "valor_b": 100}], anio=2025).status_code == 200
    u = usuario_con(m, [ctx.pid], "info1", tipo="informes")
    q = dict(anio=2025, centro_gestor_id=ctx.cg["id"], programa_id=ctx.pid)
    formula = f"(A: {desc_a} / B: {desc_b}) * 100"

    # vista previa (JSON) y .xlsx de Cuenta Pública
    t = stats(m, u, "cuenta-publica", **q).json()
    fila = dict(zip(t["encabezados"], t["filas"][0]))
    assert fila["Descripción del resumen narrativo (FIN, Propósito, Componentes y Actividades)"] == resumen
    assert fila["Descripción de variables de la fórmula"] == formula
    ws = _celdas_xlsx(stats(m, u, "exportar/cuenta-publica", **q))
    encab = {c.value: c.column for c in ws[3]}
    assert ws.cell(4, encab["Descripción del resumen narrativo (FIN, Propósito, Componentes y Actividades)"]).value == resumen
    assert ws.cell(4, encab["Descripción de variables de la fórmula"]).value == formula
    # Transparencia: Objetivo institucional (resumen) y Método de cálculo
    t = stats(m, u, "transparencia", **q).json()
    fila = dict(zip(t["encabezados"], t["filas"][0]))
    assert fila["Objetivo institucional (Resumen narrativo)"] == resumen and fila["Método de cálculo"] == formula
    ws = _celdas_xlsx(stats(m, u, "exportar/transparencia", **q))
    encab = {c.value: c.column for c in ws[3]}
    assert ws.cell(4, encab["Objetivo institucional (Resumen narrativo)"]).value == resumen
    assert ws.cell(4, encab["Método de cálculo"]).value == formula
