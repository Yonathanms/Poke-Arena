from src.modules.content.application.ports import ILocationRepository
from src.modules.content.domain.entities import Location


class ListLocationsUseCase:
    """Caso de Uso: Listar ubicaciones disponibles (lectura, tolera datos de réplica)."""

    def __init__(self, location_repo: ILocationRepository) -> None:
        self.location_repo = location_repo

    async def execute(self) -> list[Location]:
        return await self.location_repo.list_all()
