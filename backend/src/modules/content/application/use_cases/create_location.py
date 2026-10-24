from dataclasses import dataclass

from src.modules.content.application.ports import (
    IImageProcessorPort,
    IImageStoragePort,
    ILocationRepository,
)
from src.modules.content.domain.entities import Location
from src.modules.content.domain.value_objects import LocationEffectSpec
from src.shared.application.unit_of_work import IUnitOfWork


@dataclass(frozen=True)
class CreateLocationCommand:
    name: str
    effect: LocationEffectSpec
    image_bytes: bytes


class CreateLocationUseCase:
    """Caso de Uso: Crear Ubicación de Juego (F-03 / US 2.1.3)."""

    def __init__(
        self,
        uow: IUnitOfWork,
        location_repo: ILocationRepository,
        image_processor: IImageProcessorPort,
        file_storage: IImageStoragePort,
    ) -> None:
        self.uow = uow
        self.location_repo = location_repo
        self.image_processor = image_processor
        self.file_storage = file_storage

    async def execute(self, cmd: CreateLocationCommand) -> Location:
        # 1. Validar relación de aspecto 4:3 con Pillow y generar miniatura
        processed_img, thumbnail_img = self.image_processor.validate_and_process_location_image(
            cmd.image_bytes
        )

        # 2. Guardar archivos de imagen
        image_url = await self.file_storage.save_file(processed_img, ".webp", subfolder="locations")
        thumb_url = await self.file_storage.save_file(
            thumbnail_img, ".webp", subfolder="locations/thumbs"
        )

        # 3. Crear entidad de Dominio
        location = Location.create(
            name=cmd.name,
            image_url=image_url,
            thumbnail_url=thumb_url,
            effect=cmd.effect,
        )

        # 4. Guardar bajo Unit of Work en PostgreSQL con compensación de archivos huérfanos
        saved_urls = [image_url, thumb_url]
        try:
            async with self.uow:
                await self.location_repo.save(location)
        except Exception:
            for url in saved_urls:
                try:
                    await self.file_storage.delete_file(url)
                except Exception:
                    pass
            raise

        return location
