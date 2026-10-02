"""Fase 1 — criterios de aceptación 2–10 vía API, más ámbito (admin vs super admin), aislamiento
y recuperación de contraseña. El caso 1 (menú idéntico al sistema actual) es visual/manual."""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.main import app
from app.models import (Bitacora, PasswordResetToken, Programa, Sesion, Usuario, UsuarioPrograma)
from app.security import decrypt_password
from app.services import email as correo

from .conftest import ADMIN, crear_municipio, mun

EJ = 2026


@pytest.fixture()
def correos():
    enviados = []

    class Falso:
        def enviar(self, para, asunto, html):
            enviados.append({"para": para, "asunto": asunto, "html": html})

    app.dependency_overrides[correo.get_mailer] = lambda: Falso()
    yield enviados
    app.dependency_overrides.pop(correo.get_mailer, None)


class Mun:
    """Un municipio con un administrador ya logueado y utilidades para crear usuarios/programas."""

    def __init__(self, admin_sa, slug="demo"):
        self.slug = slug
        r = crear_municipio(admin_sa, slug)
        assert r.status_code == 201, r.text
        self.id = r.json()["municipio"]["id"]
        self.h = mun(slug)
        self.admin = self.cliente("admin1", "pw1")

    def cliente(self, usuario, password):
        c = TestClient(app)
        r = c.post("/api/auth/login", headers=self.h, json={"usuario": usuario, "password": password})
        assert r.status_code == 200, r.text
        return c

    def get(self, c, ruta, **kw): return c.get(ruta, headers=self.h, **kw)
    def post(self, c, ruta, json=None): return c.post(ruta, headers=self.h, json=json or {})
    def patch(self, c, ruta, json): return c.patch(ruta, headers=self.h, json=json)

    def usuario(self, usuario, tipo, password="pw", **extra):
        r = self.post(self.admin, "/api/usuarios", {"nombre": usuario.title(), "usuario": usuario,
                                                    "tipo": tipo, "password": password, **extra})
        assert r.status_code == 201, r.text
        return r.json()

    def planeacion(self, sufijo=""):
        a = self.post(self.admin, "/api/centros-gestores", {"clave": "CG" + sufijo, "nombre": "Centro"}).json()
        e = self.post(self.admin, "/api/ejes", {"clave": "E", "nombre": "Eje", "centro_gestor_id": a["id"]}).json()
        s = self.post(self.admin, "/api/subtemas", {"clave": "S", "nombre": "Sub", "eje_id": e["id"]}).json()
        es = self.post(self.admin, "/api/estrategias", {"clave": "ES", "nombre": "Est", "subtema_id": s["id"]}).json()
        return a, e, s, es

    def programa(self, clave, cg, ejercicio=EJ, **extra):
        r = self.post(self.admin, "/api/programas", {"ejercicio_fiscal": ejercicio, "clave": clave,
                                                     "nombre": "Prog " + clave, "centro_gestor_id": cg["id"], **extra})
        assert r.status_code == 201, r.text
        return r.json()


@pytest.fixture()
def m(admin):
    return Mun(admin)


# --- caso 2: 403 por tipo ------------------------------------------------------
def test_caso2_tipo_sin_permiso_recibe_403_en_la_api(m):
    for tipo in ("informes", "padron", "presupuestacion", "control_presupuestal", "indicadores", "alcalde"):
        m.usuario("u_" + tipo, tipo)
        c = m.cliente("u_" + tipo, "pw")
        assert m.post(c, "/api/usuarios", {"nombre": "x", "usuario": "x", "tipo": "informes"}).status_code == 403
        assert m.get(c, "/api/usuarios/matriz", params={"ejercicio": EJ}).status_code == 403
        assert m.post(c, "/api/usuarios/bulk", {"filas": []}).status_code == 403
        assert m.get(c, f"/api/usuarios/{uuid.uuid4()}").status_code == 403
        assert m.post(c, f"/api/usuarios/{uuid.uuid4()}/forzar-password").status_code == 403
        assert m.patch(c, f"/api/usuarios/{uuid.uuid4()}", {"nombre": "x"}).status_code == 403


def test_caso2_otros_modulos_por_tipo(m):
    m.usuario("pad", "padron")
    m.usuario("ctrl", "control_presupuestal")
    m.usuario("pres", "presupuestacion")
    pad, ctrl, pres = (m.cliente(u, "pw") for u in ("pad", "ctrl", "pres"))
    assert m.get(pad, "/api/centros-gestores").status_code == 403
    assert m.get(pad, "/api/programas").status_code == 403
    assert m.get(ctrl, "/api/usuarios").status_code == 403          # no tiene el módulo Usuarios
    assert m.get(ctrl, "/api/config").status_code == 403
    assert m.get(pres, "/api/centros-gestores").status_code == 200
    assert m.post(pres, "/api/centros-gestores", {"clave": "x", "nombre": "x"}).status_code == 403
    assert m.post(pres, "/api/frecuencias", {"clave": "x", "nombre": "x"}).status_code == 403
    assert m.get(m.admin, "/api/usuarios").status_code == 200
    # sin sesión: 401
    assert TestClient(app).get("/api/usuarios", headers=m.h).status_code == 401


def test_listado_de_usuarios_lo_ven_cinco_tipos_sin_contrasenas(m):
    m.usuario("inf", "informes")
    c = m.cliente("inf", "pw")
    lista = m.get(c, "/api/usuarios").json()
    assert {u["usuario"] for u in lista} == {"admin1", "inf"}
    assert all("password" not in u for u in lista)
    assert all("ultimo_acceso" in u for u in lista)


# --- caso 3: cambio de tipo, efecto inmediato -----------------------------------
def test_caso3_cambio_de_tipo_aplica_en_la_siguiente_peticion(m):
    u = m.usuario("ana", "informes")
    c = m.cliente("ana", "pw")
    assert m.get(c, "/api/auth/me").json()["usuario"]["tipo"] == "informes"
    assert m.get(c, "/api/config").status_code == 200
    assert m.patch(m.admin, f"/api/usuarios/{u['id']}", {"tipo": "indicadores"}).status_code == 200
    assert m.get(c, "/api/auth/me").json()["usuario"]["tipo"] == "indicadores"  # sin volver a entrar
    assert m.get(c, "/api/config").status_code == 403


def test_cambiar_tipo_no_toca_los_programas(m):
    cg, *_ = m.planeacion()
    p = m.programa("P1", cg)
    u = m.usuario("ana", "informes", programa_ids=[p["id"]])
    assert m.patch(m.admin, f"/api/usuarios/{u['id']}", {"tipo": "presupuestacion"}).json()["programa_ids"] == [p["id"]]


# --- caso 4: solo ve sus programas -----------------------------------------------
def test_caso4_usuario_solo_ve_sus_programas_y_dos_del_mismo_tipo_difieren(m):
    cg, *_ = m.planeacion()
    pa, pb, pc = m.programa("A", cg), m.programa("B", cg), m.programa("C", cg)
    m.usuario("u1", "informes", programa_ids=[pa["id"], pb["id"]])
    m.usuario("u2", "informes", programa_ids=[pc["id"]])
    claves = lambda c: sorted(p["clave"] for p in m.get(c, "/api/programas").json())
    assert claves(m.cliente("u1", "pw")) == ["A", "B"]
    assert claves(m.cliente("u2", "pw")) == ["C"]
    assert claves(m.admin) == ["A", "B", "C"]
    # no puede editar ni duplicar lo que no ve
    assert m.post(m.cliente("u1", "pw"), f"/api/programas/{pc['id']}/duplicar",
                  {"ejercicio_fiscal": 2027, "clave": "Z"}).status_code == 403  # informes no edita
    pres = m.usuario("pres", "presupuestacion", programa_ids=[pa["id"]])
    cp = m.cliente("pres", "pw")
    assert m.patch(cp, f"/api/programas/{pc['id']}", {"nombre": "x"}).status_code == 404
    assert m.patch(cp, f"/api/programas/{pa['id']}", {"nombre": "nuevo"}).status_code == 200


def test_presupuestacion_que_crea_un_programa_lo_recibe_asignado(m):
    cg, *_ = m.planeacion()
    m.usuario("pres", "presupuestacion")
    cp = m.cliente("pres", "pw")
    assert m.get(cp, "/api/programas").json() == []
    r = m.post(cp, "/api/programas", {"ejercicio_fiscal": EJ, "clave": "N", "nombre": "n", "centro_gestor_id": cg["id"]})
    assert r.status_code == 201
    assert [p["clave"] for p in m.get(cp, "/api/programas").json()] == ["N"]


# --- caso 5: contraseña visible + bitácora -----------------------------------------
def test_caso5_admin_ve_la_contrasena_y_queda_en_bitacora(m, db):
    u = m.usuario("ana", "informes", password="Secreta 1")
    r = m.get(m.admin, f"/api/usuarios/{u['id']}")
    assert r.json()["password"] == "Secreta 1"
    consulta = db.scalar(select(Bitacora).where(Bitacora.accion == "usuario.ver_password"))
    assert str(consulta.entidad_id) == u["id"] and consulta.actor_tipo.value == "usuario"
    m.get(m.admin, f"/api/usuarios/{u['id']}")
    assert db.scalar(select(func.count()).select_from(Bitacora).where(
        Bitacora.accion == "usuario.ver_password")) == 2  # cada consulta
    # en base se guarda cifrada, no en claro
    assert db.scalar(select(Usuario.password_encrypted).where(Usuario.usuario == "ana")) != "Secreta 1"


# --- caso 6: matriz ---------------------------------------------------------------
def test_caso6_guardar_matriz_12_altas_3_bajas(m, db):
    cg, *_ = m.planeacion()
    progs = [m.programa(f"P{i}", cg) for i in range(4)]
    us = [m.usuario(f"u{i}", "informes") for i in range(3)]
    altas = [{"usuario_id": u["id"], "programa_id": p["id"]} for u in us for p in progs]  # 12
    r = m.post(m.admin, "/api/usuarios/matriz", {"altas": altas, "bajas": []})
    assert r.json() == {"altas": 12, "bajas": 0, "resumen": "12 asignaciones nuevas, 0 retiradas"}
    bajas = [{"usuario_id": us[0]["id"], "programa_id": p["id"]} for p in progs[:3]]
    r = m.post(m.admin, "/api/usuarios/matriz", {"altas": [], "bajas": bajas})
    assert r.json()["resumen"] == "0 asignaciones nuevas, 3 retiradas"
    assert db.scalar(select(func.count()).select_from(UsuarioPrograma)) == 9
    bit = [b.detalle["resumen"] for b in db.scalars(select(Bitacora).where(Bitacora.accion == "matriz.guardar"))]
    assert "12 asignaciones nuevas, 0 retiradas" in bit and "0 asignaciones nuevas, 3 retiradas" in bit
    g = m.get(m.admin, "/api/usuarios/matriz", params={"ejercicio": EJ}).json()
    assert len(g["programas"]) == 4 and len(g["asignaciones"]) == 9
    assert [c["clave"] for c in g["centros_gestores"]] == ["CG"]


def test_matriz_es_atomica_si_una_celda_es_invalida(m, db):
    cg, *_ = m.planeacion()
    p = m.programa("P", cg)
    u = m.usuario("u", "informes")
    r = m.post(m.admin, "/api/usuarios/matriz", {"altas": [
        {"usuario_id": u["id"], "programa_id": p["id"]},
        {"usuario_id": u["id"], "programa_id": str(uuid.uuid4())}], "bajas": []})
    assert r.status_code == 422 and r.json()["codigo"] == "PROGRAMA_INVALIDO"
    assert db.scalar(select(func.count()).select_from(UsuarioPrograma)) == 0  # ni la válida se guardó


def test_matriz_no_asigna_programas_de_otro_municipio(admin, m):
    otro = Mun(admin, "otro")
    cg, *_ = otro.planeacion()
    ajeno = otro.programa("X", cg)
    u = m.usuario("u", "informes")
    r = m.post(m.admin, "/api/usuarios/matriz", {"altas": [{"usuario_id": u["id"], "programa_id": ajeno["id"]}]})
    assert r.status_code == 422
    r = m.patch(m.admin, f"/api/usuarios/{u['id']}", {"programa_ids": [ajeno["id"]]})
    assert r.status_code == 422


# --- caso 7: alta masiva -------------------------------------------------------
def test_caso7_alta_masiva_con_un_usuario_repetido(m):
    m.usuario("existente", "informes")
    r = m.post(m.admin, "/api/usuarios/bulk", {"filas": [
        {"nombre": "A", "usuario": "a", "tipo": "informes", "email": "a@x.mx"},
        {"nombre": "B", "usuario": "existente", "tipo": "informes"},
        {"nombre": "C", "usuario": "c", "tipo": "alcalde", "password": "1"},
        {"nombre": "D", "usuario": "a", "tipo": "informes"},           # repetido dentro del lote
        {"nombre": "E", "usuario": "e", "tipo": "informes", "email": "malo"},
    ]})
    j = r.json()
    assert [c["usuario"] for c in j["creados"]] == ["a", "c"]
    assert sorted((e["fila"], list(e["campos"])[0]) for e in j["errores"]) == [(1, "usuario"), (3, "usuario"), (4, "email")]
    assert j["creados"][0]["password_generada"] and j["creados"][1]["password_generada"] is None
    assert {u["usuario"] for u in m.get(m.admin, "/api/usuarios").json()} == {"admin1", "existente", "a", "c"}
    # la generada sirve para entrar
    m.cliente("a", j["creados"][0]["password_generada"])


def test_alta_individual_usuario_repetido_409_y_unico_por_municipio(admin, m):
    m.usuario("ana", "informes")
    r = m.post(m.admin, "/api/usuarios", {"nombre": "x", "usuario": "ana", "tipo": "informes"})
    assert (r.status_code, r.json()["codigo"]) == (409, "USUARIO_EXISTE")
    otro = Mun(admin, "otro")
    otro.usuario("ana", "informes")  # el mismo usuario en otro municipio sí es válido


# --- caso 8: duplicar ----------------------------------------------------------
def test_caso8_duplicar_programa_a_otro_ejercicio(m, db):
    cg, e, s, es = m.planeacion()
    p = m.programa("P1", cg, subtema_id=s["id"], estrategia_id=es["id"])
    antes = dict(m.get(m.admin, "/api/programas").json()[0])
    d = m.post(m.admin, f"/api/programas/{p['id']}/duplicar", {"ejercicio_fiscal": 2027, "clave": "P1-27"})
    assert d.status_code == 201
    n = d.json()
    assert (n["ejercicio_fiscal"], n["clave"], n["id"] != p["id"]) == (2027, "P1-27", True)
    # reutiliza (no duplica) centro gestor, subtema y estrategia
    assert (n["centro_gestor_id"], n["subtema_id"], n["estrategia_id"]) == (cg["id"], s["id"], es["id"])
    assert len(m.get(m.admin, "/api/centros-gestores").json()) == 1
    assert [x for x in m.get(m.admin, "/api/programas", params={"ejercicio": EJ}).json()] == [antes]  # original intacto
    # misma clave del origen: rechazado
    r = m.post(m.admin, f"/api/programas/{p['id']}/duplicar", {"ejercicio_fiscal": 2028, "clave": "P1"})
    assert r.json()["codigo"] == "CLAVE_REPETIDA"
    r = m.post(m.admin, f"/api/programas/{p['id']}/duplicar", {"ejercicio_fiscal": 2027, "clave": "P1-27"})
    assert r.status_code == 409


def test_programa_clave_unica_por_ejercicio(m):
    cg, *_ = m.planeacion()
    m.programa("P1", cg)
    r = m.post(m.admin, "/api/programas", {"ejercicio_fiscal": EJ, "clave": "P1", "nombre": "x", "centro_gestor_id": cg["id"]})
    assert r.status_code == 409
    m.programa("P1", cg, ejercicio=2027)  # otro ejercicio sí


def test_programa_con_jerarquia_inconsistente(m):
    cg, e, s, es = m.planeacion()
    cg2 = m.post(m.admin, "/api/centros-gestores", {"clave": "CG2", "nombre": "Otro"}).json()
    r = m.post(m.admin, "/api/programas", {"ejercicio_fiscal": EJ, "clave": "Z", "nombre": "z",
                                           "centro_gestor_id": cg2["id"], "subtema_id": s["id"]})
    assert (r.status_code, r.json()["codigo"]) == (422, "JERARQUIA_INVALIDA")


def test_clasificacion_programatica_es_tabla_propia_y_se_asigna(m):
    cg, *_ = m.planeacion()
    cl = m.get(m.admin, "/api/clasificaciones-programaticas").json()
    assert {c["clave"] for c in cl} >= {"especificos", "proyectos_inversion", "servicios_publicos"}
    p = m.programa("P", cg, clasificacion_programatica_id=cl[0]["id"])
    assert p["clasificacion_programatica_id"] == cl[0]["id"]


# --- caso 9: baja lógica -------------------------------------------------------
def test_caso9_deshabilitar_en_uso_no_rompe_el_historico(m):
    cg, e, s, es = m.planeacion()
    p = m.programa("P1", cg, subtema_id=s["id"], estrategia_id=es["id"])
    for ruta, o in (("centros-gestores", cg), ("ejes", e), ("subtemas", s), ("estrategias", es)):
        assert m.patch(m.admin, f"/api/{ruta}/{o['id']}", {"activo": False}).json()["activo"] is False
        assert o["id"] not in [x["id"] for x in m.get(m.admin, f"/api/{ruta}", params={"activo": True}).json()]
        assert o["id"] in [x["id"] for x in m.get(m.admin, f"/api/{ruta}").json()]  # el histórico sigue ahí
    assert m.patch(m.admin, f"/api/programas/{p['id']}", {"activo": False}).json()["activo"] is False
    assert m.get(m.admin, "/api/programas", params={"activo": True}).json() == []
    prog = m.get(m.admin, "/api/programas").json()[0]
    assert (prog["centro_gestor_id"], prog["subtema_id"]) == (cg["id"], s["id"])  # referencias intactas
    # lo deshabilitado no admite colgar cosas nuevas
    r = m.post(m.admin, "/api/ejes", {"clave": "E2", "nombre": "x", "centro_gestor_id": cg["id"]})
    assert r.status_code == 422
    r = m.post(m.admin, "/api/programas", {"ejercicio_fiscal": EJ, "clave": "N", "nombre": "x", "centro_gestor_id": cg["id"]})
    assert r.status_code == 422
    # no existe DELETE
    assert m.admin.delete(f"/api/centros-gestores/{cg['id']}", headers=m.h).status_code == 405


def test_catalogos_clave_unica_y_permisos_de_edicion(m):
    m.usuario("alc", "alcalde")
    alc = m.cliente("alc", "pw")
    assert m.post(alc, "/api/centros-gestores", {"clave": "A", "nombre": "x"}).status_code == 201
    assert m.post(alc, "/api/centros-gestores", {"clave": "A", "nombre": "y"}).status_code == 409
    f = m.get(alc, "/api/frecuencias").json()
    assert {x["clave"] for x in f} >= {"mensual", "anual"}
    assert m.patch(alc, f"/api/frecuencias/{f[0]['id']}", {"nombre": "Renombrada"}).json()["nombre"] == "Renombrada"


# --- caso 10: deshabilitado pierde acceso ----------------------------------------
def test_caso10_usuario_deshabilitado_pierde_acceso_y_sesiones_revocadas(m, db):
    u = m.usuario("ana", "informes")
    c = m.cliente("ana", "pw")
    assert m.get(c, "/api/auth/me").status_code == 200
    assert m.patch(m.admin, f"/api/usuarios/{u['id']}", {"activo": False}).status_code == 200
    assert m.get(c, "/api/auth/me").status_code == 401
    db.expire_all()
    assert all(s.revoked_at for s in db.scalars(select(Sesion).where(Sesion.usuario_id == uuid.UUID(u["id"]))))
    r = m.post(TestClient(app), "/api/auth/login", {"usuario": "ana", "password": "pw"})
    assert r.json()["codigo"] == "USUARIO_INACTIVO"


def test_forzar_password_revoca_sesiones_y_no_obliga_a_cambiarla(m):
    u = m.usuario("ana", "informes")
    c = m.cliente("ana", "pw")
    nueva = m.post(m.admin, f"/api/usuarios/{u['id']}/forzar-password").json()["password"]
    assert m.get(c, "/api/auth/me").status_code == 401
    c2 = m.cliente("ana", nueva)  # entra directo, sin pantalla de cambio obligatorio
    me = m.get(c2, "/api/auth/me").json()["usuario"]
    assert me["debe_cambiar_password"] is True  # solo informativo
    assert m.get(c2, "/api/config").status_code == 200
    assert m.get(m.admin, f"/api/usuarios/{u['id']}").json()["password"] == nueva


def test_cambio_voluntario_de_contrasena(m):
    m.usuario("ana", "informes")
    c = m.cliente("ana", "pw")
    assert m.post(c, "/api/auth/cambiar-password", {"password_actual": "mal", "password_nueva": "n"}).status_code == 403
    assert m.post(c, "/api/auth/cambiar-password", {"password_actual": "pw", "password_nueva": "n"}).status_code == 200
    assert m.get(c, "/api/auth/me").json()["usuario"]["debe_cambiar_password"] is False
    m.cliente("ana", "n")


def test_administrador_no_puede_deshabilitarse_a_si_mismo(m):
    yo = m.get(m.admin, "/api/auth/me").json()["usuario"]["id"]
    r = m.patch(m.admin, f"/api/usuarios/{yo}", {"activo": False})
    assert (r.status_code, r.json()["codigo"]) == (409, "AUTOBLOQUEO")


# --- aislamiento entre municipios --------------------------------------------------
def test_un_admin_no_ve_ni_toca_usuarios_de_otro_municipio(admin, m):
    otro = Mun(admin, "otro")
    ajeno = otro.usuario("zed", "informes")
    assert {u["usuario"] for u in m.get(m.admin, "/api/usuarios").json()} == {"admin1"}
    assert m.get(m.admin, f"/api/usuarios/{ajeno['id']}").status_code == 404
    assert m.patch(m.admin, f"/api/usuarios/{ajeno['id']}", {"nombre": "x"}).status_code == 404
    # y la sesión de un municipio no sirve en el subdominio de otro
    assert m.admin.get("/api/usuarios", headers=otro.h).status_code == 403


# --- super admin: usuarios de cualquier municipio --------------------------------------
def test_super_admin_gestiona_usuarios_de_cualquier_municipio_y_tipo(admin, m, db):
    base = f"/api/admin/municipios/{m.id}/usuarios"
    r = admin.post(base, headers=ADMIN, json={"nombre": "Otro Admin", "usuario": "adm2",
                                              "tipo": "administrador", "password": "p2"})
    assert r.status_code == 201
    uid = r.json()["id"]
    m.cliente("adm2", "p2")
    assert {u["usuario"] for u in admin.get(base, headers=ADMIN).json()} == {"admin1", "adm2"}
    assert admin.get(f"{base}/{uid}", headers=ADMIN).json()["password"] == "p2"
    assert admin.patch(f"{base}/{uid}", headers=ADMIN, json={"tipo": "alcalde"}).json()["tipo"] == "alcalde"
    nueva = admin.post(f"{base}/{uid}/forzar-password", headers=ADMIN).json()["password"]
    m.cliente("adm2", nueva)
    acciones = {b.accion: b.actor_tipo.value for b in db.scalars(select(Bitacora).where(
        Bitacora.accion.like("usuario.%")))}
    assert acciones["usuario.crear"] == "super_admin"
    assert acciones["usuario.ver_password"] == "super_admin"
    assert acciones["usuario.forzar_password"] == "super_admin"


def test_super_admin_no_cruza_municipios_y_sesiones_no_son_intercambiables(admin, m):
    otro = Mun(admin, "otro")
    uid = otro.usuario("zed", "informes")["id"]
    # el usuario zed es de "otro": desde la ruta de "demo" no existe
    assert admin.get(f"/api/admin/municipios/{m.id}/usuarios/{uid}", headers=ADMIN).status_code == 404
    assert admin.get(f"/api/admin/municipios/{uuid.uuid4()}/usuarios", headers=ADMIN).status_code == 404
    # un administrador de municipio no entra a los endpoints espejo (ámbito admin)
    assert m.admin.get(f"/api/admin/municipios/{m.id}/usuarios", headers=ADMIN).status_code == 401
    assert m.admin.get(f"/api/admin/municipios/{m.id}/usuarios", headers=m.h).status_code == 403


# --- configuración -----------------------------------------------------------------
def test_config_meses_de_avance_y_permisos(m):
    m.usuario("alc", "alcalde")
    m.usuario("inf", "informes")
    alc, inf = m.cliente("alc", "pw"), m.cliente("inf", "pw")
    assert m.get(m.admin, "/api/config").json()["meses_avance_activos"] == []
    r = m.patch(alc, "/api/config", {"meses_avance_activos": [3, 1, 2], "tolerancia_semaforo": 5})
    assert (r.json()["meses_avance_activos"], r.json()["tolerancia_semaforo"]) == ([1, 2, 3], 5)
    assert m.patch(inf, "/api/config", {"meses_avance_activos": [1]}).status_code == 403
    assert m.patch(alc, "/api/config", {"color_boton": "danger"}).status_code == 403
    assert m.patch(inf, "/api/config", {"color_boton": "danger", "mostrar_logos": False}).status_code == 200
    assert m.patch(m.admin, "/api/config", {"meses_avance_activos": [13]}).status_code == 422
    assert m.get(inf, "/api/config").json()["meses_avance_activos"] == [1, 2, 3]


# --- recuperación de contraseña ----------------------------------------------------------
def _token(correos):
    return correos[-1]["html"].split("token=")[1].split('"')[0]


def test_recuperar_responde_200_siempre_y_solo_envia_si_hay_email(m, correos):
    m.usuario("conmail", "informes", email="ana@x.mx")
    m.usuario("sinmail", "informes")
    for u in ("fantasma", "sinmail"):
        assert m.post(TestClient(app), "/api/auth/recuperar", {"usuario": u}).json() == {"ok": True}
    assert correos == []
    assert m.post(TestClient(app), "/api/auth/recuperar", {"usuario": "conmail"}).json() == {"ok": True}
    assert len(correos) == 1 and correos[0]["para"] == "ana@x.mx"
    assert "demo.localtest.me/recuperar?token=" in correos[0]["html"]


def test_recuperar_confirmar_cambia_contrasena_revoca_sesiones_y_el_token_es_de_un_uso(m, correos, db):
    m.usuario("ana", "informes", email="ana@x.mx")
    c = m.cliente("ana", "pw")
    m.post(TestClient(app), "/api/auth/recuperar", {"usuario": "ana"})
    token = _token(correos)
    guardado = db.scalar(select(PasswordResetToken.token_hash))
    assert guardado != token and token not in guardado  # solo se guarda el hash
    r = m.post(TestClient(app), "/api/auth/recuperar/confirmar", {"token": token, "password_nueva": "nueva"})
    assert r.status_code == 200
    assert m.get(c, "/api/auth/me").status_code == 401  # sesiones abiertas revocadas
    m.cliente("ana", "nueva")
    db.expire_all()
    assert db.scalar(select(Usuario.debe_cambiar_password).where(Usuario.usuario == "ana")) is False
    r = m.post(TestClient(app), "/api/auth/recuperar/confirmar", {"token": token, "password_nueva": "otra"})
    assert r.json()["codigo"] == "TOKEN_USADO"


def test_recuperar_token_vencido_invalido_y_solo_el_ultimo_enlace_sirve(m, correos, db):
    from datetime import timedelta
    m.usuario("ana", "informes", email="ana@x.mx")
    cli = TestClient(app)
    m.post(cli, "/api/auth/recuperar", {"usuario": "ana"})
    primero = _token(correos)
    m.post(cli, "/api/auth/recuperar", {"usuario": "ana"})
    segundo = _token(correos)
    assert m.post(cli, "/api/auth/recuperar/confirmar", {"token": primero, "password_nueva": "x"}).json()["codigo"] == "TOKEN_USADO"
    t = db.scalar(select(PasswordResetToken).where(PasswordResetToken.used_at.is_(None)))
    t.expires_at = t.expires_at - timedelta(hours=2)
    db.commit()
    assert m.post(cli, "/api/auth/recuperar/confirmar", {"token": segundo, "password_nueva": "x"}).json()["codigo"] == "TOKEN_VENCIDO"
    assert m.post(cli, "/api/auth/recuperar/confirmar", {"token": "basura", "password_nueva": "x"}).json()["codigo"] == "TOKEN_INVALIDO"


def test_recuperar_no_funciona_con_usuario_deshabilitado(m, correos):
    u = m.usuario("ana", "informes", email="ana@x.mx")
    m.patch(m.admin, f"/api/usuarios/{u['id']}", {"activo": False})
    m.post(TestClient(app), "/api/auth/recuperar", {"usuario": "ana"})
    assert correos == []


def test_el_token_de_un_municipio_no_sirve_en_otro(admin, m, correos):
    otro = Mun(admin, "otro")
    m.usuario("ana", "informes", email="ana@x.mx")
    m.post(TestClient(app), "/api/auth/recuperar", {"usuario": "ana"})
    r = otro.post(TestClient(app), "/api/auth/recuperar/confirmar", {"token": _token(correos), "password_nueva": "x"})
    assert r.json()["codigo"] == "TOKEN_INVALIDO"
