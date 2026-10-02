from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://indicadores:indicadores@localhost:5433/indicadores"
    session_secret: str = "dev-secret-no-usar-en-prod"
    # 32 bytes en base64 (AES-256-GCM). Obligatoria para cifrar/descifrar contraseñas de usuario.
    password_encryption_key: str = ""
    root_domain: str = "localtest.me"
    super_admin_subdomain: str = "admin"
    cookie_secure: bool = True
    # Vigencia fija de la sesión del super admin (días).
    admin_session_dias: int = 1
    # Solo para pruebas: si se define, reemplaza duracion_sesion_dias (caso de prueba 8).
    sesion_duracion_minutos_override: int | None = None

    # Almacenamiento de imágenes (logo / imagen de login). Si no hay bucket, disco local.
    upload_dir: str = "uploads"
    media_public_base_url: str = ""  # p. ej. https://media.<dominio>; vacío = /api/media/<key>
    s3_endpoint_url: str = ""
    s3_bucket: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""

    # Recuperación de contraseña por email (Resend). Sin API key el correo no se envía (solo log).
    resend_api_key: str = ""
    email_from: str = ""
    public_scheme: str = "https"  # esquema de los links del correo (http en desarrollo)
    public_port: str = ""         # p. ej. 3000 en desarrollo

    # Solo seed.py
    seed_super_admin_usuario: str = ""
    seed_super_admin_password: str = ""
    seed_super_admin_nombre: str = "Super Admin"


@lru_cache
def get_settings() -> Settings:
    return Settings()
