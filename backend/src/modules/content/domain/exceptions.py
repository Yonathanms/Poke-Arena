"""Excepciones de Dominio del Módulo Content (Reglas de Negocio)."""

from src.shared.domain.exceptions import ConflictError, DomainError, EntityNotFoundError


class InvalidCardCostError(DomainError):
    def __init__(self, cost: int) -> None:
        super().__init__(
            message="El costo de la carta debe ser un número entero entre 0 y 10.",
            code="CATALOG_INVALID_CARD_COST",
            details=[
                {
                    "field": "cost",
                    "issue": f"Valor recibido ({cost}) fuera del rango permitido [0..10].",
                }
            ],
        )


class InvalidCardPowerError(DomainError):
    def __init__(self, power: int) -> None:
        super().__init__(
            message="El poder de la carta debe ser un número entero entre -20 y 20.",
            code="CATALOG_INVALID_CARD_POWER",
            details=[
                {
                    "field": "power",
                    "issue": f"Valor recibido ({power}) fuera del rango permitido [-20..20].",
                }
            ],
        )


class InvalidCardCodeError(DomainError):
    def __init__(self, code_val: str) -> None:
        super().__init__(
            message="El código de la carta debe seguir el formato PKA-<TIPO>-<NNN>.",
            code="CATALOG_INVALID_CARD_CODE",
            details=[
                {
                    "field": "code",
                    "issue": f"El valor recibido ({code_val}) no es un código oficial válido.",
                }
            ],
        )


class CardCodeTypeMismatchError(DomainError):
    def __init__(self, code_val: str, card_type: str) -> None:
        super().__init__(
            message="El tipo indicado no coincide con el tipo del código de la carta.",
            code="CATALOG_CARD_CODE_TYPE_MISMATCH",
            details=[
                {
                    "field": "card_type",
                    "issue": (
                        f"El código {code_val} corresponde a otro tipo distinto de {card_type}."
                    ),
                }
            ],
        )


class CardCodeCapacityExhaustedError(ConflictError):
    def __init__(self, card_type: str) -> None:
        super().__init__(
            message="Se agotaron los códigos disponibles para este tipo de carta.",
            code="CATALOG_CODE_CAPACITY_EXHAUSTED",
        )
        self.details = [
            {
                "field": "card_type",
                "issue": f"No quedan códigos PKA-{card_type}-NNN disponibles.",
            }
        ]


class CardCodeCounterMissingError(DomainError):
    def __init__(self, card_type: str) -> None:
        super().__init__(
            message="No está inicializado el contador de códigos para este tipo de carta.",
            code="CATALOG_CARD_CODE_COUNTER_MISSING",
            details=[{"field": "card_type", "issue": f"No existe el contador para {card_type}."}],
        )


class AbilityNotFoundError(DomainError):
    def __init__(self, ability_code: str) -> None:
        super().__init__(
            message="No existe una habilidad con el código seleccionado.",
            code="CATALOG_ABILITY_NOT_FOUND",
            details=[
                {
                    "field": "ability_code",
                    "issue": f"No se encontró la habilidad {ability_code}.",
                }
            ],
        )


class CardImageRecordRequiredError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            message="La carta debe asociarse a un registro persistido de imagen.",
            code="CATALOG_CARD_IMAGE_REQUIRED",
            details=[{"field": "image_id", "issue": "El registro de imagen es obligatorio."}],
        )


class InvalidCardNameError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            message="El nombre de la carta es obligatorio y no puede superar 100 caracteres.",
            code="CATALOG_INVALID_CARD_NAME",
            details=[{"field": "name", "issue": "Indique entre 1 y 100 caracteres no blancos."}],
        )


class AbilityRequiredError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            message="Debe seleccionar una habilidad existente, aunque sea Sin Habilidad.",
            code="CATALOG_ABILITY_REQUIRED",
            details=[{"field": "ability_code", "issue": "Seleccione una habilidad."}],
        )


class InvalidAbilityCodeError(DomainError):
    def __init__(self, ability_code: str) -> None:
        super().__init__(
            message="El código de habilidad debe seguir el formato HAB-<NNN>.",
            code="CATALOG_INVALID_ABILITY_CODE",
            details=[
                {
                    "field": "ability_code",
                    "issue": f"El valor recibido ({ability_code}) no es válido.",
                }
            ],
        )


class InvalidCardImageMetadataError(DomainError):
    def __init__(
        self,
        byte_size: int,
        width: int,
        height: int,
        thumbnail: bool = False,
    ) -> None:
        if thumbnail:
            message = "La miniatura debe ser WebP de 200 × 280 píxeles y no estar vacía."
            details = [
                {
                    "field": "thumbnail",
                    "issue": f"Metadatos no válidos: {width}×{height}, {byte_size} bytes.",
                }
            ]
        else:
            message = (
                "La imagen debe medir al menos 600 × 840, tener proporción 5:7 "
                "y pesar como máximo 5.000.000 bytes."
            )
            details = [
                {
                    "field": "image",
                    "issue": f"Metadatos no válidos: {width}×{height}, {byte_size} bytes.",
                }
            ]
        super().__init__(
            message=message,
            code="CATALOG_INVALID_CARD_IMAGE_METADATA",
            details=details,
        )


class EvolutionSelfReferenceError(DomainError):
    def __init__(self, card_id: str) -> None:
        super().__init__(
            message="Una carta no puede evolucionar hacia sí misma.",
            code="CATALOG_EVOLUTION_SELF_REFERENCE",
            details=[{"field": "evolution_target_card_id", "issue": f"Carta: {card_id}."}],
        )


class EvolutionCycleError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            message="La asociación de evolución forma un ciclo entre cartas.",
            code="CATALOG_EVOLUTION_CYCLE",
            details=[
                {
                    "field": "evolution_target_card_id",
                    "issue": "La relación propuesta cerraría un ciclo de evolución.",
                }
            ],
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


class IdempotencyKeyReusedError(ConflictError):
    def __init__(self) -> None:
        super().__init__(
            message="La llave de idempotencia ya se utilizó con otro contenido.",
            code="IDEMPOTENCY_KEY_REUSED",
        )


class IdempotencyInProgressError(ConflictError):
    def __init__(self) -> None:
        super().__init__(
            message="La solicitud con esta llave todavía se está procesando.",
            code="IDEMPOTENCY_IN_PROGRESS",
        )


class InvalidIdempotencyKeyError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            message="La llave de idempotencia debe tener entre 1 y 128 caracteres.",
            code="INVALID_IDEMPOTENCY_KEY",
            details=[{"field": "Idempotency-Key", "issue": "Longitud permitida: 1 a 128."}],
        )


class CardCreationCommitOutcomeUnknownError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            message=(
                "No fue posible confirmar el resultado de la creación; "
                "reintente con la misma llave."
            ),
            code="CARD_CREATION_OUTCOME_UNKNOWN",
        )


class OriginalImageCompensationError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            message="La imagen original quedó pendiente de conciliación.",
            code="CARD_IMAGE_COMPENSATION_REQUIRED",
        )


class InvalidCardImageError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            message=(
                "La imagen original no es un archivo PNG, JPEG o WebP válido de proporción 5:7."
            ),
            code="CATALOG_INVALID_CARD_IMAGE",
            details=[{"field": "image", "issue": "No se pudo validar el contenido de imagen."}],
        )


class CardNotFoundError(EntityNotFoundError):
    def __init__(self, identifier: str) -> None:
        super().__init__(entity_name="Carta", identifier=identifier)


class LocationNotFoundError(EntityNotFoundError):
    def __init__(self, identifier: str) -> None:
        super().__init__(entity_name="Ubicación", identifier=identifier)
