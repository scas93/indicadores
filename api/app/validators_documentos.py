"""Fase 4.3b — reglas puras de los documentos de beneficiarios (sin base de datos ni bucket)."""
import re
import uuid
from collections.abc import Iterable

from .errors import ApiError

MAX_BYTES = 5 * 1024 * 1024  # 5 MB; debe quedar por debajo del tope del proxy del front (10 MB por defecto en Next)
TIPOS = {"ine": "INE/IFE", "curp": "CURP", "comprobante_domicilio": "COMPROBANTE DE DOMICILIO"}
TODOS = "todos"
FILTROS_FALTANTE = (TODOS, *TIPOS)

# firma real del archivo -> (content-type, extensión). Lo que declare el cliente no cuenta.
_FIRMAS = ((b"%PDF-", "application/pdf", "pdf"), (b"\xff\xd8\xff", "image/jpeg", "jpg"),
           (b"\x89PNG\r\n\x1a\n", "image/png", "png"))
MSG_TIPO = "Solo se permiten archivos PDF, JPG o PNG"
MSG_TAMANO = "El archivo excede el máximo de 5 MB"


def detectar_tipo(contenido: bytes) -> tuple[str, str] | None:
    for firma, mime, ext in _FIRMAS:
        if contenido.startswith(firma):
            return mime, ext
    return None


def validar_archivo(contenido: bytes) -> tuple[str, str]:
    """(content-type, extensión) del archivo, o 422 si está vacío, pesa más de 5 MB o no es PDF/JPG/PNG de verdad."""
    if not contenido:
        raise ApiError(422, "ARCHIVO_VACIO", "Seleccione un archivo", {"archivo": "Seleccione un archivo"})
    if len(contenido) > MAX_BYTES:
        raise ApiError(422, "ARCHIVO_MUY_GRANDE", MSG_TAMANO, {"archivo": MSG_TAMANO})
    tipo = detectar_tipo(contenido)
    if tipo is None:
        raise ApiError(422, "ARCHIVO_TIPO_INVALIDO", MSG_TIPO, {"archivo": MSG_TIPO})
    return tipo


def validar_tipo_documento(tipo: str | None) -> str:
    t = (tipo or "").strip()
    if t not in TIPOS:
        raise ApiError(422, "TIPO_DOCUMENTO_INVALIDO", "Seleccione el tipo de documento", {"tipo": "Seleccione el tipo de documento"})
    return t


def llave(municipio_id: uuid.UUID, beneficiario_id: uuid.UUID, documento_id: uuid.UUID, extension: str) -> str:
    """Llave del objeto en el bucket: el municipio va primero y es parte de la ruta."""
    return f"docs/{municipio_id}/{beneficiario_id}/{documento_id}.{extension}"


def llave_es_de(llave_: str, municipio_id: uuid.UUID) -> bool:
    return llave_.startswith(f"docs/{municipio_id}/")


def nombre_seguro(nombre: str | None) -> str:
    """Nombre del archivo para mostrar y para Content-Disposition: sin rutas ni caracteres de control."""
    base = re.sub(r"[\x00-\x1f\x7f\"\\/]", "", (nombre or "").replace("\\", "/").split("/")[-1]).strip()
    return base[:200] or "documento"


def filtro_faltante(valor: str | None) -> str:
    v = (valor or TODOS).strip().lower()
    if v not in FILTROS_FALTANTE:
        raise ApiError(422, "FILTRO_INVALIDO", "Documento faltante inválido", {"faltante": "Documento faltante inválido"})
    return v


def le_falta(presentes: Iterable[str], faltante: str) -> bool:
    """Un tipo específico: el beneficiario no tiene NINGÚN documento de ese tipo. TODOS: le falta al menos uno de los tres."""
    tiene = set(presentes)
    if faltante == TODOS:
        return any(t not in tiene for t in TIPOS)
    return faltante not in tiene
