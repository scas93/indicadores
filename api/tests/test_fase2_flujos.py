"""Fase 2 — MIR vía API: casos 1–9 de aceptación, árbol, matriz y cascada.
El caso 10 (estructura de los PDF contra el sistema de referencia) es verificación manual."""
import uuid
from datetime import date

import pytest
from sqlalchemy import select

from app.main import app
from app.models import (AvanceMensual, Bitacora, ElementoMatriz, Indicador, MetaAnual)
from app.routers.mir import hoy_actual

from .test_fase1_flujos import EJ, Mun, m  # noqa: F401  (fixture `m`)

HOY = date(2026, 10, 3)
RANGOS = {"verde": {"desde": 8.1, "hasta": 10}, "amarillo": {"desde": 6.1, "hasta": 8},
          "rojo": {"desde": -50, "hasta": 6}}


@pytest.fixture(autouse=True)
def hoy_fijo():
    app.dependency_overrides[hoy_actual] = lambda: HOY
    yield
    app.dependency_overrides.pop(hoy_actual, None)


class Ctx:
    """Un programa con su matriz ya creada y una frecuencia."""

    def __init__(self, m: Mun, sufijo=""):
        self.m = m
        cg, *_ = m.planeacion(sufijo)
        self.cg = cg
        self.prog = m.programa("P" + sufijo, cg)
        self.pid = self.prog["id"]
        self.frec = m.get(m.admin, "/api/frecuencias").json()[0]["id"]
        self.mat = m.get(m.admin, f"/api/programas/{self.pid}/matriz").json()

    def nuevo_indicador(self, elemento=None, algoritmo="a_sobre_b_pct", anuales=None, rangos=RANGOS, **ficha):
        elemento = elemento or self.mat["fin"]["id"]
        body = {"ficha": {"tipo": "estrategico", "nombre": "Indicador", "dimension": "eficacia",
                          "frecuencia_id": self.frec, "algoritmo": algoritmo, "unidad_a": "pers", "unidad_b": "pers",
                          **ficha},
                "metas": {"anio_base": 2023, "meta_administracion": 10,
                          "anuales": anuales if anuales is not None else [
                              {"anio": 2024, "valor_a_programado": 10, "valor_b_programado": 100,
                               "es_ejercicio_fiscal": True}]},
                "rangos": rangos}
        r = self.m.post(self.m.admin, f"/api/elementos-matriz/{elemento}/indicadores", body)
        assert r.status_code == 201, r.text
        return r.json()

    def put(self, ind, meses, anio=2024, c=None):
        return self.m.c_put(c or self.m.admin, ind["id"], anio, meses)


def _put(self, c, ind_id, anio, meses):
    return c.put(f"/api/indicadores/{ind_id}/avances", params={"anio": anio}, headers=self.h, json={"meses": meses})


Mun.c_put = _put


def serie(a, b=None, meses=range(1, 13)):
    return [{"mes": k, "valor_a": a, "valor_b": b} for k in meses]


@pytest.fixture()
def ctx(m):
    return Ctx(m)


def usuario_con(m, p_ids, usuario="u1", tipo="indicadores"):
    u = m.usuario(usuario, tipo)
    m.post(m.admin, "/api/usuarios/matriz", {"altas": [{"usuario_id": u["id"], "programa_id": p} for p in p_ids]})
    return m.cliente(usuario, "pw")


# --- matriz base --------------------------------------------------------------------------
def test_primera_entrada_crea_fin_y_proposito_vacios_y_no_duplica(m, ctx):
    assert ctx.mat["fin"]["nivel"] == "fin" and ctx.mat["proposito"]["nivel"] == "proposito"
    assert ctx.mat["fin"]["resumen_narrativo"] == "" and ctx.mat["componentes"] == []
    again = m.get(m.admin, f"/api/programas/{ctx.pid}/matriz").json()
    assert again["fin"]["id"] == ctx.mat["fin"]["id"] and again["proposito"]["id"] == ctx.mat["proposito"]["id"]
    assert ctx.mat["programa"]["centro_gestor"].startswith("CG")


def test_fin_y_proposito_no_se_eliminan_y_no_hay_segundo_alta(m, ctx, db):
    for k in ("fin", "proposito"):
        r = m.admin.delete(f"/api/elementos-matriz/{ctx.mat[k]['id']}", headers=m.h)
        assert r.status_code == 409 and r.json()["codigo"] == "NIVEL_NO_ELIMINABLE"
    # el índice único parcial lo respalda aunque se intente por debajo del servicio
    from app.services import mir as svc
    from app.errors import ApiError
    from app.models import Programa
    with pytest.raises(ApiError) as e:
        svc.alta_nivel_unico(db, db.get(Programa, uuid.UUID(ctx.pid)), "fin")
    assert e.value.codigo == "NIVEL_UNICO"


def test_componentes_y_actividades_numeran_y_se_editan(m, ctx):
    c1 = m.post(m.admin, f"/api/programas/{ctx.pid}/matriz/componentes", {"resumen_narrativo": "C1"}).json()
    c2 = m.post(m.admin, f"/api/programas/{ctx.pid}/matriz/componentes", {}).json()
    a1 = m.post(m.admin, f"/api/elementos-matriz/{c1['id']}/actividades", {"resumen_narrativo": "A"}).json()
    a2 = m.post(m.admin, f"/api/elementos-matriz/{c1['id']}/actividades", {}).json()
    assert (c1["numero"], c2["numero"], a1["numero"], a2["numero"]) == ("1", "2", "1.1", "1.2")
    r = m.post(m.admin, f"/api/elementos-matriz/{ctx.mat['fin']['id']}/actividades", {})
    assert r.status_code == 422  # solo cuelgan de un componente
    r = m.patch(m.admin, f"/api/elementos-matriz/{a1['id']}", {"supuestos": "S", "evidencia": "E"})
    assert r.json()["supuestos"] == "S" and r.json()["evidencia"] == "E"
    mat = m.get(m.admin, f"/api/programas/{ctx.pid}/matriz").json()
    assert [x["numero"] for x in mat["componentes"][0]["actividades"]] == ["1.1", "1.2"]


def test_eliminar_componente_cascada_con_bitacora_y_renumera(m, ctx, db):
    c1 = m.post(m.admin, f"/api/programas/{ctx.pid}/matriz/componentes", {}).json()
    c2 = m.post(m.admin, f"/api/programas/{ctx.pid}/matriz/componentes", {}).json()
    act = m.post(m.admin, f"/api/elementos-matriz/{c1['id']}/actividades", {}).json()
    i1 = ctx.nuevo_indicador(c1["id"])
    i2 = ctx.nuevo_indicador(act["id"])
    ctx.put(i1, serie(1, 10, [1, 2]))
    r = m.admin.delete(f"/api/elementos-matriz/{c1['id']}", headers=m.h)
    assert r.status_code == 200 and r.json()["elementos_eliminados"] == 2 and r.json()["indicadores_eliminados"] == 2
    assert db.scalars(select(Indicador)).all() == []
    assert db.scalars(select(AvanceMensual)).all() == []
    assert db.scalars(select(MetaAnual)).all() == []
    mat = m.get(m.admin, f"/api/programas/{ctx.pid}/matriz").json()
    assert [c["numero"] for c in mat["componentes"]] == ["1"] and mat["componentes"][0]["id"] == c2["id"]
    b = db.scalar(select(Bitacora).where(Bitacora.accion == "matriz.componente.eliminar"))
    assert b is not None and b.detalle["indicadores_eliminados"] == 2


# --- caso 1 y 2: paridad (datos sintéticos, pendiente del dato real) ---------------------------------
def test_caso1_y_2_cumplimiento_2024_sintetico_1_18_y_color(m, ctx):
    """PENDIENTE de verificación con el dato real de "Fortalecimiento del empleo": A/B sintéticos."""
    ind = ctx.nuevo_indicador()
    meses = [{"mes": 1, "valor_a": 3, "valor_b": 250}, {"mes": 2, "valor_a": 3, "valor_b": 250},
             {"mes": 3, "valor_a": 3, "valor_b": 250}, {"mes": 4, "valor_a": 2.8, "valor_b": 250}]
    r = ctx.put(ind, meses)
    assert r.status_code == 200 and r.json()["guardados"] == [1, 2, 3, 4]
    g = m.get(m.admin, f"/api/indicadores/{ind['id']}/avances", params={"anio": 2024}).json()
    assert g["sumatoria_a"] == pytest.approx(11.8) and g["sumatoria_b"] == 1000
    assert g["cumplimiento"] == 1.18 and g["color"] == "rojo"  # rango real rojo: -50 a 6
    # el cumplimiento nunca se guarda: no hay ninguna columna que lo contenga
    assert not hasattr(AvanceMensual, "cumplimiento") and not hasattr(Indicador, "cumplimiento")


# --- caso 3: solo A -----------------------------------------------------------------------------------
def test_caso3_solo_a_bloquea_b_en_servidor_y_la_oculta_en_las_respuestas(m, ctx):
    ind = ctx.nuevo_indicador(algoritmo="a", unidad_b="no debe guardarse",
                              anuales=[{"anio": 2024, "valor_a_programado": 9, "es_ejercicio_fiscal": True}])
    assert ind["ficha"]["unidad_b"] is None
    r = ctx.put(ind, serie(1, 5, [1]))
    assert r.status_code == 422 and r.json()["codigo"] == "VARIABLE_B_BLOQUEADA"
    assert ctx.put(ind, serie(1, None, [1, 2])).status_code == 200
    r = m.post(m.admin, f"/api/elementos-matriz/{ctx.mat['fin']['id']}/indicadores", {
        "ficha": {"tipo": "gestion", "nombre": "x", "frecuencia_id": ctx.frec, "algoritmo": "a"},
        "metas": {"anuales": [{"anio": 2024, "valor_a_programado": 1, "valor_b_programado": 3}]}})
    assert r.status_code == 422 and r.json()["codigo"] == "VARIABLE_B_BLOQUEADA"
    g = m.get(m.admin, f"/api/indicadores/{ind['id']}/avances", params={"anio": 2024}).json()
    assert g["indicador"]["usa_b"] is False and g["sumatoria_b"] is None
    assert all(x["valor_b"] is None for x in g["meses"]) and g["meta"]["valor_b_programado"] is None


def test_cambiar_a_solo_a_conserva_b_guardada_pero_la_ignora(m, ctx, db):
    ind = ctx.nuevo_indicador()
    ctx.put(ind, serie(5, 100, [1, 2]))
    r = m.patch(m.admin, f"/api/indicadores/{ind['id']}", {"ficha": {"algoritmo": "a"}})
    assert r.status_code == 200 and r.json()["ficha"]["unidad_b"] is None
    assert r.json()["metas"]["anuales"][0]["valor_b_programado"] is None
    g = m.get(m.admin, f"/api/indicadores/{ind['id']}/avances", params={"anio": 2024}).json()
    assert g["cumplimiento"] == 10.0 and g["sumatoria_b"] is None   # solo A = sumatoria A
    assert all(f.valor_b == 100 for f in db.scalars(select(AvanceMensual)))  # B sigue guardada
    assert db.scalar(select(MetaAnual)).valor_b_programado == 100


# --- caso 4: metas sin algoritmo/frecuencia -----------------------------------------------------------
def test_caso4_metas_sin_algoritmo_o_frecuencia_422_dice_que_falta(m, ctx):
    url = f"/api/elementos-matriz/{ctx.mat['fin']['id']}/indicadores"
    meta = {"anuales": [{"anio": 2024, "valor_a_programado": 1, "valor_b_programado": 1}]}
    r = m.post(m.admin, url, {"ficha": {"tipo": "gestion", "nombre": "x"}, "metas": meta})
    assert r.status_code == 422 and set(r.json()["campos"]) == {"algoritmo", "frecuencia_id"}
    r = m.post(m.admin, url, {"ficha": {"tipo": "gestion", "nombre": "x", "algoritmo": "a_sobre_b"}, "metas": meta})
    assert set(r.json()["campos"]) == {"frecuencia_id"} and "la frecuencia" in r.json()["mensaje"]
    # sin metas sí se puede guardar la ficha incompleta, y luego PATCH de metas vuelve a exigirlo
    ok = m.post(m.admin, url, {"ficha": {"tipo": "gestion", "nombre": "x"}})
    assert ok.status_code == 201
    r = m.patch(m.admin, f"/api/indicadores/{ok.json()['id']}", {"metas": meta})
    assert r.status_code == 422 and r.json()["codigo"] == "FICHA_INCOMPLETA"


def test_rangos_traslapados_se_rechazan_en_servidor(m, ctx):
    ind = ctx.nuevo_indicador()
    bad = {"verde": {"desde": 5, "hasta": 10}, "amarillo": {"desde": 6, "hasta": 8}}
    r = m.patch(m.admin, f"/api/indicadores/{ind['id']}", {"rangos": bad})
    assert r.status_code == 422 and "rango_amarillo" in r.json()["campos"]
    ok = {"verde": {"desde": 8.1, "hasta": 10}, "amarillo": {"desde": None, "hasta": None}}
    assert m.patch(m.admin, f"/api/indicadores/{ind['id']}", {"rangos": ok}).status_code == 200


def test_alta_de_indicador_completo_en_una_operacion_y_edicion_por_partes(m, ctx):
    ind = ctx.nuevo_indicador(prioritario=True, interpretacion="Mide X", unidad_medida="Porcentaje")
    assert ind["ficha"]["prioritario"] and ind["metas"]["anuales"][0]["es_ejercicio_fiscal"]
    assert ind["rangos"]["verde"] == {"desde": 8.1, "hasta": 10} and ind["metas"]["meta_administracion"] == 10
    r = m.patch(m.admin, f"/api/indicadores/{ind['id']}", {
        "mir": {"resumen_narrativo": "Contribuir a…", "medios_verificacion": "INEGI"},
        "metas": {"anuales": [{"anio": 2024, "valor_a_programado": 1}, {"anio": 2025, "valor_a_programado": 2}]}})
    assert r.status_code == 200 and [x["anio"] for x in r.json()["metas"]["anuales"]] == [2024, 2025]
    assert r.json()["ficha"]["nombre"] == "Indicador"  # lo no enviado no se toca
    mat = m.get(m.admin, f"/api/programas/{ctx.pid}/matriz").json()
    assert mat["fin"]["resumen_narrativo"] == "Contribuir a…" and len(mat["fin"]["indicadores"]) == 1
    dos = m.post(m.admin, f"/api/elementos-matriz/{ctx.mat['fin']['id']}/indicadores",
                 {"ficha": {"tipo": "gestion", "nombre": "Segundo"}})
    assert dos.status_code == 201  # un elemento puede tener más de un indicador


# --- caso 5: meses activos y tolerancia ----------------------------------------------------------------
def test_caso5_mes_fuera_de_activos_y_tolerancia_rechazado_dentro_aceptado(m, ctx):
    ind = ctx.nuevo_indicador()
    cfg = m.patch(m.admin, "/api/config", {"meses_avance_activos": [3, 6], "tolerancia_semaforo": 3})
    assert cfg.status_code == 200, cfg.text
    meses = [{"mes": 3, "valor_a": 1, "valor_b": 1},   # activo
             {"mes": 9, "valor_a": 2, "valor_b": 2},   # terminó 30/09, hoy 03/10, tolerancia 3 -> aceptado
             {"mes": 2, "valor_a": 3, "valor_b": 3}]   # fuera -> rechazado
    r = ctx.put(ind, meses, 2026)
    assert r.status_code == 200
    assert r.json()["guardados"] == [3, 9]
    assert [x["mes"] for x in r.json()["rechazados"]] == [2] and r.json()["rechazados"][0]["codigo"] == "MES_NO_CAPTURABLE"
    cap = {x["mes"]: x["capturable"] for x in r.json()["rejilla"]["meses"]}
    assert cap[3] and cap[9] and not cap[2] and not cap[1]
    # si TODOS los cambios son rechazables: 422 con detalle por mes
    r = ctx.put(ind, [{"mes": 1, "valor_a": 1, "valor_b": 1}], 2026)
    assert r.status_code == 422 and r.json()["codigo"] == "MESES_NO_CAPTURABLES" and "mes_1" in r.json()["campos"]
    # tolerancia 2: septiembre ya no
    m.patch(m.admin, "/api/config", {"tolerancia_semaforo": 2})
    assert ctx.put(ind, [{"mes": 9, "valor_a": 5, "valor_b": 5}], 2026).status_code == 422


def test_sin_seleccion_en_configuracion_son_12_meses_activos(m, ctx):
    ind = ctx.nuevo_indicador()
    r = ctx.put(ind, serie(1, 1))
    assert r.status_code == 200 and len(r.json()["guardados"]) == 12


# --- caso 6 y 7: gris -------------------------------------------------------------------------------
def test_caso6_sin_meses_capturados_gris_y_caso7_sumatoria_b_cero_null_gris_sin_500(m, ctx):
    ind = ctx.nuevo_indicador()
    g = m.get(m.admin, f"/api/indicadores/{ind['id']}/avances", params={"anio": 2024}).json()
    assert g["color"] == "gris" and g["cumplimiento"] is None and g["sumatoria_a"] is None
    r = ctx.put(ind, [{"mes": 1, "valor_a": 5, "valor_b": 0}, {"mes": 2, "valor_a": 2, "valor_b": 0}])
    assert r.status_code == 200
    g = m.get(m.admin, f"/api/indicadores/{ind['id']}/avances", params={"anio": 2024})
    assert g.status_code == 200 and g.json()["cumplimiento"] is None and g.json()["color"] == "gris"
    lista = m.get(m.admin, f"/api/programas/{ctx.pid}/captura-avances").json()["indicadores"]
    assert lista[0]["color"] == "gris" and lista[0]["cumplimiento"] is None


def test_hay_resultado_pero_fuera_de_rangos_es_sin_color_no_gris(m, ctx):
    ind = ctx.nuevo_indicador(algoritmo="a", anuales=[{"anio": 2024, "valor_a_programado": 1}])
    ctx.put(ind, [{"mes": 1, "valor_a": 50, "valor_b": None}])
    g = m.get(m.admin, f"/api/indicadores/{ind['id']}/avances", params={"anio": 2024}).json()
    assert g["cumplimiento"] == 50.0 and g["color"] == "sin_color"


def test_borrar_los_dos_valores_de_un_mes_lo_deja_sin_captura(m, ctx, db):
    ind = ctx.nuevo_indicador(algoritmo="a_sobre_b")
    ctx.put(ind, serie(2, 4, [1, 2]))
    ctx.put(ind, [{"mes": 2, "valor_a": None, "valor_b": None}])
    assert [f.mes for f in db.scalars(select(AvanceMensual))] == [1]
    g = m.get(m.admin, f"/api/indicadores/{ind['id']}/avances", params={"anio": 2024}).json()
    assert g["cumplimiento"] == 0.5  # el mes vacío no cuenta ni como cero


# --- caso 8 y 9: aislamiento y 403 ---------------------------------------------------------------------
def test_caso8_dos_programas_aislamiento_total(m):
    a, b = Ctx(m, "A"), Ctx(m, "B")
    ia = a.nuevo_indicador(nombre="Solo de A")
    a.put(ia, serie(1, 2, [1]))
    m.post(m.admin, f"/api/programas/{a.pid}/arbol/causas", {"texto_causa": "causa A"})
    m.post(m.admin, f"/api/programas/{a.pid}/matriz/componentes", {"resumen_narrativo": "comp A"})
    mb = m.get(m.admin, f"/api/programas/{b.pid}/matriz").json()
    assert mb["componentes"] == [] and mb["fin"]["indicadores"] == [] and mb["fin"]["id"] != a.mat["fin"]["id"]
    assert m.get(m.admin, f"/api/programas/{b.pid}/arbol").json()["causas"] == []
    assert m.get(m.admin, f"/api/programas/{b.pid}/captura-avances").json()["indicadores"] == []


def test_caso9_usuario_sin_el_programa_recibe_403_aunque_sea_del_mismo_municipio(m):
    a, b = Ctx(m, "A"), Ctx(m, "B")
    ia = a.nuevo_indicador()
    u = usuario_con(m, [a.pid])
    # su programa sí
    assert m.get(u, f"/api/programas/{a.pid}/matriz").status_code == 200
    # el ajeno, en todas las rutas
    rutas = [("get", f"/api/programas/{b.pid}/matriz"), ("get", f"/api/programas/{b.pid}/arbol"),
             ("get", f"/api/programas/{b.pid}/captura-avances")]
    for metodo, ruta in rutas:
        r = getattr(u, metodo)(ruta, headers=m.h)
        assert r.status_code == 403 and r.json()["codigo"] == "PROGRAMA_NO_ASIGNADO", ruta
    assert m.post(u, f"/api/programas/{b.pid}/matriz/componentes", {}).status_code == 403
    assert m.post(u, f"/api/programas/{b.pid}/arbol/causas", {"texto_causa": "x"}).status_code == 403
    fin_b = b.mat["fin"]["id"]
    assert m.patch(u, f"/api/elementos-matriz/{fin_b}", {"supuestos": "x"}).status_code == 403
    assert m.post(u, f"/api/elementos-matriz/{fin_b}/indicadores", {"ficha": {"tipo": "gestion", "nombre": "x"}}).status_code == 403
    ib = b.nuevo_indicador()
    assert m.patch(u, f"/api/indicadores/{ib['id']}", {"ficha": {"nombre": "x"}}).status_code == 403
    assert m.get(u, f"/api/indicadores/{ib['id']}/avances").status_code == 403
    assert m.c_put(u, ib["id"], 2024, serie(1, 1, [1])).status_code == 403
    assert u.delete(f"/api/elementos-matriz/{fin_b}", headers=m.h).status_code == 403
    # y el suyo puede capturar
    assert m.c_put(u, ia["id"], 2024, serie(1, 1, [1])).status_code == 200


def test_programa_de_otro_municipio_no_existe_para_mi(admin, m):
    otro = Mun(admin, "otro")
    ajeno = Ctx(otro)
    assert m.get(m.admin, f"/api/programas/{ajeno.pid}/matriz").status_code == 404
    assert m.get(m.admin, f"/api/indicadores/{ajeno.nuevo_indicador()['id']}/avances").status_code == 404


def test_tipo_sin_modulo_inicio_recibe_403(m):
    c = m.cliente(m.usuario("pad", "padron")["usuario"], "pw")
    ctx = Ctx(m)
    assert m.get(c, f"/api/programas/{ctx.pid}/matriz").status_code == 403


# --- árbol ----------------------------------------------------------------------------------------------
def test_arbol_dos_niveles_numeracion_espejo_y_borrado_en_cascada(m, ctx):
    p = ctx.pid
    r1 = m.post(m.admin, f"/api/programas/{p}/arbol/causas", {"texto_causa": "C1", "texto_medio": "M1"}).json()
    r2 = m.post(m.admin, f"/api/programas/{p}/arbol/causas", {"texto_causa": "C2", "texto_medio": "M2"}).json()
    s11 = m.post(m.admin, f"/api/programas/{p}/arbol/causas", {"padre_id": r1["id"], "texto_causa": "C1.1"}).json()
    m.post(m.admin, f"/api/programas/{p}/arbol/causas", {"padre_id": r1["id"], "texto_causa": "C1.2"})
    assert (r1["numero"], r2["numero"], s11["numero"]) == ("1", "2", "1.1")
    # 3er nivel y texto vacío
    assert m.post(m.admin, f"/api/programas/{p}/arbol/causas", {"padre_id": s11["id"], "texto_causa": "x"}).status_code == 422
    assert m.post(m.admin, f"/api/programas/{p}/arbol/causas", {"texto_causa": "  "}).status_code == 422
    e1 = m.post(m.admin, f"/api/programas/{p}/arbol/efectos", {"texto_efecto": "E1", "texto_fin": "F1"}).json()
    # el padre debe ser del mismo árbol (un id de causa no sirve como padre de efecto)
    assert m.post(m.admin, f"/api/programas/{p}/arbol/efectos", {"padre_id": r1["id"], "texto_efecto": "x"}).status_code == 422
    # causa y medio se editan juntos en un nodo
    r = m.patch(m.admin, f"/api/arbol-causa-medio/{r2['id']}", {"texto_causa": "C2b", "texto_medio": "M2b"})
    assert r.json()["texto_causa"] == "C2b" and r.json()["texto_medio"] == "M2b"
    m.patch(m.admin, f"/api/arbol-efecto-fin/{e1['id']}", {"texto_fin": "F1b"})
    m.admin.put(f"/api/programas/{p}/arbol/encabezado", headers=m.h, json={"problema": "Desempleo", "objetivo": "Empleo"})
    t = m.get(m.admin, f"/api/programas/{p}/arbol").json()
    assert t["encabezado"] == {"problema": "Desempleo", "objetivo": "Empleo"}
    assert [(n["numero"], len(n["hijos"])) for n in t["causas"]] == [("1", 2), ("2", 0)]
    assert t["efectos"][0]["texto_fin"] == "F1b" and t["efectos"][0]["texto_efecto"] == "E1"
    # borrar la causa 1 se lleva a sus hijos; la 2 pasa a ser la 1
    d = m.admin.delete(f"/api/arbol-causa-medio/{r1['id']}", headers=m.h)
    assert d.json() == {"eliminados": 3}
    t = m.get(m.admin, f"/api/programas/{p}/arbol").json()
    assert [(n["numero"], n["texto_causa"]) for n in t["causas"]] == [("1", "C2b")]
    assert m.admin.delete(f"/api/arbol-efecto-fin/{e1['id']}", headers=m.h).json() == {"eliminados": 1}


def test_vista_previa_calcula_sin_guardar_y_con_el_mismo_motor(m, ctx, db):
    ind = ctx.nuevo_indicador()
    meses = [{"mes": 1, "valor_a": 3, "valor_b": 250}, {"mes": 2, "valor_a": 8.8, "valor_b": 750}]
    r = m.post(m.admin, f"/api/indicadores/{ind['id']}/avances/calcular", {"meses": meses})
    assert r.status_code == 200 and r.json()["cumplimiento"] == 1.18 and r.json()["color"] == "rojo"
    assert db.scalars(select(AvanceMensual)).all() == []   # no guardó nada
    sin = m.post(m.admin, f"/api/indicadores/{ind['id']}/avances/calcular", {"meses": []}).json()
    assert sin["color"] == "gris" and sin["cumplimiento"] is None
    cero = m.post(m.admin, f"/api/indicadores/{ind['id']}/avances/calcular",
                  {"meses": [{"mes": 1, "valor_a": 1, "valor_b": 0}]}).json()
    assert cero["color"] == "gris" and cero["cumplimiento"] is None
