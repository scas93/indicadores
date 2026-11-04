"""Fase 4.2 — beneficiarios y captura por API: CURP única, cascada geográfica, edad y grupo, cascada
programa→apoyo→descripción, restricción por programa, borrado protegido y permisos."""
from datetime import date

import pytest
from .test_fase5_catalogos import Pad, dos_programas, m, ok  # noqa: F401  (m es un fixture)


def _estado(pad):
    return next(e for e in pad.get("geo/estados").json() if e["por_defecto"])["id"]


def _geo(pad):
    estado = _estado(pad)
    mu = ok(pad.post("geo/municipios", {"clave": "901", "nombre": "Muni", "estado_id": estado}), 201)
    lo = ok(pad.post("geo/localidades", {"clave": "L1", "nombre": "Loc", "municipio_id": mu["id"]}), 201)
    return estado, mu, lo


def _ben(pad, curp="EJEMPLO1", **extra):
    return ok(pad.post("beneficiarios", {"curp": curp, "nombre": "Perez Lopez Ana", **extra}), 201)


def test_curp_unica_obligatoria_y_formato_libre(m):  # noqa: F811
    pad = Pad(m)
    b = _ben(pad, " irregular-1 ")
    assert b["curp"] == "IRREGULAR-1"
    assert pad.post("beneficiarios", {"curp": "irregular-1", "nombre": "Otro"}).status_code == 409
    assert pad.post("beneficiarios", {"curp": "  ", "nombre": "Otro"}).status_code == 422
    otro = _ben(pad, "OTRA")
    # al editar, su propia CURP no cuenta como repetida, pero la de otro sí
    assert ok(pad.patch("beneficiarios", otro["id"], {"nombre": "Nuevo"}))["nombre"] == "Nuevo"
    assert pad.patch("beneficiarios", otro["id"], {"curp": "IRREGULAR-1"}).status_code == 409


def test_cascada_estado_municipio_localidad(m):  # noqa: F811
    pad = Pad(m)
    estado, mu, lo = _geo(pad)
    b = _ben(pad, estado_id=estado, municipio_id=mu["id"], localidad_id=lo["id"], genero="F",
             fecha_nacimiento="1990-03-04", colonia="Libre")
    assert (b["municipio"], b["localidad"], b["colonia"], b["genero_nombre"]) == ("Muni", "Loc", "Libre", "Femenino")
    otro = ok(pad.post("geo/municipios", {"clave": "902", "nombre": "Otro", "estado_id": estado}), 201)
    assert pad.post("beneficiarios", {"curp": "X1", "nombre": "x", "estado_id": estado, "municipio_id": otro["id"],
                                      "localidad_id": lo["id"]}).status_code == 422  # localidad de otro municipio
    assert pad.post("beneficiarios", {"curp": "X2", "nombre": "x", "localidad_id": lo["id"]}).status_code == 422


def test_filtros_exportar_y_borrado_en_lote(m):  # noqa: F811
    pad = Pad(m)
    a, b = _ben(pad, "AAA1"), _ben(pad, "BBB2")
    assert [x["curp"] for x in ok(pad.get("beneficiarios", params={"curp": "aa"}))] == ["AAA1"]
    assert pad.get("beneficiarios/exportar").status_code == 200
    assert [x["curp"] for x in ok(pad.get("beneficiarios-buscar", params={"q": "bbb"}))] == ["BBB2"]
    r = ok(pad.lote("beneficiarios", [a["id"], b["id"]]))
    assert r["eliminados"] == 2


def _montaje(pad, programa):
    ap = ok(pad.post("apoyos", {"clave": "A", "nombre": "Apoyo", "programa_id": programa["id"]}), 201)
    de = ok(pad.post("descripciones-apoyo", {"clave": "D", "nombre": "Desc", "apoyo_id": ap["id"]}), 201)
    return ap, de


def test_captura_calcula_edad_y_grupo_y_queda_en_las_del_dia(m, db):  # noqa: F811
    pa, _ = dos_programas(m)
    pad = Pad(m, [pa["id"]])
    ap, de = _montaje(pad, pa)
    hoy = date.today()
    nac = date(hoy.year - 30, 1, 1)
    b = _ben(pad, fecha_nacimiento=nac.isoformat())
    calc = ok(pad.get("padron/capturas/calculo", params={"beneficiario_id": b["id"]}))
    assert calc["edad"] in (29, 30) and calc["grupo_edad"] == "ADULTO"  # 29 si el reloj de México aún no cambia de día
    nivel = ok(pad.get("niveles-socioeconomicos"))[0]
    c = ok(pad.post("padron/capturas", {"beneficiario_id": b["id"], "programa_id": pa["id"], "apoyo_id": ap["id"],
                                        "descripcion_apoyo_id": de["id"], "nivel_socioeconomico_id": nivel["id"],
                                        "cantidad": 2, "observaciones": "obs"}), 201)
    assert (c["grupo_edad"], c["cantidad"], c["curp"], c["descripcion_apoyo"]) == ("ADULTO", 2, "EJEMPLO1", "Desc")
    assert [x["id"] for x in ok(pad.get("padron/capturas"))] == [c["id"]]
    ok(pad.c.delete(f"/api/padron/capturas/{c['id']}", headers=m.h), 204)
    assert ok(pad.get("padron/capturas")) == []


def test_edad_sin_grupo_y_sin_fecha_de_nacimiento(m):  # noqa: F811
    pa, _ = dos_programas(m)
    pad = Pad(m, [pa["id"]])
    ap, _ = _montaje(pad, pa)
    bebe = _ben(pad, "BEBE", fecha_nacimiento=date.today().replace(year=date.today().year - 1, day=1).isoformat())
    sin = _ben(pad, "SIN")
    for b, edad in ((bebe, 1), (sin, None)):
        c = ok(pad.post("padron/capturas", {"beneficiario_id": b["id"], "programa_id": pa["id"], "apoyo_id": ap["id"]}), 201)
        assert c["edad"] == edad and c["grupo_edad"] is None  # ningún grupo cubre 1 año ni "sin fecha"


def test_cascada_programa_apoyo_descripcion(m):  # noqa: F811
    pa, pb = dos_programas(m)
    pad = Pad(m, [pa["id"], pb["id"]])
    ap, de = _montaje(pad, pa)
    ap_b = ok(pad.post("apoyos", {"clave": "B", "nombre": "De B", "programa_id": pb["id"]}), 201)
    de_b = ok(pad.post("descripciones-apoyo", {"clave": "DB", "nombre": "Desc B", "apoyo_id": ap_b["id"]}), 201)
    b = _ben(pad)
    base = {"beneficiario_id": b["id"]}
    assert pad.post("padron/capturas", {**base, "programa_id": pa["id"], "apoyo_id": ap_b["id"]}).status_code == 422
    assert pad.post("padron/capturas", {**base, "programa_id": pa["id"], "apoyo_id": ap["id"],
                                        "descripcion_apoyo_id": de_b["id"]}).status_code == 422
    assert pad.post("padron/capturas", {**base, "programa_id": pa["id"], "apoyo_id": ap["id"], "cantidad": 0}).status_code == 422
    assert pad.post("padron/capturas", {**base, "programa_id": pa["id"], "apoyo_id": ap["id"]}).status_code == 201


def test_padron_solo_captura_en_sus_programas_y_ve_solo_sus_capturas(m):  # noqa: F811
    pa, pb = dos_programas(m)
    pad = Pad(m, [pa["id"]])
    adm_ap = ok(m.post(m.admin, "/api/apoyos", {"clave": "B", "nombre": "De B", "programa_id": pb["id"]}), 201)
    ap, _ = _montaje(pad, pa)
    b = _ben(pad)
    assert pad.post("padron/capturas", {"beneficiario_id": b["id"], "programa_id": pb["id"], "apoyo_id": adm_ap["id"]}).status_code == 422
    assert [p["id"] for p in ok(pad.get("padron/programas"))] == [pa["id"]]
    assert ok(pad.get("padron/programas"))[0]["centro_gestor"]
    # el administrador captura en B; Padrón no ve esa captura ni puede borrarla
    cb = ok(m.post(m.admin, "/api/padron/capturas", {"beneficiario_id": b["id"], "programa_id": pb["id"], "apoyo_id": adm_ap["id"]}), 201)
    assert ok(pad.get("padron/capturas")) == []
    assert pad.c.delete(f"/api/padron/capturas/{cb['id']}", headers=m.h).status_code == 404


def test_no_se_borra_lo_que_tiene_capturas_y_informes_no_entra(m, db):  # noqa: F811
    pa, _ = dos_programas(m)
    pad = Pad(m, [pa["id"]])
    ap, de = _montaje(pad, pa)
    estado, mu, lo = _geo(pad)
    b = _ben(pad, estado_id=estado, municipio_id=mu["id"], localidad_id=lo["id"])
    pad.post("padron/capturas", {"beneficiario_id": b["id"], "programa_id": pa["id"], "apoyo_id": ap["id"],
                                 "descripcion_apoyo_id": de["id"]})
    assert pad.delete("beneficiarios", b["id"]).status_code == 409
    assert pad.delete("apoyos", ap["id"]).status_code == 409
    assert pad.delete("geo/localidades", lo["id"]).status_code == 409  # la usa un beneficiario
    assert pad.delete("geo/municipios", mu["id"]).status_code == 409
    inf = Pad(m, [pa["id"]], tipo="informes", usuario="inf")
    for ruta in ("beneficiarios", "beneficiarios-buscar", "padron/capturas", "padron/contexto"):
        assert inf.get(ruta).status_code == 403, ruta
    assert inf.post("padron/capturas", {}).status_code == 403
