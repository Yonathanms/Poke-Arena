from abc import ABC, abstractmethod
from types import TracebackType
from typing import Self


class IUnitOfWork(ABC):
    """
    Contrato base de Unidad de Trabajo (Unit of Work).
    Garantiza atomicidad transaccional y rollback automático en caso de fallo (DA-01, Regla 4).
    """

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            await self.rollback()
        else:
            await self.commit()

    @abstractmethod
    async def commit(self) -> None:
        """Confirma la transacción actual en la base de datos."""
        raise NotImplementedError

    @abstractmethod
    async def rollback(self) -> None:
        """Revierte los cambios de la transacción actual."""
        raise NotImplementedError
