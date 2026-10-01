"""Almacenamiento básico de imágenes (logo / imagen de login).
Con S3_BUCKET configurado usa R2/S3; si no, disco local servido en /api/media/<key>."""
import uuid
from pathlib import Path

from ..config import get_settings
from ..errors import ApiError

TIPOS = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}
MAX_BYTES = 3 * 1024 * 1024


def guardar_imagen(contenido: bytes, content_type: str) -> str:
    ext = TIPOS.get(content_type)
    if ext is None:
        raise ApiError(422, "IMAGEN_INVALIDA", "Formato no permitido (png, jpg, webp)")
    if len(contenido) > MAX_BYTES:
        raise ApiError(422, "IMAGEN_MUY_GRANDE", "La imagen excede 3 MB")
    s = get_settings()
    key = f"img/{uuid.uuid4().hex}.{ext}"
    if s.s3_bucket:
        import boto3  # opcional: solo si se usa R2/S3

        boto3.client(
            "s3", endpoint_url=s.s3_endpoint_url or None,
            aws_access_key_id=s.s3_access_key_id, aws_secret_access_key=s.s3_secret_access_key,
        ).put_object(Bucket=s.s3_bucket, Key=key, Body=contenido, ContentType=content_type)
        return f"{s.media_public_base_url.rstrip('/')}/{key}"
    path = Path(s.upload_dir) / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(contenido)
    return f"/api/media/{key}"
