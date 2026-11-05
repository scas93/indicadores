"""Fase 4.3b — reglas puras de los documentos: tamaño, tipo por contenido, llave con municipio, "falta documento"."""
import uuid

import pytest

from app import validators_documentos as vd
from app.errors import ApiError

PDF, PNG, JPG = b"%PDF-1.7\n...", b"\x89PNG\r\n\x1a\n" + b"x" * 10, b"\xff\xd8\xff\xe0" + b"x" * 10


def test_tipo_por_contenido_real_y_no_por_lo_que_diga_el_cliente():
    assert vd.validar_archivo(PDF) == ("application/pdf", "pdf")
    assert vd.validar_archivo(PNG) == ("image/png", "png")
    assert vd.validar_archivo(JPG) == ("image/jpeg", "jpg")
    for falso in (b"MZ\x90\x00 programa.exe", b"<html><script>", b"GIF89a....", b"just text %PDF-"):
        with pytest.raises(ApiError) as e:
            vd.validar_archivo(falso)
        assert e.value.codigo == "ARCHIVO_TIPO_INVALIDO" and e.value.status == 422


def test_tamano_maximo_5_mb_y_vacio():
    assert vd.validar_archivo(PDF + b"0" * (vd.MAX_BYTES - len(PDF)))[1] == "pdf"  # exactamente 5 MB cabe
    with pytest.raises(ApiError) as e:
        vd.validar_archivo(PDF + b"0" * (vd.MAX_BYTES - len(PDF) + 1))
    assert e.value.codigo == "ARCHIVO_MUY_GRANDE" and "5 MB" in e.value.mensaje
    with pytest.raises(ApiError) as e:
        vd.validar_archivo(b"")
    assert e.value.codigo == "ARCHIVO_VACIO"


def test_el_tope_de_5_mb_cabe_bajo_el_del_proxy_de_next():
    assert vd.MAX_BYTES + 1024 * 1024 < 10 * 1024 * 1024  # 10 MB = valor por defecto de proxyClientMaxBodySize


def test_la_llave_lleva_el_municipio():
    m, b, d = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    k = vd.llave(m, b, d, "pdf")
    assert k == f"docs/{m}/{b}/{d}.pdf" and vd.llave_es_de(k, m) and not vd.llave_es_de(k, uuid.uuid4())


def test_tipo_de_documento_y_nombre_seguro():
    assert vd.validar_tipo_documento("ine") == "ine"
    for malo in (None, "", "pasaporte"):
        with pytest.raises(ApiError):
            vd.validar_tipo_documento(malo)
    assert vd.nombre_seguro("../../etc/passwd") == "passwd" and vd.nombre_seguro('a"b\r\n.pdf') == "ab.pdf" and vd.nombre_seguro(None) == "documento"


def test_le_falta_con_tipo_especifico_y_con_todos():
    assert vd.le_falta([], "ine") and vd.le_falta(["curp"], "ine") and not vd.le_falta(["ine", "ine"], "ine")
    assert vd.le_falta(["ine", "curp"], vd.TODOS)                       # falta el comprobante
    assert not vd.le_falta(["ine", "curp", "comprobante_domicilio"], vd.TODOS)
    assert vd.le_falta([], vd.TODOS)
    assert vd.filtro_faltante(None) == vd.TODOS and vd.filtro_faltante("CURP") == "curp"
    with pytest.raises(ApiError):
        vd.filtro_faltante("otro")
