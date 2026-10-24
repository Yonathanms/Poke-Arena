from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.application.unit_of_work import IUnitOfWork


class SqlUnitOfWork(IUnitOfWork):
    """Implementación de Unit of Work sobre AsyncSession de SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
