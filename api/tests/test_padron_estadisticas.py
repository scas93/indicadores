"""Fase 4.3a — Estadísticas del Padrón por API: conteo de capturas, alcance por programa, Concentrado y Comparativo."""
from datetime import date

from .test_fase5_catalogos import Pad, dos_programas, m, ok  # noqa: F401  (m es un fixture)

BASE = "padron/estadisticas"
ANIO = date.today().year


def _escenario(m):  # noqa: F811
    pa, pb = dos_programas(m)
    pad = Pad(m, [pa["id"]])
    est = next(e for e in pad.get("geo/estados").json() if e["por_defecto"])["id"]
    mu = ok(pad.post("geo/municipios", {"clave": "901", "nombre": "Muni", "estado_id": est}), 201)
    locs = [ok(pad.post("geo/localidades", {"clave": f"L{i}", "nombre": f"Loc{i}", "municipio_id": mu["id"]}), 201) for i in range(1, 7)]
    ap_a = ok(pad.post("apoyos", {"clave": "A", "nombre": "Despensa", "programa_id": pa["id"]}), 201)
    ap_b = ok(m.post(m.admin, "/api/apoyos", {"clave": "B", "nombre": "Becas", "programa_id": pb["id"]}), 201)
    col = ok(pad.post("geo/colonias", {"clave": "C1", "nombre": "Jardines", "estado_id": est, "municipio_id": mu["id"]}), 201)
    return pad, pa, pb, est, mu, locs, ap_a, ap_b, col


def _ben(pad, curp, loc, genero, edad, est, mu, **extra):
    nac = date(ANIO - edad, 1, 1).isoformat()
    return ok(pad.post("beneficiarios", {"curp": curp, "nombre": f"Nombre {curp}", "genero": genero, "fecha_nacimiento": nac,
                                         "estado_id": est, "municipio_id": mu["id"], "localidad_id": loc["id"], **extra}), 201)


def _cap(cli, m, b, prog, apoyo, fecha, **extra):  # noqa: F811
    return ok(m.post(cli, "/api/padron/capturas", {"beneficiario_id": b["id"], "programa_id": prog["id"], "apoyo_id": apoyo["id"],
                                                    "fecha_entrega": fecha, **extra}), 201)


def test_dashboard_cuenta_capturas_y_agrupa_sin_grupo(m):  # noqa: F811
    pad, pa, pb, est, mu, locs, ap_a, ap_b, col = _escenario(m)
    adulto = _ben(pad, "A1", locs[0], "F", 30, est, mu)
    bebe = _ben(pad, "B1", locs[1], "M", 1, est, mu)
    sin_fecha = ok(pad.post("beneficiarios", {"curp": "S1", "nombre": "Sin fecha"}), 201)
    hoy = date.today().isoformat()
    _cap(pad.c, m, adulto, pa, ap_a, hoy, cantidad=5)   # cantidad 5 sigue siendo UNA captura
    _cap(pad.c, m, adulto, pa, ap_a, hoy)
    _cap(pad.c, m, bebe, pa, ap_a, hoy)
    _cap(pad.c, m, sin_fecha, pa, ap_a, hoy)
    r = ok(pad.get(f"{BASE}/dashboard"))
    assert r["total"] == 4
    assert r["genero"]["femenino"] == 2 and r["genero"]["masculino"] == 1 and r["genero"]["sin_dato"] == 1
    assert r["genero"]["pct_femenino"] == 50.0
    grupos = {g["nombre"]: g["total"] for g in r["por_grupo_edad"]}
    assert grupos == {"ADULTO": 2, "Sin grupo": 2} and sum(grupos.values()) == r["total"]
    assert r["por_apoyo"] == [{"nombre": "Despensa", "total": 4}]
    assert [x["nombre"] for x in r["por_localidad"]] == ["Loc1", "Loc2"]  # "Sin localidad" no entra al top


def test_top_5_localidades(m):  # noqa: F811
    pad, pa, pb, est, mu, locs, ap_a, ap_b, col = _escenario(m)
    hoy = date.today().isoformat()
    for i, loc in enumerate(locs):  # Loc1 tiene 6 capturas, Loc2 5 ... Loc6 1
        b = _ben(pad, f"T{i}", loc, "F", 30, est, mu)
        for _ in range(6 - i):
            _cap(pad.c, m, b, pa, ap_a, hoy)
    top = ok(pad.get(f"{BASE}/dashboard"))["por_localidad"]
    assert [(x["nombre"], x["total"]) for x in top] == [("Loc1", 6), ("Loc2", 5), ("Loc3", 4), ("Loc4", 3), ("Loc5", 2)]


def test_alcance_por_programa_asignado_y_filtro_de_programas(m):  # noqa: F811
    pad, pa, pb, est, mu, locs, ap_a, ap_b, col = _escenario(m)
    b = _ben(pad, "X1", locs[0], "F", 30, est, mu)
    hoy = date.today().isoformat()
    _cap(pad.c, m, b, pa, ap_a, hoy)
    _cap(m.admin, m, b, pb, ap_b, hoy)
    assert ok(pad.get(f"{BASE}/dashboard"))["total"] == 1                      # Padrón solo ve su programa
    assert ok(pad.get(f"{BASE}/dashboard", params={"programa_ids[]": pb["id"]}))["total"] == 0  # pedir uno ajeno no lo abre
    assert ok(m.get(m.admin, f"/api/{BASE}/dashboard"))["total"] == 2          # el administrador ve todo
    assert ok(m.get(m.admin, f"/api/{BASE}/dashboard", params={"programa_ids[]": pb["id"]}))["total"] == 1
    assert ok(pad.get(f"{BASE}/detalles"))["total"] == 1


def test_dashboard_filtra_por_fechas_y_por_defecto_es_hoy(m):  # noqa: F811
    pad, pa, pb, est, mu, locs, ap_a, ap_b, col = _escenario(m)
    b = _ben(pad, "F1", locs[0], "F", 30, est, mu)
    _cap(pad.c, m, b, pa, ap_a, date.today().isoformat())
    _cap(pad.c, m, b, pa, ap_a, "2024-05-01")
    assert ok(pad.get(f"{BASE}/dashboard"))["total"] == 1
    assert ok(pad.get(f"{BASE}/dashboard", params={"fecha_ini": "2024-01-01", "fecha_fin": "2024-12-31"}))["total"] == 1
    assert ok(pad.get(f"{BASE}/dashboard", params={"fecha_ini": "2024-01-01", "fecha_fin": date.today().isoformat()}))["total"] == 2
    assert pad.get(f"{BASE}/dashboard", params={"fecha_ini": "2026-02-01", "fecha_fin": "2026-01-01"}).status_code == 422


def test_detallado_colonia_del_catalogo_o_a_mano_y_exportar(m):  # noqa: F811
    pad, pa, pb, est, mu, locs, ap_a, ap_b, col = _escenario(m)
    cat = _ben(pad, "C1", locs[0], "F", 30, est, mu, colonia_id=col["id"])
    mano = _ben(pad, "C2", locs[0], "M", 30, est, mu, colonia="Mi colonia")
    assert cat["colonia"] == "Jardines" and cat["colonia_id"] == col["id"]
    hoy = date.today().isoformat()
    _cap(pad.c, m, cat, pa, ap_a, hoy)
    _cap(pad.c, m, mano, pa, ap_a, hoy)
    r = ok(pad.get(f"{BASE}/detalles"))
    assert r["titulo"] == "DETALLADO PADRON BENEFICIARIO" and r["total"] == 2 and len(r["encabezados"]) == 16
    assert {f[5] for f in r["filas"]} == {"[C1]Jardines", "Mi colonia"}
    assert pad.get(f"{BASE}/detalles/exportar").status_code == 200
    assert ok(pad.get(f"{BASE}/detalles", params={"curp": "c2"}))["total"] == 1
    # una colonia del catálogo en uso por un beneficiario no se puede borrar
    assert pad.delete("geo/colonias", col["id"]).status_code == 409


def test_concentrado_exige_curp_valida_y_cuenta_por_anio(m):  # noqa: F811
    pad, pa, pb, est, mu, locs, ap_a, ap_b, col = _escenario(m)
    b = _ben(pad, "K1", locs[0], "F", 30, est, mu)
    nivel = ok(pad.get("niveles-socioeconomicos"))[0]
    _cap(pad.c, m, b, pa, ap_a, "2024-03-01")
    _cap(pad.c, m, b, pa, ap_a, "2025-03-01")
    _cap(pad.c, m, b, pa, ap_a, "2025-04-01", nivel_socioeconomico_id=nivel["id"])
    for params in ({"tipo": "concentrado"}, {"tipo": "concentrado", "curp": "NOEXISTE"}):
        r = pad.get(f"{BASE}/detalles", params={**params, "anio_ini": 2024, "anio_fin": 2025})
        assert r.status_code == 422 and r.json()["mensaje"] == "Para Generar Tipo Concentrado debe tener un CURP valido"
    r = ok(pad.get(f"{BASE}/detalles", params={"tipo": "concentrado", "curp": "k1", "anio_ini": 2024, "anio_fin": 2025}))
    assert r["beneficiario"]["nombre"] == "Nombre K1" and r["beneficiario"]["genero"] == "Femenino"
    assert r["beneficiario"]["grupo_edad_actual"] == "ADULTO" and r["beneficiario"]["nivel_socioeconomico"] == nivel["nombre"]
    assert r["anios"] == [2024, 2025] and r["documentos"] == []
    assert r["beneficio"][0]["anios"] == {"2024": 1, "2025": 2}
    assert pad.get(f"{BASE}/detalles/exportar", params={"tipo": "concentrado", "curp": "K1", "anio_ini": 2024, "anio_fin": 2025}).status_code == 200


def test_comparativo_top_5_por_total_del_rango(m):  # noqa: F811
    pad, pa, pb, est, mu, locs, ap_a, ap_b, col = _escenario(m)
    for i, (loc, por_anio) in enumerate(zip(locs, [{2024: 1, 2025: 4}, {2024: 4}, {2025: 3}, {2024: 1}, {2025: 1}, {2026: 1}])):
        b = _ben(pad, f"M{i}", loc, "F", 30, est, mu)
        for anio, n in por_anio.items():
            for _ in range(n):
                _cap(pad.c, m, b, pa, ap_a, f"{anio}-02-01")
    r = ok(pad.get(f"{BASE}/comparativo", params={"anio_ini": 2024, "anio_fin": 2025}))
    assert r["anios"] == [2024, 2025]
    assert [(x["nombre"], x["total"]) for x in r["localidades"]] == [("Loc1", 5), ("Loc2", 4), ("Loc3", 3), ("Loc4", 1), ("Loc5", 1)]
    assert r["localidades"][0]["anios"] == {"2024": 1, "2025": 4}
    assert pad.get(f"{BASE}/comparativo", params={"anio_ini": 2020, "anio_fin": 2025}).status_code == 422


def test_informes_no_entra_a_las_estadisticas_del_padron(m):  # noqa: F811
    pa, _ = dos_programas(m)
    inf = Pad(m, [pa["id"]], tipo="informes", usuario="inf")
    for ruta in ("dashboard", "detalles", "detalles/exportar", "comparativo"):
        assert inf.get(f"{BASE}/{ruta}").status_code == 403, ruta
