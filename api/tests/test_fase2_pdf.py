"""Fase 2 — descargas PDF: se generan, respetan el acceso por programa y no inventan datos.
La coincidencia de estructura con el sistema de referencia (caso 10) es verificación manual."""
import re
import zlib

import pytest

from .test_fase2_flujos import Ctx, hoy_fijo, serie, usuario_con  # noqa: F401
from .test_fase1_flujos import m  # noqa: F401


def texto(pdf: bytes) -> str:
    """Texto aproximado del PDF (los streams de ReportLab van en ASCII85+Flate)."""
    import base64
    out = []
    for blob in re.findall(rb"stream\r?\n(.*?)endstream", pdf, re.S):
        try:
            raw = zlib.decompress(base64.a85decode(blob.strip(), adobe=False) if blob.strip().endswith(b"~>") else blob)
        except Exception:  # noqa: BLE001
            try:
                raw = zlib.decompress(base64.a85decode(blob.strip().removesuffix(b"~>")))
            except Exception:  # noqa: BLE001
                continue
        out.append(raw.decode("latin-1"))
    # los párrafos parten las líneas: se unen todas las cadenas mostradas con Tj en un solo texto
    cadenas = re.findall(r"\(((?:[^()\\]|\\.)*)\) Tj", " ".join(out))
    return re.sub(r"\s+", " ", " ".join(cadenas))


@pytest.fixture()
def lleno(m):
    c = Ctx(m)
    m.post(m.admin, f"/api/programas/{c.pid}/arbol/causas", {"texto_causa": "Causa uno", "texto_medio": "Medio uno"})
    m.admin.put(f"/api/programas/{c.pid}/arbol/encabezado", headers=m.h, json={"problema": "PROBLEMA X", "objetivo": "OBJETIVO X"})
    m.post(m.admin, f"/api/programas/{c.pid}/arbol/efectos", {"texto_efecto": "Efecto uno", "texto_fin": "Fin uno"})
    comp = m.post(m.admin, f"/api/programas/{c.pid}/matriz/componentes", {"resumen_narrativo": "Componente uno"}).json()
    c.ind = c.nuevo_indicador(nombre="Indicador de fin")
    c.nuevo_indicador(comp["id"], nombre="Indicador de componente", algoritmo="a",
                      anuales=[{"anio": 2024, "valor_a_programado": 3}])
    c.put(c.ind, [{"mes": 1, "valor_a": 3, "valor_b": 250}, {"mes": 2, "valor_a": 3, "valor_b": 250},
                  {"mes": 3, "valor_a": 3, "valor_b": 250}, {"mes": 4, "valor_a": 2.8, "valor_b": 250}])
    return c


@pytest.mark.parametrize("ruta", [
    "/api/programas/{p}/arbol/descarga?tipo=completo", "/api/programas/{p}/arbol/descarga?tipo=problemas",
    "/api/programas/{p}/arbol/descarga?tipo=objetivos", "/api/programas/{p}/matriz/descarga?tipo=resultados",
    "/api/programas/{p}/matriz/descarga?tipo=cumplimiento&anio=2024",
    "/api/indicadores/{i}/exportar?formato=fn", "/api/indicadores/{i}/exportar?formato=fa&anio=2024"])
def test_los_siete_pdf_se_generan(m, lleno, ruta):
    r = m.get(m.admin, ruta.format(p=lleno.pid, i=lleno.ind["id"]))
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf" and r.content.startswith(b"%PDF")
    assert "attachment" in r.headers["content-disposition"]


def test_los_pdf_llevan_los_datos_capturados(m, lleno):
    t = texto(m.get(m.admin, f"/api/programas/{lleno.pid}/arbol/descarga?tipo=completo").content)
    assert "PROBLEMA X" in t and "OBJETIVO X" in t and "Causa uno" in t and "Medio uno" in t and "Fin uno" in t
    prob = texto(m.get(m.admin, f"/api/programas/{lleno.pid}/arbol/descarga?tipo=problemas").content)
    assert "Causa uno" in prob and "Medio uno" not in prob and "OBJETIVO X" not in prob
    obj = texto(m.get(m.admin, f"/api/programas/{lleno.pid}/arbol/descarga?tipo=objetivos").content)
    assert "Medio uno" in obj and "Causa uno" not in obj and "PROBLEMA X" not in obj
    cum = texto(m.get(m.admin, f"/api/programas/{lleno.pid}/matriz/descarga?tipo=cumplimiento&anio=2024").content)
    assert "Indicador de fin" in cum and "1.18" in cum and "Rojo" in cum
    fa = texto(m.get(m.admin, f"/api/indicadores/{lleno.ind['id']}/exportar?formato=fa&anio=2024").content)
    assert "1.18" in fa and "Variable B" in fa


def test_ficha_de_avance_solo_a_no_muestra_variable_b(m, lleno):
    sola = m.get(m.admin, f"/api/programas/{lleno.pid}/captura-avances").json()["indicadores"]
    ind_a = next(i for i in sola if i["algoritmo"] == "a")
    fa = texto(m.get(m.admin, f"/api/indicadores/{ind_a['id']}/exportar?formato=fa&anio=2024").content)
    assert "Variable A" in fa and "Variable B" not in fa


def test_pdf_tipo_invalido_y_acceso_por_programa(m, lleno):
    assert m.get(m.admin, f"/api/programas/{lleno.pid}/arbol/descarga?tipo=otro").status_code == 422
    assert m.get(m.admin, f"/api/programas/{lleno.pid}/matriz/descarga?tipo=otro").status_code == 422
    assert m.get(m.admin, f"/api/indicadores/{lleno.ind['id']}/exportar?formato=zz").status_code == 422
    otro = Ctx(m, "B")
    u = usuario_con(m, [otro.pid])
    for ruta in (f"/api/programas/{lleno.pid}/arbol/descarga", f"/api/programas/{lleno.pid}/matriz/descarga",
                 f"/api/indicadores/{lleno.ind['id']}/exportar"):
        assert m.get(u, ruta).status_code == 403, ruta


def test_texto_con_caracteres_especiales_no_rompe_el_pdf(m):
    c = Ctx(m)
    m.post(m.admin, f"/api/programas/{c.pid}/arbol/causas", {"texto_causa": "a < b & <b>x</b>\nlínea 2 ñ é"})
    r = m.get(m.admin, f"/api/programas/{c.pid}/arbol/descarga")
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
