"""Transactional idempotency and outbox behavior using real PostgreSQL connections."""

import asyncio
import os
import uuid
from collections.abc import AsyncIterator
from dataclasses import replace
from pathlib import Path

import pytest
import pytest_asyncio
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from alembic import command
from src.main import app
from src.modules.content.application.dtos import CardCreatedEventDTO, CreateCardResult
from src.modules.content.application.ports import ICardImageInspector, IOutboxWriter
from src.modules.content.application.use_cases.create_card import (
    AuthenticatedCardActor,
    CreateCardCommand,
    CreateCardUseCase,
)
from src.modules.content.application.use_cases.list_abilities import ListCardAbilitiesUseCase
from src.modules.content.application.use_cases.process_durable_work import (
    GetCardImageStatusUseCase,
)
from src.modules.content.composition import (
    get_card_image_status_use_case,
    get_create_card_use_case,
    get_list_card_abilities_use_case,
)
from src.modules.content.domain.exceptions import AbilityNotFoundError, IdempotencyKeyReusedError
from src.modules.content.domain.value_objects import (
    AbilityCode,
    CardImageFormat,
    CardImageMetadata,
    CardImageState,
    CardRarity,
    CardThumbnailMetadata,
    CardType,
)
from src.modules.content.infrastructure.repositories.sql_ability_repository import (
    SqlAbilityRepository,
)
from src.modules.content.infrastructure.repositories.sql_card_code_allocator import (
    SqlCardCodeAllocator,
)
from src.modules.content.infrastructure.repositories.sql_card_image_repository import (
    SqlCardImageRepository,
)
from src.modules.content.infrastructure.repositories.sql_card_repository import (
    SqlCardRepository,
)
from src.modules.content.infrastructure.repositories.sql_creation_records import (
    SqlCardCreationIdempotencyAdapter,
    SqlOutboxWriter,
)
from src.modules.content.infrastructure.repositories.sql_processing_transactions import (
    SqlCardImageProcessingTransactions,
)
from src.modules.content.infrastructure.services.pillow_image_processor import (
    PillowImageProcessor,
)
from src.modules.content.infrastructure.unit_of_work import SqlUnitOfWork
from src.modules.identity.composition import register_identity_module
from src.modules.identity.contracts import AuthenticatedPrincipal, InvalidAccessTokenError
from src.shared.application.unit_of_work import IUnitOfWork
from src.shared.infrastructure.config import get_settings

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_CONFIG = BACKEND_ROOT / "alembic.ini"
RAW_IMAGE = b"valid-image-fixture-content"


def _upgrade(connection: Connection, target: str) -> None:
    config = Config(str(ALEMBIC_CONFIG))
    config.attributes["connection"] = connection
    command.upgrade(config, target)


@pytest_asyncio.fixture(loop_scope="function")
async def creation_database() -> AsyncIterator[
    tuple[AsyncEngine, async_sessionmaker[AsyncSession]]
]:
    url = os.getenv("CONTENT_MIGRATION_TEST_URL")
    if not url and os.getenv("RUN_ISOLATED_POSTGRES_TESTS") == "1":
        url = get_settings().DATABASE_WRITE_URL
    if not url:
        pytest.skip(
            "Defina CONTENT_MIGRATION_TEST_URL o RUN_ISOLATED_POSTGRES_TESTS=1 "
            "para pruebas PostgreSQL aisladas."
        )
    schema = f"content_create_test_{uuid.uuid4().hex}"
    admin = create_async_engine(url)
    async with admin.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    await admin.dispose()
    engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
    try:
        async with engine.connect() as connection:
            await connection.run_sync(lambda conn: _upgrade(conn, "head"))
            await connection.commit()
        yield engine, async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    finally:
        await engine.dispose()
        admin = create_async_engine(url)
        async with admin.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose()


class FixedImageInspector:
    def inspect_card_image(self, raw_bytes: bytes) -> CardImageMetadata:
        return CardImageMetadata(CardImageFormat.PNG, len(raw_bytes), 600, 840)


class MemoryStorage:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.saves = 0
        self.deletes = 0

    async def save_file(self, content: bytes, extension: str, subfolder: str = "") -> str:
        self.saves += 1
        key = f"/uploads/{uuid.uuid4()}{extension}"
        self.files[key] = content
        return key

    async def delete_file(self, file_url: str) -> None:
        self.deletes += 1
        self.files.pop(file_url, None)


class FailingOutbox:
    async def add_card_created(self, event: CardCreatedEventDTO) -> None:
        raise RuntimeError("outbox insert failed")


class CommitThenDisconnectUnitOfWork(SqlUnitOfWork):
    async def commit(self) -> None:
        await super().commit()
        raise ConnectionError("connection lost after server commit")


def _use_case(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    storage: MemoryStorage,
    *,
    outbox: IOutboxWriter | None = None,
    uow: IUnitOfWork | None = None,
    image_inspector: ICardImageInspector | None = None,
) -> CreateCardUseCase:
    return CreateCardUseCase(
        uow=uow or SqlUnitOfWork(session),
        card_repo=SqlCardRepository(session),
        code_allocator=SqlCardCodeAllocator(session),
        ability_repo=SqlAbilityRepository(session),
        image_repo=SqlCardImageRepository(session),
        idempotency=SqlCardCreationIdempotencyAdapter(session, session_factory),
        outbox=outbox or SqlOutboxWriter(session),
        image_inspector=image_inspector or FixedImageInspector(),
        file_storage=storage,
    )


def _command(
    *, actor: str = "admin-1", key: str = "request-1", image: bytes = RAW_IMAGE
) -> CreateCardCommand:
    return CreateCardCommand(
        name="Pikachu",
        cost=0,
        power=-2,
        card_type=CardType.FUEGO,
        rarity=CardRarity.COMUN,
        ability_code=AbilityCode("HAB-000"),
        image_bytes=image,
        actor=AuthenticatedCardActor(actor),
        idempotency_key=key,
    )


@pytest.mark.asyncio
async def test_concurrent_identical_creates_share_one_card_counter_and_event(
    creation_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    engine, factory = creation_database
    storage = MemoryStorage()

    async def create() -> CreateCardResult:
        async with factory() as session:
            return await _use_case(session, factory, storage).execute(_command())

    first, second = await asyncio.gather(create(), create())
    assert first.snapshot == second.snapshot
    assert sorted((first.replayed, second.replayed)) == [False, True]
    assert first.snapshot.code == "PKA-FUE-001"
    assert storage.saves == 1
    async with engine.connect() as connection:
        assert await connection.scalar(text("SELECT count(*) FROM catalog_cards")) == 1
        assert await connection.scalar(text("SELECT count(*) FROM catalog_card_images")) == 1
        assert await connection.scalar(text("SELECT count(*) FROM shared_outbox")) == 1
        assert await connection.scalar(text("SELECT count(*) FROM shared_idempotency_records")) == 1
        assert (
            await connection.scalar(
                text("SELECT last_value FROM catalog_card_code_counters WHERE card_type = 'FUE'")
            )
            == 1
        )


@pytest.mark.asyncio
async def test_key_reuse_conflicts_and_other_actor_is_independent(
    creation_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = creation_database
    storage = MemoryStorage()
    async with factory() as session:
        use_case = _use_case(session, factory, storage)
        original = await use_case.execute(_command())
        replay = await use_case.execute(_command())
        assert replay.replayed is True
        assert replay.snapshot == original.snapshot
        assert storage.saves == 1
        with pytest.raises(IdempotencyKeyReusedError):
            await use_case.execute(_command(image=b"different-image"))
        other_actor = await use_case.execute(_command(actor="admin-2"))
        assert other_actor.snapshot.id != original.snapshot.id
        assert storage.saves == 2


@pytest.mark.asyncio
async def test_failure_after_counter_allocation_rolls_back_and_releases_key(
    creation_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    engine, factory = creation_database
    storage = MemoryStorage()
    async with factory() as session:
        failing = _use_case(session, factory, storage, outbox=FailingOutbox())
        with pytest.raises(RuntimeError, match="outbox insert failed"):
            await failing.execute(_command())
    async with engine.connect() as connection:
        assert await connection.scalar(text("SELECT count(*) FROM catalog_cards")) == 0
        assert await connection.scalar(text("SELECT count(*) FROM catalog_card_images")) == 0
        assert await connection.scalar(text("SELECT count(*) FROM shared_outbox")) == 0
        assert await connection.scalar(text("SELECT count(*) FROM shared_idempotency_records")) == 0
        assert (
            await connection.scalar(
                text("SELECT last_value FROM catalog_card_code_counters WHERE card_type = 'FUE'")
            )
            == 0
        )
    assert storage.files == {}
    async with factory() as session:
        retried = await _use_case(session, factory, storage).execute(_command())
        assert retried.snapshot.code == "PKA-FUE-001"


@pytest.mark.asyncio
async def test_missing_ability_does_not_store_file_or_consume_code_or_key(
    creation_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    engine, factory = creation_database
    storage = MemoryStorage()
    async with factory() as session:
        use_case = _use_case(session, factory, storage)
        invalid = replace(_command(), ability_code=AbilityCode("HAB-999"))
        with pytest.raises(AbilityNotFoundError):
            await use_case.execute(invalid)
        assert storage.saves == 0
        valid_result = await use_case.execute(_command())
        assert valid_result.snapshot.code == "PKA-FUE-001"
    async with engine.connect() as connection:
        assert await connection.scalar(text("SELECT count(*) FROM shared_idempotency_records")) == 1
        assert (
            await connection.scalar(
                text("SELECT last_value FROM catalog_card_code_counters WHERE card_type = 'FUE'")
            )
            == 1
        )


@pytest.mark.asyncio
async def test_unknown_commit_result_is_resolved_from_primary_without_deleting_original(
    creation_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = creation_database
    storage = MemoryStorage()
    async with factory() as session:
        result = await _use_case(
            session,
            factory,
            storage,
            uow=CommitThenDisconnectUnitOfWork(session),
        ).execute(_command())
    assert result.snapshot.code == "PKA-FUE-001"
    assert result.replayed is True
    assert storage.saves == 1
    assert storage.deletes == 0
    assert len(storage.files) == 1


@pytest.mark.asyncio
async def test_initial_outbox_aggregate_version_is_unique(
    creation_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    engine, factory = creation_database
    storage = MemoryStorage()
    async with factory() as session:
        result = await _use_case(session, factory, storage).execute(_command())
    async with engine.begin() as connection:
        event = (
            await connection.execute(
                text(
                    "SELECT id, event_type, payload FROM shared_outbox "
                    "WHERE aggregate_id = :aggregate_id"
                ),
                {"aggregate_id": result.snapshot.id},
            )
        ).one()
        with pytest.raises(IntegrityError):
            await connection.execute(
                text(
                    "INSERT INTO shared_outbox "
                    "(id, event_type, payload, status, aggregate_type, aggregate_id, "
                    "aggregate_version, schema_version, created_at) "
                    "VALUES (:id, 'CardCreated', '{}', 'PENDING', 'card', :aggregate_id, "
                    "1, 1, now())"
                ),
                {"id": str(uuid.uuid4()), "aggregate_id": result.snapshot.id},
            )
        assert event.event_type == "CardCreated"


@pytest.mark.asyncio
async def test_idempotent_replay_keeps_original_pending_snapshot_after_ready(
    creation_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = creation_database
    storage = MemoryStorage()
    async with factory() as session:
        original = await _use_case(session, factory, storage).execute(_command())

    async with factory() as session:
        result = await session.execute(
            text("SELECT image_id FROM catalog_cards WHERE id = :card_id"),
            {"card_id": original.snapshot.id},
        )
        image_id = result.scalar_one()
        repository = SqlCardImageRepository(session)
        claim = await repository.claim_next()
        assert claim is not None and claim.image_id == image_id
        event = await repository.complete(
            claim,
            "/uploads/cards/thumbnails/attempt.webp",
            CardThumbnailMetadata(CardImageFormat.WEBP, 64, 200, 280),
        )
        assert event is not None
        await session.commit()

    async with factory() as session:
        replay = await _use_case(session, factory, storage).execute(_command())

    assert replay.replayed is True
    assert replay.snapshot == original.snapshot
    assert replay.snapshot.image_status == CardImageState.PENDING.value
    assert replay.snapshot.available_to_players is False


class Stage9IdentityContract:
    async def authenticate(self, access_token: str) -> AuthenticatedPrincipal:
        if access_token != "stage9-admin-token":
            raise InvalidAccessTokenError()
        return AuthenticatedPrincipal(
            user_id="stage9-admin",
            is_platform_admin=True,
        )


@pytest.mark.asyncio
async def test_authenticated_create_card_without_image_api_flow_against_isolated_postgres(
    creation_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    engine, factory = creation_database
    storage = MemoryStorage()
    previous_identity = getattr(app.state, "identity_module_contract", None)
    previous_identity_service = getattr(app.state, "identity_application_service", None)
    register_identity_module(app, Stage9IdentityContract())

    async def create_card_use_case_dependency() -> AsyncIterator[CreateCardUseCase]:
        async with factory() as session:
            yield _use_case(
                session,
                factory,
                storage,
                image_inspector=PillowImageProcessor(),
            )

    async def list_abilities_use_case_dependency() -> AsyncIterator[ListCardAbilitiesUseCase]:
        async with factory() as session:
            yield ListCardAbilitiesUseCase(SqlAbilityRepository(session))

    app.dependency_overrides[get_create_card_use_case] = create_card_use_case_dependency
    app.dependency_overrides[get_list_card_abilities_use_case] = list_abilities_use_case_dependency
    app.dependency_overrides[get_card_image_status_use_case] = lambda: GetCardImageStatusUseCase(
        SqlCardImageProcessingTransactions(factory)
    )

    headers = {"Authorization": "Bearer stage9-admin-token"}
    form = {
        "name": "Charmander API Stage 9",
        "cost": "0",
        "power": "-2",
        "card_type": "FUE",
        "rarity": "COMUN",
        "ability_code": "HAB-000",
    }

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            catalog_response = await client.get("/api/v1/content/abilities", headers=headers)
            assert catalog_response.status_code == 200
            assert any(ability["code"] == "HAB-000" for ability in catalog_response.json())

            create_headers = {**headers, "Idempotency-Key": "stage9-create-001"}
            created_response = await client.post(
                "/api/v1/content/cards",
                data=form,
                headers=create_headers,
            )
            assert created_response.status_code == 201
            created = created_response.json()
            assert created["code"] == "PKA-FUE-001"
            assert created["image_status"] is None
            assert created["image_url"] is None
            assert created["thumbnail_url"] is None
            assert created["available_to_players"] is False
            assert created_response.headers["location"] == created["status_url"]

            replay_response = await client.post(
                "/api/v1/content/cards",
                data=form,
                headers=create_headers,
            )
            assert replay_response.status_code == 201
            assert replay_response.json()["id"] == created["id"]
            assert storage.saves == 0

            status_response = await client.get(created["status_url"], headers=headers)
            assert status_response.status_code == 200
            assert status_response.json()["image_status"] is None
            assert status_response.json()["attempts"] == 0

            invalid_cost_response = await client.post(
                "/api/v1/content/cards",
                data={**form, "cost": "11"},
                headers={**headers, "Idempotency-Key": "stage9-invalid-cost"},
            )
            assert invalid_cost_response.status_code == 400

            invalid_image_response = await client.post(
                "/api/v1/content/cards",
                data=form,
                files={"image": ("broken.png", b"not-an-image", "image/png")},
                headers={**headers, "Idempotency-Key": "stage9-invalid-image"},
            )
            assert invalid_image_response.status_code == 400

            legacy_field_response = await client.post(
                "/api/v1/content/cards",
                data={**form, "code": "PKA-FUE-002"},
                headers={**headers, "Idempotency-Key": "stage9-legacy-field"},
            )
            assert legacy_field_response.status_code == 422
    finally:
        app.dependency_overrides.pop(get_create_card_use_case, None)
        app.dependency_overrides.pop(get_list_card_abilities_use_case, None)
        app.dependency_overrides.pop(get_card_image_status_use_case, None)
        if previous_identity is None:
            delattr(app.state, "identity_module_contract")
        else:
            app.state.identity_module_contract = previous_identity
        if previous_identity_service is None:
            delattr(app.state, "identity_application_service")
        else:
            app.state.identity_application_service = previous_identity_service

    assert storage.saves == 0
    async with engine.connect() as connection:
        assert await connection.scalar(text("SELECT count(*) FROM catalog_cards")) == 1
        assert await connection.scalar(text("SELECT count(*) FROM catalog_card_images")) == 0
        assert await connection.scalar(text("SELECT count(*) FROM shared_outbox")) == 1
        assert (
            await connection.scalar(
                text("SELECT last_value FROM catalog_card_code_counters WHERE card_type = 'FUE'")
            )
            == 1
        )
