"""Fase 4.3b — documentos de beneficiarios por API (con almacén simulado, sin bucket real)."""
import pytest

from app.services import documentos_storage as ds

from .test_fase1_flujos import Mun
from .test_fase5_catalogos import Pad, dos_programas, m, ok  # noqa: F401  (m es un fixture)

PDF = b"%PDF-1.7\ncontenido"
PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 20


@pytest.fixture()
def almacen():
    a = ds.MemoriaAlmacen()
    ds.usar_almacen(a)
    yield a
    ds.usar_almacen(None)


def _ben(pad, curp="C1", **extra):
    return ok(pad.post("beneficiarios", {"curp": curp, "nombre": f"Nombre {curp}", **extra}), 201)


def _sube(pad, b, tipo="ine", contenido=PDF, nombre="doc.pdf", mime="application/pdf", obs=""):
    return pad.c.post(f"/api/beneficiarios/{b['id']}/documentos", headers=pad.m.h,
                      files={"archivo": (nombre, contenido, mime)}, data={"tipo": tipo, "observaciones": obs})


def test_subir_listar_ver_y_borrar_limpia_el_bucket(m, almacen):  # noqa: F811
    pad = Pad(m, [dos_programas(m)[0]["id"]])
    b = _ben(pad)
    d = ok(_sube(pad, b, "comprobante_domicilio", obs="recibo de luz"), 201)
    assert d["titulo"] == "COMPROBANTE DE DOMICILIO" and d["observaciones"] == "recibo de luz" and d["tipo"] == "comprobante_domicilio"
    (llave,) = almacen.objetos
    assert llave.startswith(f"docs/{m.id}/{b['id']}/")
    assert [x["id"] for x in ok(pad.get(f"beneficiarios/{b['id']}/documentos"))] == [d["id"]]
    r = pad.get(f"beneficiarios/{b['id']}/documentos/{d['id']}/archivo")
    assert r.status_code == 200 and r.content == PDF and r.headers["content-type"] == "application/pdf"
    assert "inline" in r.headers["content-disposition"] and r.headers["cache-control"] == "private, no-store"
    assert "attachment" in pad.get(f"beneficiarios/{b['id']}/documentos/{d['id']}/archivo?descargar=true").headers["content-disposition"]
    _sube(pad, b, "comprobante_domicilio")  # varios del mismo tipo se permiten
    assert len(ok(pad.get(f"beneficiarios/{b['id']}/documentos"))) == 2
    assert pad.c.delete(f"/api/beneficiarios/{b['id']}/documentos/{d['id']}", headers=m.h).status_code == 204
    assert llave not in almacen.objetos and len(almacen.objetos) == 1


def test_valida_tamano_y_tipo_por_contenido(m, almacen):  # noqa: F811
    pad = Pad(m, [dos_programas(m)[0]["id"]])
    b = _ben(pad)
    falso = _sube(pad, b, contenido=b"MZ ejecutable", nombre="virus.pdf", mime="application/pdf")  # dice ser PDF
    assert falso.status_code == 422 and falso.json()["codigo"] == "ARCHIVO_TIPO_INVALIDO"
    grande = _sube(pad, b, contenido=PDF + b"0" * (5 * 1024 * 1024))
    assert grande.status_code == 422 and grande.json()["codigo"] == "ARCHIVO_MUY_GRANDE"
    assert _sube(pad, b, tipo="pasaporte").json()["codigo"] == "TIPO_DOCUMENTO_INVALIDO"
    assert ok(_sube(pad, b, contenido=PNG, nombre="f.png", mime="image/png"), 201)["content_type"] == "image/png"
    assert len(almacen.objetos) == 1  # lo rechazado no llegó al bucket


def test_sin_bucket_responde_error_y_no_escribe_en_disco(m, tmp_path, monkeypatch):  # noqa: F811
    ds.usar_almacen(None)
    monkeypatch.chdir(tmp_path)
    pad = Pad(m, [dos_programas(m)[0]["id"]])
    b = _ben(pad)
    r = _sube(pad, b)
    assert r.status_code == 503 and r.json()["codigo"] == "ALMACEN_NO_CONFIGURADO"
    assert list(tmp_path.iterdir()) == []  # ni uploads/ ni nada
    assert ok(pad.get(f"beneficiarios/{b['id']}/documentos")) == []
    assert pad.delete("beneficiarios", b["id"]).status_code == 204  # sin documentos no se necesita bucket


def test_un_municipio_no_alcanza_los_documentos_de_otro(admin, m, almacen):  # noqa: F811
    pad = Pad(m, [dos_programas(m)[0]["id"]])
    b = _ben(pad)
    d = ok(_sube(pad, b), 201)
    otro = Mun(admin, "otro")
    ajeno = otro.admin
    base = f"/api/beneficiarios/{b['id']}/documentos"
    assert otro.get(ajeno, base).status_code == 404
    assert otro.get(ajeno, f"{base}/{d['id']}/archivo").status_code == 404
    assert ajeno.delete(f"{base}/{d['id']}", headers=otro.h).status_code == 404
    # ni siquiera con un beneficiario propio: el documento ajeno no cuelga de él
    b2 = ok(otro.post(ajeno, "/api/beneficiarios", {"curp": "X1", "nombre": "Otro"}), 201)
    assert otro.get(ajeno, f"/api/beneficiarios/{b2['id']}/documentos/{d['id']}/archivo").status_code == 404
    assert len(almacen.objetos) == 1


def test_informes_recibe_403(m, almacen):  # noqa: F811
    pad = Pad(m, [dos_programas(m)[0]["id"]])
    b = _ben(pad)
    d = ok(_sube(pad, b), 201)
    m.usuario("inf", "informes")
    inf = m.cliente("inf", "pw")
    base = f"/api/beneficiarios/{b['id']}/documentos"
    assert m.get(inf, base).status_code == 403
    assert m.get(inf, f"{base}/{d['id']}/archivo").status_code == 403
    assert inf.post(base, headers=m.h, files={"archivo": ("a.pdf", PDF, "application/pdf")}, data={"tipo": "ine"}).status_code == 403
    assert inf.delete(f"{base}/{d['id']}", headers=m.h).status_code == 403
    assert m.get(inf, "/api/padron/estadisticas/documentos").status_code == 403
    assert m.get(m.admin, base).status_code == 200  # el administrador sí


def test_borrar_beneficiario_limpia_archivos_y_con_capturas_no_se_borra(m, almacen):  # noqa: F811
    pa, _ = dos_programas(m)
    pad = Pad(m, [pa["id"]])
    b1, b2 = _ben(pad, "B1"), _ben(pad, "B2")
    _sube(pad, b1, "ine"), _sube(pad, b1, "curp"), _sube(pad, b2, "ine")
    assert len(almacen.objetos) == 3
    assert pad.delete("beneficiarios", b1["id"]).status_code == 204
    assert [k.split("/")[2] for k in almacen.objetos] == [b2["id"]]
    ap = ok(pad.post("apoyos", {"clave": "A", "nombre": "Despensa", "programa_id": pa["id"]}), 201)
    from datetime import date
    ok(m.post(pad.c, "/api/padron/capturas", {"beneficiario_id": b2["id"], "programa_id": pa["id"], "apoyo_id": ap["id"],
                                              "fecha_entrega": date.today().isoformat()}), 201)
    assert pad.delete("beneficiarios", b2["id"]).status_code == 409  # la regla existente se mantiene
    assert len(almacen.objetos) == 1  # y sus archivos siguen ahí


def test_reporte_falta_documento_tipo_especifico_y_todos(m, almacen):  # noqa: F811
    pa, pb = dos_programas(m)
    pad = Pad(m, [pa["id"]])  # alcance de un solo programa: el reporte igual cubre a todos
    completo, solo_ine, nada = _ben(pad, "COMPLETO"), _ben(pad, "SOLOINE"), _ben(pad, "NADA", telefono="477", correo="a@b.mx")
    for t in ("ine", "curp", "comprobante_domicilio"):
        _sube(pad, completo, t)
    _sube(pad, solo_ine, "ine")
    _sube(pad, solo_ine, "ine")

    def falta(**q):
        r = ok(pad.get("padron/estadisticas/documentos", params=q))
        return [f[0] for f in r["filas"]], r

    assert falta()[0] == ["NADA", "SOLOINE"]                 # TODOS: al menos un tipo faltante
    assert falta(faltante="todos")[0] == ["NADA", "SOLOINE"]
    assert falta(faltante="ine")[0] == ["NADA"]
    assert falta(faltante="curp")[0] == ["NADA", "SOLOINE"]
    assert falta(faltante="comprobante_domicilio")[0] == ["NADA", "SOLOINE"]
    assert falta(curp="nad")[0] == ["NADA"] and falta(nombre="solo", faltante="curp")[0] == ["SOLOINE"]
    r = falta()[1]
    assert r["titulo"] == "REPORTE FALTA DE DOCUMENTOS"
    assert r["encabezados"] == ["CURP", "Nombre", "Estado", "Municipio", "Localidad", "Colonia", "Tel.", "Correo"]
    assert r["filas"][0][6:] == ["477", "a@b.mx"]
    assert pad.get("padron/estadisticas/documentos", params={"faltante": "x"}).status_code == 422
    x = pad.get("padron/estadisticas/documentos/exportar", params={"faltante": "ine"})
    assert x.status_code == 200 and x.content[:2] == b"PK" and "reporte_falta_documentos.xlsx" in x.headers["content-disposition"]


def test_concentrado_trae_los_documentos(m, almacen):  # noqa: F811
    pad = Pad(m, [dos_programas(m)[0]["id"]])
    b = _ben(pad, "CONC1")
    d = ok(_sube(pad, b, "curp"), 201)
    r = ok(pad.get("padron/estadisticas/detalles", params={"tipo": "concentrado", "curp": "CONC1"}))
    assert [x["id"] for x in r["documentos"]] == [d["id"]] and r["beneficiario"]["id"] == b["id"]
