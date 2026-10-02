"""Envío de correo (Resend) solo para la recuperación de contraseña iniciada por el propio usuario."""
import json
import logging
import urllib.request
from typing import Protocol

from fastapi import Depends

from ..config import Settings, get_settings

log = logging.getLogger(__name__)


class Mailer(Protocol):
    def enviar(self, para: str, asunto: str, html: str) -> None: ...


class ResendMailer:
    def __init__(self, api_key: str, remitente: str):
        self.api_key, self.remitente = api_key, remitente

    def enviar(self, para: str, asunto: str, html: str) -> None:
        req = urllib.request.Request(
            "https://api.resend.com/emails", method="POST",
            data=json.dumps({"from": self.remitente, "to": [para], "subject": asunto, "html": html}).encode(),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req, timeout=10).read()
        except Exception:  # nunca debe revelar (ni romper) la respuesta del endpoint
            log.exception("No se pudo enviar el correo de recuperación")


class SinCorreo:
    """Sin RESEND_API_KEY (desarrollo): no envía nada; deja constancia en el log."""

    def enviar(self, para: str, asunto: str, html: str) -> None:
        log.warning("RESEND_API_KEY sin configurar: no se envió '%s' a %s", asunto, para)


def get_mailer(settings: Settings = Depends(get_settings)) -> Mailer:
    if settings.resend_api_key and settings.email_from:
        return ResendMailer(settings.resend_api_key, settings.email_from)
    return SinCorreo()


def enlace_recuperacion(settings: Settings, subdominio: str, token: str) -> str:
    puerto = f":{settings.public_port}" if settings.public_port else ""
    return f"{settings.public_scheme}://{subdominio}.{settings.root_domain}{puerto}/recuperar?token={token}"


def cuerpo_recuperacion(nombre: str, municipio: str, enlace: str) -> tuple[str, str]:
    return (f"Recupera tu contraseña — {municipio}",
            f"<p>Hola {nombre},</p><p>Recibimos una solicitud para restablecer tu contraseña. "
            f"Abre este enlace (vigente 1 hora, de un solo uso):</p><p><a href=\"{enlace}\">{enlace}</a></p>"
            f"<p>Si no la solicitaste, ignora este mensaje.</p>")
