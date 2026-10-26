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
