"""Excepciones de Dominio del Módulo Content (Reglas de Negocio)."""

from src.shared.domain.exceptions import ConflictError, DomainError, EntityNotFoundError


class InvalidCardCostError(DomainError):
    def __init__(self, cost: int) -> None:
        super().__init__(
            message="El costo de la carta debe ser un número entero entre 1 y 6.",
            code="CATALOG_INVALID_CARD_COST",
            details=[
                {
                    "field": "cost",
                    "issue": f"Valor recibido ({cost}) fuera del rango permitido [1..6].",
                }
            ],
        )


class InvalidCardPowerError(DomainError):
    def __init__(self, power: int) -> None:
        super().__init__(
            message="El poder de la carta no puede ser negativo.",
            code="CATALOG_INVALID_CARD_POWER",
            details=[{"field": "power", "issue": f"Valor recibido ({power}) menor que 0."}],
        )


class InvalidImageAspectRatioError(DomainError):
    def __init__(self, resource_type: str, expected_ratio: str, actual_ratio: str) -> None:
        super().__init__(
            message=f"La proporción de imagen para {resource_type} debe ser {expected_ratio}.",
            code="INVALID_IMAGE_ASPECT_RATIO",
            details=[
                {"resource": resource_type, "expected": expected_ratio, "actual": actual_ratio}
            ],
        )


class DuplicateCardCodeError(ConflictError):
    def __init__(self, code_val: str) -> None:
        super().__init__(
            message=f"Ya existe una carta registrada con el código '{code_val}'.",
            code="CATALOG_DUPLICATE_CARD_CODE",
        )


class CardNotFoundError(EntityNotFoundError):
    def __init__(self, identifier: str) -> None:
        super().__init__(entity_name="Carta", identifier=identifier)


class LocationNotFoundError(EntityNotFoundError):
    def __init__(self, identifier: str) -> None:
        super().__init__(entity_name="Ubicación", identifier=identifier)
