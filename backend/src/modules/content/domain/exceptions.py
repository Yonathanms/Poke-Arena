from src.shared.domain.exceptions import DomainError


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
            status_code=400,
        )


class InvalidCardPowerError(DomainError):
    def __init__(self, power: int) -> None:
        super().__init__(
            message="El poder de la carta no puede ser negativo.",
            code="CATALOG_INVALID_CARD_POWER",
            details=[{"field": "power", "issue": f"Valor recibido ({power}) menor que 0."}],
            status_code=400,
        )


class InvalidImageAspectRatioError(DomainError):
    def __init__(self, resource_type: str, expected_ratio: str, actual_ratio: str) -> None:
        super().__init__(
            message=f"La proporción de imagen para {resource_type} debe ser {expected_ratio}.",
            code="INVALID_IMAGE_ASPECT_RATIO",
            details=[
                {"resource": resource_type, "expected": expected_ratio, "actual": actual_ratio}
            ],
            status_code=400,
        )


class DuplicateCardCodeError(DomainError):
    def __init__(self, code_val: str) -> None:
        super().__init__(
            message=f"Ya existe una carta registrada con el código '{code_val}'.",
            code="CATALOG_DUPLICATE_CARD_CODE",
            status_code=409,
        )


class CardNotFoundError(DomainError):
    def __init__(self, identifier: str) -> None:
        super().__init__(
            message=f"La carta con identificador '{identifier}' no fue encontrada.",
            code="CATALOG_CARD_NOT_FOUND",
            status_code=404,
        )


class LocationNotFoundError(DomainError):
    def __init__(self, identifier: str) -> None:
        super().__init__(
            message=f"La ubicación con identificador '{identifier}' no fue encontrada.",
            code="CATALOG_LOCATION_NOT_FOUND",
            status_code=404,
        )
