"""Errores del adaptador: dobles de sesión sin motores ni credenciales reales."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.catalogo import catalogo_module as catalogo

ErrorPersistencia = catalogo.puertos_cartas.ErrorPersistencia
TIPO = catalogo.puertos_cartas.TipoErrorPersistencia


class DriverError(Exception):
    """Diagnóstico mínimo de driver; el mensaje sensible nunca debe propagarse."""

    def __init__(self, state: str | None) -> None:
        """Modela SQLSTATE conocido, desconocido o ausente sin conexión real."""
        self.sqlstate = state
        self.constraint_name = "constraint_test"
        super().__init__("valor_sensible_de_prueba")


def driver_failure(state: str | None, wrapped: bool) -> DBAPIError:
    """Construye el diagnóstico directo o envuelto que recibe SQLAlchemy async."""
    original: Exception = DriverError(state)
    if wrapped:
        wrapper = Exception("valor_sensible_de_prueba")
        wrapper.__cause__ = original
        original = wrapper
    return DBAPIError("SQL_sensible_de_prueba", {"private": "valor"}, original)


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    """Abre solo una transacción lógica; sin bind no puede alcanzar una base."""
    async with AsyncSession() as current:
        await current.begin()
        yield current


async def test_composition_uses_the_declared_port(session: AsyncSession) -> None:
    """Comprueba que la composición carga el adaptador y su puerto canónico."""
    repository = catalogo.crear_repositorio_cartas(session)
    assert catalogo.puertos_cartas.CartasRepositoryPort in type(repository).__mro__


@pytest.mark.parametrize("state,expected", [
    ("23505", TIPO.DUPLICADO), ("23503", TIPO.REFERENCIA),
    ("23514", TIPO.RESTRICCION), ("23502", TIPO.RESTRICCION),
    ("P0001", TIPO.RESTRICCION), ("XX000", TIPO.OPERACION),
    (None, TIPO.OPERACION),
])
@pytest.mark.parametrize("wrapped", [False, True])
async def test_write_error_translation(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
    state: str | None, expected: str, wrapped: bool,
) -> None:
    """Verifica clasificación/sanitización para SQLSTATE y envoltura asyncpg."""
    failure = driver_failure(state, wrapped)
    monkeypatch.setattr(session, "flush", AsyncMock(side_effect=failure))
    carta = catalogo.dominio_cartas.Carta(
        id="isolated", code="PKA-FUE-001", name="Prueba", cost=1, power=1,
        card_type="FUE", rarity="COMUN", ability_id="existing",
        created_at=datetime.now(UTC),
    )
    repo = catalogo.crear_repositorio_cartas(session)
    with pytest.raises(ErrorPersistencia) as exc:
        await repo.agregar(carta)
    assert exc.value.tipo == expected
    assert exc.value.restriccion == ("constraint_test" if wrapped else None)
    assert "sensible" not in str(exc.value)
    assert exc.value.__suppress_context__
    assert session.in_transaction()


@pytest.mark.parametrize("method", [
    "buscar_por_id", "buscar_por_codigo", "buscar_habilidad_por_codigo", "bloquear_contador",
])
async def test_query_error_translation(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch, method: str,
) -> None:
    """Cada ruta de lectura/bloqueo traduce el fallo sin tomar control de la sesión."""
    scalar = AsyncMock(side_effect=driver_failure("XX000", True))
    monkeypatch.setattr(session, "scalar", scalar)
    repo = catalogo.crear_repositorio_cartas(session)
    operation: Any = getattr(repo, method)
    with pytest.raises(ErrorPersistencia) as exc:
        await operation("isolated")
    assert exc.value.tipo == TIPO.OPERACION
    assert exc.value.restriccion == "constraint_test"
    assert "sensible" not in str(exc.value)
    scalar.assert_awaited_once()
    assert session.in_transaction()
