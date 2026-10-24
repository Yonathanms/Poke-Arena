from typing import Any


class DomainError(Exception):
    """Excepción base para errores de reglas de negocio en el Dominio."""

    def __init__(
        self,
        message: str,
        code: str = "DOMAIN_ERROR",
        details: list[dict[str, Any]] | None = None,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or []
        self.status_code = status_code


class EntityNotFoundError(DomainError):
    """Error cuando un recurso solicitado no existe."""

    def __init__(self, entity_name: str, identifier: str) -> None:
        super().__init__(
            message=f"{entity_name} con identificador '{identifier}' no fue encontrado.",
            code=f"{entity_name.upper()}_NOT_FOUND",
            status_code=404,
        )


class ConflictError(DomainError):
    """Error por violación de unicidad o estado en conflicto."""

    def __init__(self, message: str, code: str = "RESOURCE_CONFLICT") -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=409,
        )
