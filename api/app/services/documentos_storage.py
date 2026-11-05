"""Almacén de documentos de beneficiarios (Fase 4.3b): bucket PRIVADO de R2 (S3), aparte del de imágenes de marca.

Nunca hay URL pública ni respaldo en disco: sin bucket configurado se responde 503. En pruebas y desarrollo local se
puede usar `MemoriaAlmacen` (DOCS_ALMACEN_MEMORIA=true, o `usar_almacen(...)` desde una prueba)."""
from typing import Protocol

from ..config import get_settings
from ..errors import ApiError


class Almacen(Protocol):
    def guardar(self, llave: str, contenido: bytes, content_type: str) -> None: ...
    def leer(self, llave: str) -> bytes: ...
    def borrar(self, llave: str) -> None: ...


class MemoriaAlmacen:
    """Simulado: vive en la memoria del proceso. Para pruebas y desarrollo local; no escribe nada en disco."""

    def __init__(self) -> None:
        self.objetos: dict[str, tuple[bytes, str]] = {}

    def guardar(self, llave, contenido, content_type):
        self.objetos[llave] = (contenido, content_type)

    def leer(self, llave):
        try:
            return self.objetos[llave][0]
        except KeyError:
            raise ApiError(404, "ARCHIVO_NO_ENCONTRADO", "El archivo no está en el almacenamiento") from None

    def borrar(self, llave):
        self.objetos.pop(llave, None)


class S3Almacen:
    def __init__(self, endpoint: str, bucket: str, key_id: str, secret: str, region: str) -> None:
        import boto3  # solo si hay bucket configurado

        self.bucket = bucket
        self.cli = boto3.client("s3", endpoint_url=endpoint or None, region_name=region or "auto",
                                aws_access_key_id=key_id, aws_secret_access_key=secret)

    def _falla(self, e: Exception):
        raise ApiError(502, "ALMACEN_ERROR", "No se pudo completar la operación con el almacenamiento de documentos") from e

    def guardar(self, llave, contenido, content_type):
        try:  # sin ACL: el bucket es privado
            self.cli.put_object(Bucket=self.bucket, Key=llave, Body=contenido, ContentType=content_type)
        except Exception as e:  # noqa: BLE001
            self._falla(e)

    def leer(self, llave):
        try:
            return self.cli.get_object(Bucket=self.bucket, Key=llave)["Body"].read()
        except Exception as e:  # noqa: BLE001
            if getattr(e, "response", {}).get("Error", {}).get("Code") in ("NoSuchKey", "404"):
                raise ApiError(404, "ARCHIVO_NO_ENCONTRADO", "El archivo no está en el almacenamiento") from e
            self._falla(e)

    def borrar(self, llave):  # borrar una llave que ya no existe no es error
        try:
            self.cli.delete_object(Bucket=self.bucket, Key=llave)
        except Exception as e:  # noqa: BLE001
            self._falla(e)


_forzado: Almacen | None = None
_memoria: MemoriaAlmacen | None = None


def usar_almacen(almacen: Almacen | None) -> None:
    """Para pruebas: reemplaza el almacén (None = vuelve a la configuración del ambiente)."""
    global _forzado
    _forzado = almacen


def obtener_almacen() -> Almacen:
    global _memoria
    if _forzado is not None:
        return _forzado
    s = get_settings()
    if s.docs_s3_bucket:
        return S3Almacen(s.docs_s3_endpoint_url, s.docs_s3_bucket, s.docs_s3_access_key_id,
                         s.docs_s3_secret_access_key, s.docs_s3_region)
    if s.docs_almacen_memoria:
        _memoria = _memoria or MemoriaAlmacen()
        return _memoria
    raise ApiError(503, "ALMACEN_NO_CONFIGURADO",
                   "El almacenamiento de documentos no está configurado en este ambiente. Avise al administrador del sistema.")
