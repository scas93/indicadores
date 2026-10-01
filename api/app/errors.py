class ApiError(Exception):
    """Error de negocio con código estable que el front traduce."""

    def __init__(self, status: int, codigo: str, mensaje: str = "", campos: dict | None = None):
        self.status = status
        self.codigo = codigo
        self.mensaje = mensaje or codigo
        self.campos = campos or {}
        super().__init__(codigo)


class TenantViolation(Exception):
    """Se intentó escribir o mover un registro fuera del municipio de la petición."""
