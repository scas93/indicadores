"""Fase 5, parte 1 — catálogos del Padrón vía API: permisos por tipo, unicidad de claves, rangos de edad,
pertenencia entre catálogos, borrado solo si nada lo usa, bitácora y datos de plantilla."""
import io

import pytest
from openpyxl import load_workbook
from sqlalchemy import select, update

from app.models import Bitacora, GeografiaEstado, Municipio
from app.services import padron_catalogos as svc

from .test_fase1_flujos import Mun

RUTAS = ["apoyos", "descripciones-apoyo", "niveles-socioeconomicos", "grupos-edad",
         "geo/municipios", "geo/localidades", "geo/colonias"]


@pytest.fixture()
def m(admin, db):
    mun = Mun(admin)
    estado = db.scalar(select(GeografiaEstado).order_by(GeografiaEstado.clave))
    db.execute(update(Municipio).where(Municipio.subdominio == "demo").values(estado_republica_id=estado.id))
    db.commit()
    mun.estado = str(estado.id)
    return mun


class Pad:
    """Un usuario Padrón con sus programas asignados y atajos para dar de alta registros."""

    def __init__(self, m, programa_ids=(), tipo="padron", usuario="pad"):
        self.m = m
        m.usuario(usuario, tipo, programa_ids=list(programa_ids))
        self.c = m.cliente(usuario, "pw")

    def get(self, ruta, **kw): return self.m.get(self.c, f"/api/{ruta}", **kw)
    def post(self, ruta, cuerpo): return self.m.post(self.c, f"/api/{ruta}", cuerpo)
    def patch(self, ruta, id_, cuerpo): return self.m.patch(self.c, f"/api/{ruta}/{id_}", cuerpo)
    def delete(self, ruta, id_): return self.c.delete(f"/api/{ruta}/{id_}", headers=self.m.h)
    def lote(self, ruta, ids): return self.post(f"{ruta}/eliminar-lote", {"ids": ids})


def dos_programas(m):
    cg, *_ = m.planeacion()
    return m.programa("A", cg), m.programa("B", cg)


def ok(r, status=200):
    assert r.status_code == status, r.text
    return r.json() if r.content else None


# --- quién los usa -------------------------------------------------------------------------------------
def test_informes_recibe_403_en_todos_los_endpoints_de_los_catalogos(m):
    pa, _ = dos_programas(m)
    inf = Pad(m, [pa["id"]], tipo="informes", usuario="inf")
    uid = "00000000-0000-0000-0000-000000000001"
    for ruta in RUTAS:
        assert inf.get(ruta).status_code == 403, ruta
        assert inf.get(f"{ruta}/exportar").status_code == 403, ruta
        assert inf.post(ruta, {"clave": "x", "nombre": "x"}).status_code == 403, ruta
        assert inf.patch(ruta, uid, {"nombre": "x"}).status_code == 403, ruta
        assert inf.delete(ruta, uid).status_code == 403, ruta
        assert inf.lote(ruta, [uid]).status_code == 403, ruta
    assert inf.get("padron/programas").status_code == 403 and inf.get("geo/estados").status_code == 403


def test_padron_y_administrador_entran_a_los_siete_catalogos(m):
    pad = Pad(m)
    for ruta in RUTAS:
        assert pad.get(ruta).status_code == 200, ruta
        assert m.get(m.admin, f"/api/{ruta}").status_code == 200, ruta
    assert m.get(m.cliente("pad", "pw"), "/api/estadisticas/ejes", params={"anio": 2025}).status_code == 403  # no es acceso a Informes


def test_sin_sesion_es_401(m):
    from fastapi.testclient import TestClient
    from app.main import app
    assert TestClient(app).get("/api/apoyos", headers=m.h).status_code == 401


# --- alta, edición y borrado de cada catálogo -----------------------------------------------------------
def test_ciclo_completo_en_los_siete_catalogos(m):
    pa, _ = dos_programas(m)
    pad = Pad(m, [pa["id"]])
    estados = pad.get("geo/estados").json()
    estado = estados[0]["id"]

    ap = ok(pad.post("apoyos", {"clave": "DESP", "nombre": "Despensas", "programa_id": pa["id"], "observaciones": "x"}), 201)
    assert (ap["programa_id"], ap["observaciones"]) == (pa["id"], "x")
    de = ok(pad.post("descripciones-apoyo", {"clave": "D1", "nombre": "Básicas", "apoyo_id": ap["id"]}), 201)
    nv = ok(pad.post("niveles-socioeconomicos", {"nombre": "Muy alto"}), 201)
    gr = ok(pad.post("grupos-edad", {"nombre": "Infancia", "edad_min": 81, "edad_max": 90}), 201)
    mu = ok(pad.post("geo/municipios", {"clave": "015", "nombre": "Uno", "estado_id": estado}), 201)
    lo = ok(pad.post("geo/localidades", {"clave": "L1", "nombre": "Centro", "municipio_id": mu["id"]}), 201)
    co = ok(pad.post("geo/colonias", {"clave": "C1", "nombre": "Jardines", "estado_id": estado, "municipio_id": mu["id"]}), 201)
    assert (lo["municipio"], lo["estado_id"]) == ("Uno", estado) and co["municipio"] == "Uno" and gr["rango"] == "81-90"
    assert nv["clave"] == "muy_alto"

    for ruta, reg, cambio in [("apoyos", ap, {"nombre": "Despensa"}), ("descripciones-apoyo", de, {"nombre": "Básica"}),
                              ("niveles-socioeconomicos", nv, {"nombre": "Altísimo"}),
                              ("grupos-edad", gr, {"nombre": "Otra", "edad_max": 95}),
                              ("geo/municipios", mu, {"nombre": "Uno bis"}), ("geo/localidades", lo, {"nombre": "Centro 2"}),
                              ("geo/colonias", co, {"nombre": "Jardines 2"})]:
        nuevo = ok(pad.patch(ruta, reg["id"], cambio))
        assert nuevo["nombre"] == cambio["nombre"], ruta
        assert nuevo["clave"] == reg["clave"], ruta  # editar el nombre no mueve la clave
    # borrar en orden: primero lo que depende de otro
    for ruta, reg in [("geo/colonias", co), ("geo/localidades", lo), ("geo/municipios", mu), ("grupos-edad", gr),
                      ("niveles-socioeconomicos", nv), ("descripciones-apoyo", de), ("apoyos", ap)]:
        assert pad.delete(ruta, reg["id"]).status_code == 204, ruta
        assert all(f["id"] != reg["id"] for f in pad.get(ruta).json()), ruta


def test_busqueda_por_clave_y_por_nombre(m):
    pa, _ = dos_programas(m)
    pad = Pad(m, [pa["id"]])
    for c, n in [("A1", "Despensas"), ("B2", "Becas")]:
        ok(pad.post("apoyos", {"clave": c, "nombre": n, "programa_id": pa["id"]}), 201)
    assert [x["clave"] for x in pad.get("apoyos", params={"clave": "a"}).json()] == ["A1"]
    assert [x["clave"] for x in pad.get("apoyos", params={"nombre": "BEC"}).json()] == ["B2"]
    assert len(pad.get("apoyos").json()) == 2


# --- claves únicas ---------------------------------------------------------------------------------------
def test_no_se_pueden_crear_dos_claves_iguales(m):
    pa, _ = dos_programas(m)
    pad = Pad(m, [pa["id"]])
    ap = ok(pad.post("apoyos", {"clave": "X", "nombre": "a", "programa_id": pa["id"]}), 201)
    assert pad.post("apoyos", {"clave": "x", "nombre": "b", "programa_id": pa["id"]}).json()["codigo"] == "CLAVE_DUPLICADA"
    de = ok(pad.post("descripciones-apoyo", {"clave": "X", "nombre": "a", "apoyo_id": ap["id"]}), 201)
    assert pad.post("descripciones-apoyo", {"clave": "X", "nombre": "b", "apoyo_id": ap["id"]}).status_code == 409
    mu = ok(pad.post("geo/municipios", {"clave": "M", "nombre": "a"}), 201)  # estado por omisión: el del municipio
    assert mu["estado_id"] == m.estado
    assert pad.post("geo/municipios", {"clave": "M", "nombre": "b"}).status_code == 409
    ok(pad.post("geo/localidades", {"clave": "L", "nombre": "a", "municipio_id": mu["id"]}), 201)
    assert pad.post("geo/localidades", {"clave": "L", "nombre": "b", "municipio_id": mu["id"]}).status_code == 409
    ok(pad.post("geo/colonias", {"clave": "C", "nombre": "a", "estado_id": m.estado, "municipio_id": mu["id"]}), 201)
    assert pad.post("geo/colonias", {"clave": "C", "nombre": "b", "estado_id": m.estado, "municipio_id": mu["id"]}).status_code == 409
    ok(pad.post("niveles-socioeconomicos", {"nombre": "Nuevo"}), 201)
    assert pad.post("niveles-socioeconomicos", {"nombre": "nuevo"}).status_code == 409
    # editar una clave hacia otra existente también se rechaza
    otra = ok(pad.post("apoyos", {"clave": "Y", "nombre": "c", "programa_id": pa["id"]}), 201)
    assert pad.patch("apoyos", otra["id"], {"clave": "X"}).status_code == 409
    assert pad.patch("apoyos", otra["id"], {"clave": "Y", "nombre": "c2"}).status_code == 200  # conservar la propia, sí
    assert de["clave"] == "X"


def test_clave_y_nombre_obligatorios(m):
    pa, _ = dos_programas(m)
    pad = Pad(m, [pa["id"]])
    r = pad.post("apoyos", {"clave": " ", "nombre": "", "programa_id": pa["id"]})
    assert (r.status_code, sorted(r.json()["campos"])) == (422, ["clave", "nombre"])


def test_la_clave_se_repite_libremente_entre_municipios_de_la_plataforma(admin, m):
    pa, _ = dos_programas(m)
    ok(Pad(m, [pa["id"]]).post("apoyos", {"clave": "X", "nombre": "a", "programa_id": pa["id"]}), 201)
    otro = Mun(admin, "otro")
    cg, *_ = otro.planeacion()
    po = otro.programa("A", cg)
    assert otro.post(otro.admin, "/api/apoyos", {"clave": "X", "nombre": "a", "programa_id": po["id"]}).status_code == 201


# --- grupos de edad --------------------------------------------------------------------------------------
def test_grupos_de_edad_sin_traslape_ni_rangos_invertidos(m):
    pad = Pad(m)
    base = {g["clave"]: g for g in pad.get("grupos-edad").json()}
    assert sorted(base) == ["11-17", "18-59", "2-10", "60-80"]  # los 4 de la referencia, todos con máximo
    assert [(g["nombre"], g["edad_min"], g["edad_max"]) for g in pad.get("grupos-edad").json()] == [
        ("NIÑO", 2, 10), ("ADOLESCENTE", 11, 17), ("ADULTO", 18, 59), ("TERCERA EDAD", 60, 80)]
    assert pad.post("grupos-edad", {"nombre": "X", "edad_min": 55, "edad_max": 65}).json()["codigo"] == "RANGO_TRASLAPADO"
    assert pad.post("grupos-edad", {"nombre": "X", "edad_min": 10, "edad_max": 13}).json()["codigo"] == "RANGO_TRASLAPADO"
    assert pad.post("grupos-edad", {"nombre": "X", "edad_min": 70}).json()["codigo"] == "RANGO_TRASLAPADO"  # abierto sobre 60-80
    r = pad.post("grupos-edad", {"nombre": "X", "edad_min": 90, "edad_max": 81})
    assert (r.status_code, r.json()["codigo"]) == (422, "RANGO_INVALIDO")
    # el catálogo permite agregar rangos nuevos en los huecos
    ok(pad.post("grupos-edad", {"nombre": "Longevos", "edad_min": 81, "edad_max": 90}), 201)
    ok(pad.post("grupos-edad", {"nombre": "Lactantes", "edad_min": 0, "edad_max": 1}), 201)
    # editar: ampliar un grupo hacia otro se rechaza; moverlo dentro de su hueco, no
    g = base["11-17"]
    assert pad.patch("grupos-edad", g["id"], {"edad_max": 20}).json()["codigo"] == "RANGO_TRASLAPADO"
    assert pad.patch("grupos-edad", g["id"], {"edad_min": 12, "edad_max": 17}).status_code == 200
    assert pad.patch("grupos-edad", g["id"], {"nombre": "Adolescentes"}).json()["nombre"] == "Adolescentes"
    assert pad.post("grupos-edad", {"nombre": "Adolescentes", "edad_min": 100, "edad_max": 105}).status_code == 409  # nombre repetido


# --- pertenencia entre catálogos ----------------------------------------------------------------------------
def test_apoyo_solo_con_un_programa_asignado_y_solo_se_ven_los_de_sus_programas(m):
    pa, pb = dos_programas(m)
    pad = Pad(m, [pa["id"]])
    assert [p["clave"] for p in pad.get("padron/programas").json()] == ["A"]
    assert [p["clave"] for p in m.get(m.admin, "/api/padron/programas").json()] == ["A", "B"]
    r = pad.post("apoyos", {"clave": "X", "nombre": "x", "programa_id": pb["id"]})
    assert (r.status_code, r.json()["codigo"]) == (422, "PROGRAMA_NO_ASIGNADO")
    assert pad.post("apoyos", {"clave": "X", "nombre": "x"}).status_code == 422  # sin programa
    ap_a = ok(pad.post("apoyos", {"clave": "XA", "nombre": "x", "programa_id": pa["id"]}), 201)
    ap_b = ok(m.post(m.admin, "/api/apoyos", {"clave": "XB", "nombre": "x", "programa_id": pb["id"]}), 201)
    assert [a["clave"] for a in pad.get("apoyos").json()] == ["XA"]                      # no ve el del programa B
    assert sorted(a["clave"] for a in m.get(m.admin, "/api/apoyos").json()) == ["XA", "XB"]
    assert pad.patch("apoyos", ap_b["id"], {"nombre": "y"}).status_code == 404
    assert pad.delete("apoyos", ap_b["id"]).status_code == 404
    assert pad.patch("apoyos", ap_a["id"], {"programa_id": pb["id"]}).status_code == 422   # tampoco moverlo a B
    # el programa inexistente o de otro municipio
    assert pad.post("apoyos", {"clave": "Z", "nombre": "x", "programa_id": "00000000-0000-0000-0000-000000000009"}).status_code == 422


def test_descripcion_solo_de_un_apoyo_existente_y_visible(m):
    pa, pb = dos_programas(m)
    pad = Pad(m, [pa["id"]])
    ap_b = ok(m.post(m.admin, "/api/apoyos", {"clave": "XB", "nombre": "x", "programa_id": pb["id"]}), 201)
    assert pad.post("descripciones-apoyo", {"clave": "D", "nombre": "d", "apoyo_id": ap_b["id"]}).status_code == 422
    assert pad.post("descripciones-apoyo", {"clave": "D", "nombre": "d", "apoyo_id": "00000000-0000-0000-0000-000000000009"}).status_code == 422
    assert pad.post("descripciones-apoyo", {"clave": "D", "nombre": "d"}).status_code == 422
    de_b = ok(m.post(m.admin, "/api/descripciones-apoyo", {"clave": "DB", "nombre": "d", "apoyo_id": ap_b["id"]}), 201)
    assert pad.get("descripciones-apoyo").json() == []
    assert pad.patch("descripciones-apoyo", de_b["id"], {"nombre": "z"}).status_code == 404
    ap_a = ok(pad.post("apoyos", {"clave": "XA", "nombre": "x", "programa_id": pa["id"]}), 201)
    de_a = ok(pad.post("descripciones-apoyo", {"clave": "DA", "nombre": "d", "apoyo_id": ap_a["id"]}), 201)
    assert pad.patch("descripciones-apoyo", de_a["id"], {"apoyo_id": ap_b["id"]}).status_code == 422
    assert [d["apoyo_id"] for d in pad.get("descripciones-apoyo", params={"apoyo_id": ap_a["id"]}).json()] == [ap_a["id"]]


def test_localidad_y_colonia_pertenencias(m, db):
    pad = Pad(m)
    otro_estado = next(e["id"] for e in pad.get("geo/estados").json() if e["id"] != m.estado)
    mu = ok(pad.post("geo/municipios", {"clave": "015", "nombre": "Uno"}), 201)
    assert pad.post("geo/localidades", {"clave": "L", "nombre": "x"}).status_code == 422  # requiere municipio
    assert pad.post("geo/localidades", {"clave": "L", "nombre": "x", "municipio_id": "00000000-0000-0000-0000-000000000009"}).status_code == 422
    # una colonia cuelga de estado + municipio, no de una localidad; el municipio debe ser del estado
    r = pad.post("geo/colonias", {"clave": "C", "nombre": "x", "estado_id": otro_estado, "municipio_id": mu["id"]})
    assert (r.status_code, r.json()["codigo"]) == (422, "JERARQUIA_INVALIDA")
    lo = ok(pad.post("geo/localidades", {"clave": "L", "nombre": "x", "municipio_id": mu["id"]}), 201)
    assert pad.post("geo/colonias", {"clave": "C", "nombre": "x", "estado_id": m.estado, "municipio_id": lo["id"]}).status_code == 422  # una localidad no es municipio
    assert pad.post("geo/colonias", {"clave": "C", "nombre": "x", "estado_id": m.estado}).status_code == 422
    co = ok(pad.post("geo/colonias", {"clave": "C", "nombre": "x", "estado_id": m.estado, "municipio_id": mu["id"]}), 201)
    assert pad.patch("geo/colonias", co["id"], {"estado_id": otro_estado}).status_code == 422
    # un municipio con colonias no puede cambiar de estado
    assert pad.patch("geo/municipios", mu["id"], {"estado_id": otro_estado}).status_code == 422
    # filtros por estado y municipio
    assert len(pad.get("geo/colonias", params={"municipio_id": mu["id"]}).json()) == 1
    assert pad.get("geo/colonias", params={"estado_id": otro_estado}).json() == []
    assert [x["id"] for x in pad.get("geo/localidades", params={"estado_id": m.estado}).json()] == [lo["id"]]


# --- borrar solo si nada lo usa -----------------------------------------------------------------------------
def test_no_se_borra_lo_que_otro_registro_usa(m):
    pa, _ = dos_programas(m)
    pad = Pad(m, [pa["id"]])
    ap = ok(pad.post("apoyos", {"clave": "X", "nombre": "x", "programa_id": pa["id"]}), 201)
    de = ok(pad.post("descripciones-apoyo", {"clave": "D", "nombre": "d", "apoyo_id": ap["id"]}), 201)
    r = pad.delete("apoyos", ap["id"])
    assert (r.status_code, r.json()["codigo"]) == (409, "REGISTRO_EN_USO") and "descripciones de apoyo" in r.json()["mensaje"]
    mu = ok(pad.post("geo/municipios", {"clave": "M", "nombre": "m"}), 201)
    lo = ok(pad.post("geo/localidades", {"clave": "L", "nombre": "l", "municipio_id": mu["id"]}), 201)
    assert pad.delete("geo/municipios", mu["id"]).status_code == 409
    pad.delete("geo/localidades", lo["id"])
    co = ok(pad.post("geo/colonias", {"clave": "C", "nombre": "c", "estado_id": m.estado, "municipio_id": mu["id"]}), 201)
    assert pad.delete("geo/municipios", mu["id"]).status_code == 409  # ahora lo usa una colonia
    pad.delete("geo/colonias", co["id"])
    assert pad.delete("geo/municipios", mu["id"]).status_code == 204
    assert pad.delete("descripciones-apoyo", de["id"]).status_code == 204
    assert pad.delete("apoyos", ap["id"]).status_code == 204
    assert pad.delete("apoyos", ap["id"]).status_code == 404


def test_regla_de_borrado_preparada_para_las_entregas(m, monkeypatch):
    """La parte 2 registra aquí el conteo de entregas; mientras haya una, ningún catálogo que la use se borra."""
    pa, _ = dos_programas(m)
    pad = Pad(m, [pa["id"]])
    ap = ok(pad.post("apoyos", {"clave": "X", "nombre": "x", "programa_id": pa["id"]}), 201)
    gr = ok(pad.post("grupos-edad", {"nombre": "Nuevo", "edad_min": 81, "edad_max": 90}), 201)
    entregas = {"n": 2}
    for entidad in ("apoyo", "grupo_edad"):
        monkeypatch.setitem(svc.USOS_EXTRA, entidad, [("entregas", lambda db, id_: entregas["n"])])
    r = pad.delete("apoyos", ap["id"])
    assert (r.status_code, r.json()["codigo"]) == (409, "REGISTRO_EN_USO") and "2 entregas" in r.json()["mensaje"]
    assert pad.delete("grupos-edad", gr["id"]).status_code == 409
    entregas["n"] = 0
    assert pad.delete("apoyos", ap["id"]).status_code == 204
    assert pad.delete("grupos-edad", gr["id"]).status_code == 204


def test_eliminar_en_lote_borra_lo_libre_y_reporta_lo_demas(m):
    pa, _ = dos_programas(m)
    pad = Pad(m, [pa["id"]])
    usado = ok(pad.post("apoyos", {"clave": "U", "nombre": "u", "programa_id": pa["id"]}), 201)
    libres = [ok(pad.post("apoyos", {"clave": f"L{i}", "nombre": "l", "programa_id": pa["id"]}), 201)["id"] for i in range(2)]
    ok(pad.post("descripciones-apoyo", {"clave": "D", "nombre": "d", "apoyo_id": usado["id"]}), 201)
    r = ok(pad.lote("apoyos", libres + [usado["id"], libres[0], "00000000-0000-0000-0000-000000000009"]))
    assert r["eliminados"] == 2
    assert sorted(x["codigo"] for x in r["rechazados"]) == ["NO_ENCONTRADO", "REGISTRO_EN_USO"]
    assert [a["clave"] for a in pad.get("apoyos").json()] == ["U"]


# --- bitácora -------------------------------------------------------------------------------------------------
def test_los_cambios_quedan_en_bitacora(m, db):
    pa, _ = dos_programas(m)
    pad = Pad(m, [pa["id"]])
    ap = ok(pad.post("apoyos", {"clave": "X", "nombre": "x", "programa_id": pa["id"]}), 201)
    pad.patch("apoyos", ap["id"], {"nombre": "y"})
    pad.delete("apoyos", ap["id"])
    gr = ok(pad.post("grupos-edad", {"nombre": "N", "edad_min": 81, "edad_max": 90}), 201)
    acciones = [b.accion for b in db.scalars(select(Bitacora).where(Bitacora.entidad.in_(["apoyo", "grupo_edad"])).order_by(Bitacora.created_at))]
    assert acciones == ["apoyo.crear", "apoyo.editar", "apoyo.eliminar", "grupo_edad.crear"]
    assert gr["id"]


# --- datos de plantilla y exportación ------------------------------------------------------------------------------
def test_un_municipio_nuevo_trae_los_4_grupos_de_edad_y_niveles_y_arranca_vacio_en_lo_demas(m):
    pad = Pad(m)
    assert len(pad.get("grupos-edad").json()) == 4 and len(pad.get("niveles-socioeconomicos").json()) == 4
    for ruta in ("apoyos", "descripciones-apoyo", "geo/colonias"):
        assert pad.get(ruta).json() == [], ruta


def test_exportar_genera_el_excel_con_las_columnas_de_la_pantalla(m):
    pa, _ = dos_programas(m)
    pad = Pad(m, [pa["id"]])
    ok(pad.post("apoyos", {"clave": "X", "nombre": "Despensas", "programa_id": pa["id"], "observaciones": "o"}), 201)
    r = pad.get("apoyos/exportar", params={"nombre": "desp"})
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    filas = list(load_workbook(io.BytesIO(r.content)).active.values)
    assert filas == [("Clave", "Apoyo", "Observaciones"), ("X", "Despensas", "o")]
    g = list(load_workbook(io.BytesIO(pad.get("grupos-edad/exportar").content)).active.values)
    assert g[0] == ("Edad", "Rango min-max") and g[1] == ("NIÑO", "2-10") and g[-1] == ("TERCERA EDAD", "60-80")


def test_aislamiento_entre_municipios(admin, m):
    pa, _ = dos_programas(m)
    ap = ok(Pad(m, [pa["id"]]).post("apoyos", {"clave": "X", "nombre": "x", "programa_id": pa["id"]}), 201)
    otro = Mun(admin, "otro")
    assert otro.get(otro.admin, "/api/apoyos").json() == []
    assert otro.admin.delete(f"/api/apoyos/{ap['id']}", headers=otro.h).status_code == 404
