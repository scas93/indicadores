"""Casos de aceptación de la spec (tabla 'Criterios de aceptación'), vía API."""
import uuid

from sqlalchemy import func, select

from app.models import (Bitacora, CatalogoMunicipio, ClasificacionProgramatica, Frecuencia,
                        GeografiaEstado, GeografiaLocalidad,
                        GeografiaMunicipio, Municipio, Sesion, Usuario)
from app.security import decrypt_password

from .conftest import ADMIN, crear_municipio, mun


def login(client, slug, usuario="admin1", password="pw1"):
    return client.post("/api/auth/login", headers=mun(slug),
                       json={"usuario": usuario, "password": password})


# --- caso 1 ----------------------------------------------------------------
def test_alta_de_municipio_deja_admin_listo_y_plantillas_copiadas(admin, db):
    r = crear_municipio(admin, "demo")
    assert r.status_code == 201, r.text
    assert login(admin, "demo").status_code == 200
    me = admin.get("/api/auth/me", headers=mun("demo")).json()
    assert me["usuario"]["tipo"] == "administrador"
    assert me["municipio"]["subdominio"] == "demo"
    mid = uuid.UUID(r.json()["municipio"]["id"])
    tipos = dict(db.execute(select(CatalogoMunicipio.tipo, func.count()).where(
        CatalogoMunicipio.municipio_id == mid).group_by(CatalogoMunicipio.tipo)).all())
    for t in ("dimension", "algoritmo", "grupo_edad", "nivel_socioeconomico",
              "conac_capitulo", "conac_partida"):
        assert tipos.get(t), f"no se copió {t}"
    # Fase 1: frecuencia y clasificación programática son tablas propias, no filas genéricas
    assert "frecuencia" not in tipos and "clasificacion_programatica" not in tipos
    assert db.scalar(select(func.count()).select_from(Frecuencia).where(
        Frecuencia.municipio_id == mid)) > 0
    assert db.scalar(select(func.count()).select_from(ClasificacionProgramatica).where(
        ClasificacionProgramatica.municipio_id == mid)) > 0
    assert db.scalar(select(func.count()).select_from(Bitacora).where(
        Bitacora.accion == "municipio.crear")) == 1


def test_copia_de_conac_conserva_jerarquia_y_geografia_solo_del_estado(admin, db):
    est = db.scalar(select(GeografiaEstado).where(GeografiaEstado.clave == "11"))
    otro = db.scalar(select(GeografiaEstado).where(GeografiaEstado.clave == "14"))
    gm = GeografiaMunicipio(estado_id=est.id, clave="003", nombre="Apaseo el Alto")
    gm2 = GeografiaMunicipio(estado_id=otro.id, clave="120", nombre="Zapopan")
    db.add_all([gm, gm2])
    db.flush()
    db.add(GeografiaLocalidad(municipio_geo_id=gm.id, clave="0001", nombre="Apaseo el Alto"))
    db.add(GeografiaLocalidad(municipio_geo_id=gm2.id, clave="0001", nombre="Zapopan"))
    db.commit()
    r = crear_municipio(admin, "gto", estado=str(est.id))
    mid = uuid.UUID(r.json()["municipio"]["id"])
    geo = db.scalars(select(CatalogoMunicipio).where(
        CatalogoMunicipio.municipio_id == mid, CatalogoMunicipio.tipo.like("geo_%"))).all()
    assert sorted(g.nombre for g in geo) == ["Apaseo el Alto", "Apaseo el Alto"]  # municipio + localidad
    pe = db.scalar(select(CatalogoMunicipio).where(
        CatalogoMunicipio.municipio_id == mid, CatalogoMunicipio.tipo == "conac_partida_especifica",
        CatalogoMunicipio.clave == "2213"))
    partida = db.get(CatalogoMunicipio, pe.padre_id)
    assert (partida.tipo, partida.clave) == ("conac_partida", "221")


def test_editar_plantilla_global_no_toca_copias_existentes(admin, db):
    mid = uuid.UUID(crear_municipio(admin, "demo").json()["municipio"]["id"])
    fid = [f for f in admin.get("/api/admin/plantillas/frecuencia", headers=ADMIN).json()
           if f["clave"] == "mensual"][0]["id"]
    assert admin.patch(f"/api/admin/plantillas/frecuencia/{fid}", headers=ADMIN,
                       json={"nombre": "Cada mes"}).status_code == 200
    copia = db.scalar(select(Frecuencia).where(
        Frecuencia.municipio_id == mid, Frecuencia.clave == "mensual"))
    assert copia.nombre == "Mensual"


def test_password_generada_se_devuelve_una_vez_y_sirve(admin):
    r = admin.post("/api/admin/municipios", headers=ADMIN, json={
        "nombre": "Gen", "subdominio": "gen", "admin_nombre": "A", "admin_usuario": "u",
        "admin_password": ""})
    pw = r.json()["password_inicial"]
    assert pw
    assert login(admin, "gen", "u", pw).status_code == 200


# --- caso 2 ----------------------------------------------------------------
def test_alta_con_subdominio_usado_409_y_no_crea_nada(admin, db):
    assert crear_municipio(admin, "demo").status_code == 201
    antes = (db.scalar(select(func.count()).select_from(Municipio)),
             db.scalar(select(func.count()).select_from(Usuario)),
             db.scalar(select(func.count()).select_from(CatalogoMunicipio)))
    r = crear_municipio(admin, "DEMO", admin_usuario="otro")
    assert r.status_code == 409 and r.json()["codigo"] == "SUBDOMINIO_EN_USO"
    db.expire_all()
    despues = (db.scalar(select(func.count()).select_from(Municipio)),
               db.scalar(select(func.count()).select_from(Usuario)),
               db.scalar(select(func.count()).select_from(CatalogoMunicipio)))
    assert antes == despues


def test_alta_con_subdominio_reservado_o_invalido_422(admin):
    assert crear_municipio(admin, "admin").status_code == 422
    assert crear_municipio(admin, "api").status_code == 422
    assert crear_municipio(admin, "mal nombre").status_code == 422


def test_alta_que_falla_a_mitad_revierte_todo(admin, db, monkeypatch):
    from app.services import municipios as svc

    def boom(*a, **k):
        raise RuntimeError("falla al cifrar")
    monkeypatch.setattr(svc, "encrypt_password", boom)
    try:
        crear_municipio(admin, "roto")
    except RuntimeError:
        pass
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(Municipio)) == 0
    assert db.scalar(select(func.count()).select_from(CatalogoMunicipio)) == 0


def test_disponibilidad_en_vivo(admin):
    crear_municipio(admin, "demo")
    g = lambda v: admin.get("/api/admin/municipios/subdominio-disponible", headers=ADMIN,
                            params={"valor": v}).json()
    assert g("libre")["disponible"]
    assert g("demo")["motivo"] == "SUBDOMINIO_EN_USO"
    assert g("admin")["motivo"] == "SUBDOMINIO_RESERVADO"


# --- caso 3 ----------------------------------------------------------------
def test_subdominio_inexistente_da_404_nunca_login(client):
    for path in ("/api/auth/branding", "/api/auth/me"):
        r = client.get(path, headers=mun("noexiste"))
        assert r.status_code == 404 and r.json()["codigo"] == "MUNICIPIO_NO_ENCONTRADO"
    r = login(client, "noexiste")
    assert r.status_code == 404


# --- caso 4 ----------------------------------------------------------------
def test_suspender_bloquea_login_y_sesiones_abiertas(admin):
    mid = crear_municipio(admin, "demo").json()["municipio"]["id"]
    assert login(admin, "demo").status_code == 200
    assert admin.get("/api/auth/me", headers=mun("demo")).status_code == 200
    r = admin.patch(f"/api/admin/municipios/{mid}", headers=ADMIN, json={"estado": "suspendido"})
    assert r.status_code == 200
    for resp in (admin.get("/api/auth/me", headers=mun("demo")),
                 admin.get("/api/auth/branding", headers=mun("demo")), login(admin, "demo")):
        assert resp.status_code == 403 and resp.json()["codigo"] == "MUNICIPIO_SUSPENDIDO"
    admin.patch(f"/api/admin/municipios/{mid}", headers=ADMIN, json={"estado": "activo"})
    assert admin.get("/api/auth/me", headers=mun("demo")).status_code == 200


# --- caso 5 ----------------------------------------------------------------
def test_sesion_de_un_municipio_no_sirve_en_otro(admin):
    crear_municipio(admin, "a", admin_usuario="ua", password="pa")
    crear_municipio(admin, "b", admin_usuario="ub", password="pb")
    assert login(admin, "a", "ua", "pa").status_code == 200
    cookie_a = admin.cookies.get("sesion_municipio")
    admin.cookies.clear()
    admin.cookies.set("sesion_municipio", cookie_a)
    assert admin.get("/api/auth/me", headers=mun("a")).status_code == 200
    r = admin.get("/api/auth/me", headers=mun("b"))
    assert r.status_code == 403 and r.json()["codigo"] == "MUNICIPIO_NO_COINCIDE"
    assert admin.post("/api/auth/logout", headers=mun("b")).status_code == 403


def test_usuario_con_mismo_nombre_en_dos_municipios_no_se_mezcla(admin):
    crear_municipio(admin, "a", admin_usuario="admin", password="pa")
    crear_municipio(admin, "b", admin_usuario="admin", password="pb")
    assert login(admin, "a", "admin", "pb").status_code == 401  # contraseña de B en A
    assert login(admin, "b", "admin", "pb").status_code == 200


# --- caso 6 ----------------------------------------------------------------
def test_sesion_admin_no_abre_api_de_municipio_y_viceversa(admin):
    crear_municipio(admin, "demo")
    login(admin, "demo")
    cookie_admin = admin.cookies.get("sesion_admin")
    cookie_mun = admin.cookies.get("sesion_municipio")

    # super admin presentado como cookie de municipio
    admin.cookies.clear()
    admin.cookies.set("sesion_municipio", cookie_admin)
    r = admin.get("/api/auth/me", headers=mun("demo"))
    assert r.status_code == 401 and r.json()["codigo"] == "SESION_INVALIDA"

    # usuario de municipio presentado como cookie de admin
    admin.cookies.clear()
    admin.cookies.set("sesion_admin", cookie_mun)
    r = admin.get("/api/admin/municipios", headers=ADMIN)
    assert r.status_code == 401 and r.json()["codigo"] == "SESION_INVALIDA"

    # cada cookie en su ámbito correcto sí funciona; cruzar subdominio de ámbito no
    admin.cookies.clear()
    admin.cookies.set("sesion_admin", cookie_admin)
    assert admin.get("/api/admin/municipios", headers=ADMIN).status_code == 200
    assert admin.get("/api/admin/municipios", headers=mun("demo")).status_code == 403
    assert admin.post("/api/admin/auth/login", headers=mun("demo"),
                      json={"usuario": "root", "password": "super-secreta"}).status_code == 403
    assert admin.post("/api/auth/login", headers=ADMIN,
                      json={"usuario": "x", "password": "y"}).status_code == 403


def test_endpoints_admin_exigen_sesion(client):
    assert client.get("/api/admin/municipios", headers=ADMIN).status_code == 401
    assert client.get("/api/admin/plantillas/frecuencia", headers=ADMIN).status_code == 401
    assert client.get("/api/admin/municipios").status_code == 403  # sin ámbito


def test_login_super_admin_con_credenciales_malas(client):
    r = client.post("/api/admin/auth/login", headers=ADMIN,
                    json={"usuario": "root", "password": "mala"})
    assert r.status_code == 401


# --- caso 7 ----------------------------------------------------------------
def test_password_de_usuario_recien_creado_es_recuperable(admin, db):
    crear_municipio(admin, "demo", password="Mi clave 123")
    u = db.scalar(select(Usuario).where(Usuario.usuario == "admin1"))
    assert u.password_encrypted != "Mi clave 123"
    assert decrypt_password(u.password_encrypted) == "Mi clave 123"


# --- caso 8 ----------------------------------------------------------------
def test_sesion_vence_sin_cerrar_sesion(admin, monkeypatch):
    crear_municipio(admin, "demo")
    assert login(admin, "demo").status_code == 200
    assert admin.get("/api/auth/me", headers=mun("demo")).status_code == 200
    # El vencimiento lo decide el servidor (sesion.expires_at), no el cliente
    from app.db import new_session
    with new_session() as s:
        for ses in s.scalars(select(Sesion).where(Sesion.usuario_id.is_not(None))):
            from datetime import timedelta
            ses.expires_at = ses.expires_at - timedelta(days=31)
        s.commit()
    r = admin.get("/api/auth/me", headers=mun("demo"))
    assert r.status_code == 401 and r.json()["codigo"] == "SESION_EXPIRADA"


def test_duracion_en_minutos_override_para_pruebas(admin, monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("SESION_DURACION_MINUTOS_OVERRIDE", "1")
    get_settings.cache_clear()
    try:
        crear_municipio(admin, "demo")
        r = login(admin, "demo")
        from datetime import datetime, timezone
        exp = datetime.fromisoformat(r.json()["expira"])
        assert 0 < (exp - datetime.now(timezone.utc)).total_seconds() <= 60
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


def test_duracion_sesion_es_parametro_del_municipio(admin):
    mid = crear_municipio(admin, "demo").json()["municipio"]["id"]
    assert admin.patch(f"/api/admin/municipios/{mid}", headers=ADMIN,
                       json={"duracion_sesion_dias": 0}).status_code == 422
    assert admin.patch(f"/api/admin/municipios/{mid}", headers=ADMIN,
                       json={"duracion_sesion_dias": 7}).json()["duracion_sesion_dias"] == 7


# --- sesión y revocación -----------------------------------------------------
def test_logout_revoca_la_sesion(admin):
    crear_municipio(admin, "demo")
    login(admin, "demo")
    cookie = admin.cookies.get("sesion_municipio")
    assert admin.post("/api/auth/logout", headers=mun("demo")).status_code == 200
    admin.cookies.set("sesion_municipio", cookie)  # el navegador "reusa" la cookie vieja
    assert admin.get("/api/auth/me", headers=mun("demo")).status_code == 401


def test_cookie_manipulada_se_rechaza(admin):
    crear_municipio(admin, "demo")
    login(admin, "demo")
    c = admin.cookies.get("sesion_municipio")
    admin.cookies.clear()
    admin.cookies.set("sesion_municipio", c[:-3] + "AAA")
    assert admin.get("/api/auth/me", headers=mun("demo")).status_code == 401


def test_cookie_es_httponly_samesite_lax(client, admin):
    crear_municipio(client, "demo")
    r = login(client, "demo")
    sc = r.headers["set-cookie"].lower()
    assert "httponly" in sc and "samesite=lax" in sc and "max-age=" in sc


def test_login_credenciales_y_usuario_inactivo(admin, db):
    crear_municipio(admin, "demo")
    assert login(admin, "demo", "admin1", "mala").status_code == 401
    assert login(admin, "demo", "fantasma", "x").status_code == 401
    assert admin.post("/api/auth/verificar-usuario", headers=mun("demo"),
                      json={"usuario": "fantasma"}).status_code == 404
    assert admin.post("/api/auth/verificar-usuario", headers=mun("demo"),
                      json={"usuario": "admin1"}).json()["nombre"] == "Admin demo"
    u = db.scalar(select(Usuario))
    u.activo = False
    db.commit()
    assert login(admin, "demo").json()["codigo"] == "USUARIO_INACTIVO"


def test_login_nunca_obliga_ni_apaga_debe_cambiar_password(admin, db):
    """Decisión de producto: la bandera es solo informativa; el login no la toca."""
    crear_municipio(admin, "demo")
    assert db.scalar(select(Usuario.debe_cambiar_password)) is True
    assert login(admin, "demo").status_code == 200
    db.expire_all()
    assert db.scalar(select(Usuario.debe_cambiar_password)) is True
    me = admin.get("/api/auth/me", headers=mun("demo")).json()
    assert me["usuario"]["debe_cambiar_password"] is True


def test_branding_expone_solo_lo_necesario(admin):
    mid = crear_municipio(admin, "demo").json()["municipio"]["id"]
    admin.patch(f"/api/admin/municipios/{mid}", headers=ADMIN,
                json={"color_boton": "success", "mostrar_logos": False, "imagen_login_url": "/x.png"})
    b = admin.get("/api/auth/branding", headers=mun("demo")).json()
    assert b == {"nombre": "Demo", "logo_url": None, "imagen_login_url": "/x.png",
                 "color_boton": "success", "mostrar_logos": False}


# --- plantillas globales -------------------------------------------------------
def test_plantillas_crud_y_borrado_solo_si_nadie_referencia(admin):
    c = admin.post("/api/admin/plantillas/frecuencia", headers=ADMIN,
                   json={"clave": "decenal", "nombre": "Decenal"})
    assert c.status_code == 201
    assert admin.post("/api/admin/plantillas/frecuencia", headers=ADMIN,
                      json={"clave": "decenal", "nombre": "Otra"}).status_code == 409
    assert admin.delete(f"/api/admin/plantillas/frecuencia/{c.json()['id']}",
                        headers=ADMIN).status_code == 204

    est = admin.get("/api/admin/plantillas/geografia", headers=ADMIN, params={"nivel": "estado"}).json()
    gto = [e for e in est if e["clave"] == "11"][0]
    assert len(est) == 32
    crear_municipio(admin, "demo", estado=gto["id"])
    r = admin.delete(f"/api/admin/plantillas/geografia/{gto['id']}", headers=ADMIN)
    assert r.status_code == 409 and r.json()["codigo"] == "REGISTRO_EN_USO"  # lo usa un municipio

    cap = [x for x in admin.get("/api/admin/plantillas/conac", headers=ADMIN,
                                params={"nivel": "capitulo"}).json() if x["clave"] == "2000"][0]
    r = admin.delete(f"/api/admin/plantillas/conac/{cap['id']}", headers=ADMIN)
    assert r.status_code == 409  # tiene partidas hijas


def test_plantilla_tipo_desconocido_404(admin):
    assert admin.get("/api/admin/plantillas/nada", headers=ADMIN).status_code == 404


def test_error_de_validacion_trae_detalle_por_campo(admin):
    r = admin.post("/api/admin/municipios", headers=ADMIN, json={"nombre": ""})
    assert r.status_code == 422
    assert "nombre" in r.json()["campos"] and "admin_usuario" in r.json()["campos"]


def test_subida_de_imagen_valida_tipo(admin):
    ok = admin.post("/api/admin/uploads/imagen", headers=ADMIN,
                    files={"archivo": ("l.png", b"\x89PNG....", "image/png")})
    assert ok.status_code == 201 and ok.json()["url"].startswith("/api/media/img/")
    bad = admin.post("/api/admin/uploads/imagen", headers=ADMIN,
                     files={"archivo": ("l.html", b"<script>", "text/html")})
    assert bad.status_code == 422


def test_plantilla_con_jerarquia_acepta_ids_como_texto(admin):
    cap = [x for x in admin.get("/api/admin/plantillas/conac", headers=ADMIN,
                                params={"nivel": "capitulo"}).json() if x["clave"] == "3000"][0]
    r = admin.post("/api/admin/plantillas/conac", headers=ADMIN, json={
        "clave": "311", "nombre": "Energía eléctrica", "nivel": "partida", "padre_id": cap["id"]})
    assert r.status_code == 201 and r.json()["padre_id"] == cap["id"]
    r = admin.post("/api/admin/plantillas/conac", headers=ADMIN, json={
        "clave": "312", "nombre": "x", "nivel": "partida", "padre_id": "no-es-uuid"})
    assert r.status_code == 422
