"""Seed de datos de prueba de Fase 3 (`seed_estadisticas.py`): idempotencia y que lo sembrado reproduce los
conteos verificados en la referencia. Fuera de la suite de reglas de negocio: es herramienta de staging."""
import html
import re
from pathlib import Path

import pytest
from sqlalchemy import func, select

import seed_estadisticas as seed
from app.models import (AvanceMensual, CentroGestor, ElementoMatriz, Eje, Indicador, MetaAnual, Programa, Usuario,
                        UsuarioPrograma)
from seed_data import economico_2025 as datos

from .test_fase1_flujos import m  # noqa: F401  (fixture `m`)

XLS = Path(__file__).parents[2] / "humanos/docs/referencias/indicadores_resultados.xls"
PW = "pw-demo-1"


def _cuentas(db):
    return {t.__name__: db.scalar(select(func.count()).select_from(t)) for t in
            (CentroGestor, Eje, Programa, ElementoMatriz, Indicador, MetaAnual, AvanceMensual, Usuario, UsuarioPrograma)}


def test_el_dataset_coincide_con_el_export_de_referencia():
    if not XLS.exists():
        pytest.skip("falta el .xls de referencia")
    celdas = lambda r: [re.sub(r"\s+", " ", html.unescape(re.sub("<[^>]+>", "", c))).strip()  # noqa: E731
                        for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", r, re.I | re.S)]
    filas = re.findall(r"<tr.*?</tr>", XLS.read_text(encoding="utf-8", errors="replace"), re.I | re.S)[3:]
    num = lambda x: None if x == "" else float(x)  # noqa: E731
    assert len(filas) == 2 * len(datos.INDICADORES)
    for ind, (fa, fb) in zip(datos.INDICADORES, zip(filas[::2], filas[1::2])):
        a, b = celdas(fa), celdas(fb)
        assert (a[15], a[16], a[17].lower()) == (ind["ref"], ind["nombre"], ind["nivel"])
        assert int(a[15]) == ind["id"] and a[20] == ind["meta_texto"], ind["ref"]
        assert a[25] == ind["unidad_a"], ind["ref"]
        assert float(a[22]) == ind["alcanzada"] and round(float(a[23]), 2) == ind["avance"], ind["ref"]
        assert [num(x) for x in a[26:]] == [None if x is None else float(x) for x in ind["A"]], ind["ref"]
        if ind["algoritmo"] != "a":
            assert [num(x) for x in b[2:]] == [None if x is None else float(x) for x in ind["B"]], ind["ref"]


def test_municipio_inexistente_falla_con_mensaje_claro(m, db):  # noqa: F811
    with pytest.raises(ValueError, match="No existe el municipio"):
        seed.sembrar(db, "no-existe", "informes1", PW)


def test_sembrar_es_idempotente_y_reproduce_los_conteos_de_la_referencia(m, db):  # noqa: F811
    r = seed.sembrar(db, m.slug, "informes1", PW)
    assert r["indicadores"] == 19
    primera = _cuentas(db)
    assert primera["Indicador"] == 19 and primera["Programa"] == 1 and primera["MetaAnual"] == 19
    assert primera["ElementoMatriz"] == 2 + 5 + 12 and primera["UsuarioPrograma"] == 1
    ids = {i.nombre: i.id_numerico for i in db.scalars(select(Indicador))}
    assert sorted(ids.values()) == sorted(i["id"] for i in datos.INDICADORES)  # los IDs reales: 410, 411, 512…
    i411 = db.scalar(select(Indicador).where(Indicador.id_numerico == 411))
    assert i411.meta_administracion == "15% PERSONAS ATENDIDAS LABORALMENTE." and i411.descripcion_b.startswith("TOTAL DE PERSONAS SIN EMPLEO")
    assert db.scalar(select(Programa.nombre)) == "FORTALECIMIENTO DEL EMPLEO Y LA GESTIÓN EMPRESARIAL"
    for _ in range(2):  # re-correr (y con otra contraseña) no duplica nada
        seed.sembrar(db, m.slug, "informes1", PW)
    assert _cuentas(db) == primera

    u = m.cliente("informes1", PW)
    for modo, esperado in datos.CONTEOS_2025.items():
        for ruta in ("dependencias", "ejes"):
            g = m.get(u, f"/api/estadisticas/{ruta}", params={"anio": 2025, "tipo_cumplimiento": modo}).json()["grupos"]
            assert len(g) == 1 and g[0]["nombre"] == "ECONÓMICO", (ruta, modo)
            assert {k: g[0][k] for k in esperado} == esperado, (ruta, modo)
    op = m.get(u, "/api/estadisticas/opciones").json()
    assert op["anios"] == [2025] and [p["clave"] for p in op["programas"]] == ["1014"]


def test_recorrer_de_nuevo_corrige_lo_editado_y_cambia_la_contrasena(m, db):  # noqa: F811
    seed.sembrar(db, m.slug, "informes1", PW)
    ind = db.scalar(select(Indicador).where(Indicador.nombre == "VARIACIÓN EN LA POBLACIÓN ECONÓMICAMENTE ACTIVO."))
    ind.rango_verde_desde = 0  # alguien lo editó
    db.commit()
    seed.sembrar(db, m.slug, "informes1", "otra-pw-2")
    db.refresh(ind)
    assert float(ind.rango_verde_desde) == 8.1
    assert m.cliente("informes1", "otra-pw-2") is not None
    with pytest.raises(ValueError, match="otro tipo"):
        seed.sembrar(db, m.slug, "admin1", PW)  # el administrador del municipio ya usa ese nombre


def test_el_seed_reasigna_los_ids_provisionales_y_respeta_el_consecutivo(m, db):  # noqa: F811
    """Staging: tras la migración los indicadores quedan 1..19; el seed los lleva a los IDs reales sin chocar,
    y un indicador nuevo sigue desde el máximo (ya no desde 19)."""
    seed.sembrar(db, m.slug, "informes1", PW)
    for k, i in enumerate(db.scalars(select(Indicador).order_by(Indicador.nombre)), 1):  # como los dejaría la migración
        i.id_numerico = 1000 + k
    db.commit()
    seed.sembrar(db, m.slug, "informes1", PW)
    assert sorted(i.id_numerico for i in db.scalars(select(Indicador))) == sorted(x["id"] for x in datos.INDICADORES)
    from app.services.mir import siguiente_id_numerico
    from app.tenancy import scope_session
    scope_session(db, db.scalar(select(Indicador.municipio_id)))
    assert siguiente_id_numerico(db) == max(x["id"] for x in datos.INDICADORES) + 1
    # un ID real ocupado por otro indicador ajeno al seed no se pisa en silencio
    otro = db.scalar(select(Indicador).where(Indicador.id_numerico == 410))
    otro.nombre = "AJENO"
    otro.id_numerico = 410
    db.commit()
    with pytest.raises(ValueError, match="ya lo usa otro indicador"):
        seed.sembrar(db, m.slug, "informes1", PW)


def test_cuenta_publica_del_seed_reproduce_id_formula_y_meta_del_export_de_referencia(m, db):  # noqa: F811
    """Los 19 indicadores: ID, "Descripción de variables de la fórmula" y "Meta del indicador programada" salen
    idénticos al export real del sistema de referencia."""
    if not XLS.exists():
        pytest.skip("falta el .xls de referencia")
    seed.sembrar(db, m.slug, "informes1", PW)
    u = m.cliente("informes1", PW)
    op = m.get(u, "/api/estadisticas/opciones").json()
    t = m.get(u, "/api/estadisticas/cuenta-publica", params={
        "anio": 2025, "centro_gestor_id": op["centros_gestores"][0]["id"], "programa_id": op["programas"][0]["id"]}).json()
    generado = {str(f[15]): (f[19], f[20]) for f in t["filas"][::2]}  # una fila por indicador (la A)
    celdas = lambda r: [re.sub(r"\s+", " ", html.unescape(re.sub("<[^>]+>", "", c))).strip()  # noqa: E731
                        for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", r, re.I | re.S)]
    filas = re.findall(r"<tr.*?</tr>", XLS.read_text(encoding="utf-8", errors="replace"), re.I | re.S)[3:]
    esperado = {celdas(f)[15]: (celdas(f)[19], celdas(f)[20]) for f in filas[::2]}
    assert generado == esperado and len(esperado) == 19
