from dataclasses import dataclass

from src.modules.content.application.ports import (
    ICardRepository,
    ICardSearchProjectionPort,
    IImageProcessorPort,
)
from src.modules.content.domain.entities import Card
from src.modules.content.domain.exceptions import DuplicateCardCodeError
from src.modules.content.domain.value_objects import AbilitySpec, CardRarity, CardType
from src.shared.application.unit_of_work import IUnitOfWork
from src.shared.infrastructure.storage import LocalFileStorage


@dataclass(frozen=True)
class CreateCardCommand:
    code: str
    name: str
    cost: int
    power: int
    card_type: CardType
    rarity: CardRarity
    image_bytes: bytes
    ability: AbilitySpec | None = None


class CreateCardUseCase:
    """Caso de Uso: Crear Carta (F-02 / US 2.1.1)."""

    def __init__(
        self,
        uow: IUnitOfWork,
        card_repo: ICardRepository,
        projection_port: ICardSearchProjectionPort,
        image_processor: IImageProcessorPort,
        file_storage: LocalFileStorage,
    ) -> None:
        self.uow = uow
        self.card_repo = card_repo
        self.projection_port = projection_port
        self.image_processor = image_processor
        self.file_storage = file_storage

    async def execute(self, cmd: CreateCardCommand) -> Card:
        # 1. Validar no duplicidad de código
        existing = await self.card_repo.get_by_code(cmd.code.upper())
        if existing:
            raise DuplicateCardCodeError(cmd.code)

        # 2. Validar proporciones (5:7) y generar miniatura con Pillow
        processed_img, thumbnail_img = self.image_processor.validate_and_process_card_image(
            cmd.image_bytes
        )

        # 3. Guardar archivos de imagen
        image_url = await self.file_storage.save_file(processed_img, ".webp", subfolder="cards")
        thumb_url = await self.file_storage.save_file(
            thumbnail_img, ".webp", subfolder="cards/thumbs"
        )

        # 4. Crear entidad de Dominio (aplica reglas de negocio: costo [1..6], poder >= 0)
        card = Card.create(
            code=cmd.code,
            name=cmd.name,
            cost=cmd.cost,
            power=cmd.power,
            card_type=cmd.card_type,
            rarity=cmd.rarity,
            image_url=image_url,
            thumbnail_url=thumb_url,
            ability=cmd.ability,
        )

        # 5. Persistencia Transaccional con Unit of Work (ACID en PostgreSQL)
        async with self.uow:
            await self.card_repo.save(card)

        # 6. Sincronizar proyección NoSQL en MongoDB para búsquedas rápidas (RNF-ALM-01)
        await self.projection_port.sync_card_projection(card)

        return card
