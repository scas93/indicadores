"""Fase 1 — reglas de negocio de usuarios, permisos, matriz y config (funciones puras)."""
import uuid

import pytest

from app import validators_usuarios as vu
from app.errors import ApiError

U1, U2, P1, P2, P3 = (uuid.uuid4() for _ in range(5))
TIPOS = ["informes", "padron", "presupuestacion", "control_presupuestal", "indicadores", "alcalde",
         "administrador"]


def fila(**kw):
    return {"nombre": "Ana", "usuario": "ana", "tipo": "informes", **kw}


# --- caso 2: acceso directo por URL a un módulo no permitido -> 403 ----------
def test_son_7_tipos():
    assert vu.TIPOS == set(TIPOS)


@pytest.mark.parametrize("tipo", [t for t in TIPOS if t != "administrador"])
def test_solo_administrador_gestiona_usuarios(tipo):
    with pytest.raises(ApiError) as e:
        vu.validar_tipo_permitido("usuarios_gestion", tipo)
    assert (e.value.status, e.value.codigo) == (403, "TIPO_NO_PERMITIDO")


def test_administrador_gestiona_usuarios():
    vu.validar_tipo_permitido("usuarios_gestion", "administrador")


def test_super_admin_sin_tipo_no_pasa_por_validar_tipo():
    # el super admin usa endpoints espejo de otro ámbito; un tipo None jamás está permitido aquí
    assert not vu.tipo_permitido("usuarios_gestion", None)


@pytest.mark.parametrize("tipo,esperado", [
    ("informes", True), ("padron", True), ("presupuestacion", True), ("indicadores", True),
    ("alcalde", True), ("administrador", True), ("control_presupuestal", False)])
def test_quien_ve_el_listado_de_usuarios(tipo, esperado):
    assert vu.tipo_permitido("usuarios_ver", tipo) is esperado


def test_edicion_de_planeacion_y_programas():
    assert {t for t in TIPOS if vu.tipo_permitido("planeacion_editar", t)} == {"alcalde", "administrador"}
    assert {t for t in TIPOS if vu.tipo_permitido("programas_editar", t)} == {
        "alcalde", "presupuestacion", "administrador"}
    assert not vu.tipo_permitido("planeacion_ver", "padron")


def test_config_meses_solo_admin_y_alcalde_login_informes_y_admin():
    vu.validar_campos_config("alcalde", ["meses_avance_activos"])
    vu.validar_campos_config("informes", ["color_boton", "mostrar_logos"])
    for tipo, campo in [("informes", "meses_avance_activos"), ("alcalde", "color_boton"),
                        ("presupuestacion", "tolerancia_semaforo")]:
        with pytest.raises(ApiError) as e:
            vu.validar_campos_config(tipo, [campo])
        assert e.value.status == 403


# --- caso 4: programas visibles por usuario ----------------------------------
def test_programas_visibles_dos_usuarios_del_mismo_tipo_ven_distinto():
    assert vu.programas_visibles("informes", [P1, P2]) == {P1, P2}
    assert vu.programas_visibles("informes", [P3]) == {P3}
    assert vu.programas_visibles("informes", []) == frozenset()  # sin asignar: no ve ninguno


def test_administrador_y_alcalde_ven_todos():
    assert vu.programas_visibles("administrador", []) is None
    assert vu.programas_visibles("alcalde", [P1]) is None


# --- altas (individual y masiva usan la misma función) -----------------------
def test_fila_valida():
    assert vu.validar_fila_usuario(fila(), existentes=set()) == {}


def test_fila_usuario_repetido_en_el_municipio_y_en_el_lote():
    assert "usuario" in vu.validar_fila_usuario(fila(), existentes={"ana"})
    assert "usuario" in vu.validar_fila_usuario(fila(), existentes=set(), vistos={"ana"})


def test_fila_email_y_tipo_invalidos():
    e = vu.validar_fila_usuario(fila(email="no-es-email", tipo="superjefe"), set())
    assert set(e) == {"email", "tipo"}
    assert vu.validar_fila_usuario(fila(email=""), set()) == {}
    assert vu.validar_fila_usuario(fila(email=None), set()) == {}


def test_fila_sin_nombre_ni_usuario():
    assert set(vu.validar_fila_usuario({"tipo": "informes"}, set())) == {"nombre", "usuario"}


def test_sin_reglas_de_complejidad_de_password():
    # decisión del cliente: ni longitud mínima ni mayúsculas/números/símbolos
    assert vu.validar_fila_usuario(fila(password="a"), set()) == {}


def test_anios_y_meses():
    assert vu.validar_anios_meses([2026], [1, 12]) == {}
    assert set(vu.validar_anios_meses([1999], [0])) == {"anios_acceso", "meses_acceso"}
    assert set(vu.validar_anios_meses(None, [13])) == {"meses_acceso"}


def test_levantar_si_errores():
    vu.levantar_si_errores({})
    with pytest.raises(ApiError) as e:
        vu.levantar_si_errores({"usuario": "El usuario ya existe en el municipio"})
    assert (e.value.status, e.value.codigo) == (409, "USUARIO_EXISTE")
    with pytest.raises(ApiError) as e:
        vu.levantar_si_errores({"email": "x"})
    assert e.value.status == 422


def test_autobloqueo():
    vu.validar_no_autobloqueo(U1, U2, "administrador", {"activo": False})  # a otro sí
    vu.validar_no_autobloqueo(U1, U1, "administrador", {"nombre": "x", "tipo": "administrador"})
    for cambios in ({"activo": False}, {"tipo": "informes"}):
        with pytest.raises(ApiError) as e:
            vu.validar_no_autobloqueo(U1, U1, "administrador", cambios)
        assert e.value.codigo == "AUTOBLOQUEO"


# --- caso 6: matriz ----------------------------------------------------------
def test_cambios_de_matriz_se_depuran_contra_lo_existente():
    actuales = {(U1, P1), (U1, P2)}
    ins, borr = vu.calcular_cambios_matriz(actuales, altas=[(U1, P1), (U2, P1)], bajas=[(U1, P2), (U2, P3)])
    assert ins == {(U2, P1)}          # (U1,P1) ya estaba asignado
    assert borr == {(U1, P2)}         # (U2,P3) no existía


def test_alta_y_baja_de_la_misma_celda_es_conflicto():
    with pytest.raises(ApiError) as e:
        vu.calcular_cambios_matriz(set(), [(U1, P1)], [(U1, P1)])
    assert e.value.codigo == "MATRIZ_CONFLICTO"


def test_resumen_de_matriz():
    assert vu.resumen_matriz(12, 3) == "12 asignaciones nuevas, 3 retiradas"
    assert vu.resumen_matriz(1, 1) == "1 asignación nueva, 1 retirada"
    assert vu.resumen_matriz(0, 0) == "0 asignaciones nuevas, 0 retiradas"


def test_ids_de_otro_municipio_se_rechazan():
    vu.validar_ids_del_municipio([P1], [P1, P2], "programa")
    with pytest.raises(ApiError) as e:
        vu.validar_ids_del_municipio([P1, P3], [P1], "programa")
    assert (e.value.status, e.value.codigo) == (422, "PROGRAMA_INVALIDO")


# --- configuración -----------------------------------------------------------
def test_meses_avance():
    assert vu.validar_meses_avance([3, 1, 3, 12]) == [1, 3, 12]
    for malo in ([0], [13], [True]):
        with pytest.raises(ApiError):
            vu.validar_meses_avance(malo)


def test_tolerancia():
    assert vu.validar_tolerancia(0) == 0 and vu.validar_tolerancia(365) == 365
    for malo in (-1, 366, True):
        with pytest.raises(ApiError):
            vu.validar_tolerancia(malo)
