"""Pruebas PostgreSQL para migraciones e invariantes del módulo Content.

Configurar CONTENT_MIGRATION_TEST_URL con una base desechable dedicada. Cada prueba crea
un schema aleatorio y ejecuta Alembic desde cero; nunca usa la URL de la aplicación.
"""

import asyncio
import hashlib
import io
import os
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from alembic.config import Config
from PIL import Image
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
from src.modules.content.application.dtos import CardImageRecordDTO
from src.modules.content.application.use_cases.process_card_image import ProcessCardImageUseCase
from src.modules.content.application.use_cases.process_durable_work import ProcessOutboxEventUseCase
from src.modules.content.domain.entities import Card
from src.modules.content.domain.exceptions import CardCodeCapacityExhaustedError
from src.modules.content.domain.value_objects import (
    AbilityCode,
    CardImageFormat,
    CardImageMetadata,
    CardImageState,
    CardRarity,
    CardThumbnailMetadata,
    CardType,
)
from src.modules.content.infrastructure.repositories.mongo_card_projection import (
    MongoCardProjection,
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
from src.modules.content.infrastructure.repositories.sql_processing_transactions import (
    SqlCardImageProcessingTransactions,
    SqlOutboxProcessingTransactions,
)
from src.modules.content.infrastructure.services.pillow_image_processor import PillowImageProcessor
from src.modules.content.infrastructure.unit_of_work import SqlUnitOfWork
from src.shared.infrastructure.mongo import get_mongo_db
from src.shared.infrastructure.storage import LocalFileStorage

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_CONFIG = BACKEND_ROOT / "alembic.ini"


def _upgrade(sync_connection: Connection, target: str) -> None:
    config = Config(str(ALEMBIC_CONFIG))
    config.attributes["connection"] = sync_connection
    command.upgrade(config, target)


@pytest_asyncio.fixture(loop_scope="function")
async def migrated_database() -> AsyncIterator[AsyncEngine]:
    url = os.getenv("CONTENT_MIGRATION_TEST_URL")
    if not url:
        pytest.skip("Defina CONTENT_MIGRATION_TEST_URL para pruebas PostgreSQL aisladas.")

    schema_name = f"content_test_{uuid.uuid4().hex}"
    admin_engine = create_async_engine(url)
    async with admin_engine.begin() as admin_connection:
        await admin_connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
    await admin_engine.dispose()

    engine = create_async_engine(
        url,
        connect_args={"server_settings": {"search_path": schema_name}},
    )
    try:
        async with engine.connect() as connection:
            await connection.run_sync(lambda conn: _upgrade(conn, "001_initial_schema"))
            await connection.commit()
            await connection.execute(
                text(
                    "INSERT INTO catalog_cards "
                    "(id, code, name, cost, power, card_type, rarity, image_url, "
                    "thumbnail_url, ability_spec, created_at) "
                    "VALUES (:id, :code, 'Antigua', 2, 3, 'FUE', 'COMUN', '/old/a.webp', "
                    "'/old/a-thumb.webp', CAST(:ability AS json), now())"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "code": "PKA-FUE-013",
                    "ability": '{"ability_type":"HAB-000","description":"","params":{}}',
                },
            )
            await connection.execute(
                text(
                    "INSERT INTO catalog_cards "
                    "(id, code, name, cost, power, card_type, rarity, image_url, "
                    "thumbnail_url, ability_spec, created_at) "
                    "VALUES (:id, 'PKA-FUE-014', 'Ambigua', 3, 2, 'FUE', 'COMUN', "
                    "'/old/b.webp', NULL, CAST(:ability AS json), now())"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "ability": '{"ability_type":"AL_REVELARSE","params":{"x":1}}',
                },
            )
            await connection.execute(
                text(
                    "INSERT INTO catalog_cards "
                    "(id, code, name, cost, power, card_type, rarity, image_url, "
                    "thumbnail_url, ability_spec, created_at) "
                    "VALUES (:id, 'LEGACY-UNKNOWN', 'Incompatible', 3, 2, 'OLD', "
                    "'OLD_RARITY', '/old/c.webp', NULL, NULL, now())"
                ),
                {"id": str(uuid.uuid4())},
            )
            await connection.commit()
            await connection.run_sync(lambda conn: _upgrade(conn, "head"))
            await connection.commit()
        yield engine
    finally:
        await engine.dispose()
        admin_engine = create_async_engine(url)
        async with admin_engine.begin() as admin_connection:
            await admin_connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
        await admin_engine.dispose()


@pytest_asyncio.fixture(loop_scope="function")
async def empty_migrated_database() -> AsyncIterator[AsyncEngine]:
    """Aplica las dos revisiones sin filas legacy para cubrir una instalación limpia."""
    url = os.getenv("CONTENT_MIGRATION_TEST_URL")
    if not url:
        pytest.skip("Defina CONTENT_MIGRATION_TEST_URL para pruebas PostgreSQL aisladas.")

    schema_name = f"content_empty_test_{uuid.uuid4().hex}"
    admin_engine = create_async_engine(url)
    async with admin_engine.begin() as admin_connection:
        await admin_connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
    await admin_engine.dispose()

    engine = create_async_engine(
        url,
        connect_args={"server_settings": {"search_path": schema_name}},
    )
    try:
        async with engine.connect() as connection:
            await connection.run_sync(lambda conn: _upgrade(conn, "001_initial_schema"))
            await connection.commit()
            await connection.run_sync(lambda conn: _upgrade(conn, "head"))
            await connection.commit()
        yield engine
    finally:
        await engine.dispose()
        admin_engine = create_async_engine(url)
        async with admin_engine.begin() as admin_connection:
            await admin_connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
        await admin_engine.dispose()


async def _create_pending_card(engine: AsyncEngine, card_type: CardType) -> str:
    card_id = str(uuid.uuid4())
    image_id = str(uuid.uuid4())
    async with AsyncSession(engine, expire_on_commit=False, autoflush=False) as session:
        image_record = CardImageRecordDTO(
            id=image_id,
            original_storage_key=f"cards/{image_id}.webp",
            original_sha256="a" * 64,
            original_metadata=CardImageMetadata(
                image_format=CardImageFormat.WEBP,
                byte_size=12_000,
                width=600,
                height=840,
            ),
            state=CardImageState.PENDING,
        )
        image_repository = SqlCardImageRepository(session)
        card_repository = SqlCardRepository(session)
        allocator = SqlCardCodeAllocator(session)
        uow = SqlUnitOfWork(session)
        async with uow:
            await image_repository.save(image_record)
            assigned_code = await allocator.allocate_next(card_type)
            card = Card.create(
                code=assigned_code.value,
                name="Pendiente",
                cost=0,
                power=-1,
                card_type=card_type,
                rarity=CardRarity.COMUN,
                image_url=image_record.original_storage_key,
                ability_code=AbilityCode("HAB-000"),
                image_state=CardImageState.PENDING,
                image_metadata=image_record.original_metadata,
                card_id=card_id,
            )
            await card_repository.save(card, image_id)
        return card_id


@pytest.mark.asyncio
async def test_upgrade_preserves_legacy_rows_and_reports_ambiguous_data(
    migrated_database: AsyncEngine,
) -> None:
    async with migrated_database.connect() as connection:
        archived = (
            await connection.execute(
                text("SELECT code FROM catalog_cards_legacy_002 ORDER BY code")
            )
        ).scalars().all()
        issues = (
            await connection.execute(
                text("SELECT legacy_code, reason FROM catalog_card_migration_issues")
            )
        ).all()
        active_count = await connection.scalar(text("SELECT count(*) FROM catalog_cards"))
        ability_count = await connection.scalar(
            text("SELECT count(*) FROM catalog_abilities WHERE code = 'HAB-000'")
        )
        counter_count = await connection.scalar(
            text("SELECT count(*) FROM catalog_card_code_counters")
        )
        fuego_counter = await connection.scalar(
            text("SELECT last_value FROM catalog_card_code_counters WHERE card_type = 'FUE'")
        )

        assert archived == ["LEGACY-UNKNOWN", "PKA-FUE-013", "PKA-FUE-014"]
        assert active_count == 0
        assert len(issues) == 3
        issue_by_code = {issue.legacy_code: issue.reason for issue in issues}
        assert "HAB-000 explícito" in issue_by_code["PKA-FUE-013"]
        assert "sin mapeo aprobado" in issue_by_code["PKA-FUE-014"]
        assert "Código legado no oficial" in issue_by_code["LEGACY-UNKNOWN"]
        assert ability_count == 1
        assert counter_count == 6
        assert fuego_counter == 14

        async with AsyncSession(migrated_database, expire_on_commit=False) as session:
            ability_repository = SqlAbilityRepository(session)
            async with session.begin():
                await ability_repository.ensure_none_ability()
                await ability_repository.ensure_none_ability()

        await connection.run_sync(lambda conn: _upgrade(conn, "head"))
        await connection.commit()
        ability_count_after_repeat = await connection.scalar(
            text("SELECT count(*) FROM catalog_abilities WHERE code = 'HAB-000'")
        )
        assert ability_count_after_repeat == 1


@pytest.mark.asyncio
async def test_empty_database_upgrade_seeds_six_counters_and_hab000(
    empty_migrated_database: AsyncEngine,
) -> None:
    async with empty_migrated_database.connect() as connection:
        counters = (
            await connection.execute(
                text(
                    "SELECT card_type, last_value FROM catalog_card_code_counters "
                    "ORDER BY card_type"
                )
            )
        ).all()
        ability_count = await connection.scalar(
            text("SELECT count(*) FROM catalog_abilities WHERE code = 'HAB-000'")
        )
        issue_count = await connection.scalar(
            text("SELECT count(*) FROM catalog_card_migration_issues")
        )

    assert counters == [
        ("AGU", 0),
        ("ELE", 0),
        ("FUE", 0),
        ("LUC", 0),
        ("PLA", 0),
        ("PSI", 0),
    ]
    assert ability_count == 1
    assert issue_count == 0


@pytest.mark.asyncio
async def test_pending_card_reconstruction_keeps_ability_and_image_metadata(
    migrated_database: AsyncEngine,
) -> None:
    card_id = await _create_pending_card(migrated_database, CardType.AGUA)

    async with AsyncSession(migrated_database, expire_on_commit=False) as session:
        card = await SqlCardRepository(session).get_by_id(card_id)

    assert card is not None
    assert card.ability_code == AbilityCode("HAB-000")
    assert card.image_state is CardImageState.PENDING
    assert card.image_metadata == CardImageMetadata(
        image_format=CardImageFormat.WEBP, byte_size=12_000, width=600, height=840
    )
    assert card.thumbnail_metadata is None
    assert card.available_to_players is False


@pytest.mark.asyncio
async def test_concurrent_allocations_are_serialized_per_type(
    migrated_database: AsyncEngine,
) -> None:
    async def allocate(card_type: CardType) -> str:
        async with AsyncSession(
            migrated_database, expire_on_commit=False, autoflush=False
        ) as session:
            async with session.begin():
                return (await SqlCardCodeAllocator(session).allocate_next(card_type)).value

    same_type_codes = await asyncio.gather(*(allocate(CardType.LUCHA) for _ in range(6)))
    other_type_codes = await asyncio.gather(allocate(CardType.AGUA), allocate(CardType.PLANTA))

    assert len(set(same_type_codes)) == 6
    assert sorted(code[-3:] for code in same_type_codes) == [
        "001",
        "002",
        "003",
        "004",
        "005",
        "006",
    ]
    assert tuple(other_type_codes) == ("PKA-AGU-001", "PKA-PLA-001")


@pytest.mark.asyncio
async def test_rollback_after_allocation_does_not_consume_code(
    migrated_database: AsyncEngine,
) -> None:
    async with AsyncSession(
        migrated_database, expire_on_commit=False, autoflush=False
    ) as session:
        with pytest.raises(RuntimeError, match="simulated"):
            async with session.begin():
                await SqlCardCodeAllocator(session).allocate_next(CardType.ELECTRICO)
                raise RuntimeError("simulated persistence failure")
        async with session.begin():
            code = await SqlCardCodeAllocator(session).allocate_next(CardType.ELECTRICO)
        assert code.value == "PKA-ELE-001"


@pytest.mark.asyncio
async def test_database_constraints_reject_invalid_card_values_and_references(
    migrated_database: AsyncEngine,
) -> None:
    async with migrated_database.connect() as connection:
        async with connection.begin():
            image_id = str(uuid.uuid4())
            await connection.execute(
                text(
                    "INSERT INTO catalog_card_images "
                    "(id, original_storage_key, original_sha256, image_format, byte_size, "
                    "width, height, state, attempts, generation, created_at, updated_at) "
                    "VALUES (:id, 'x.webp', :sha, 'WEBP', 1, 600, 840, 'PENDING', "
                    "0, 0, now(), now())"
                ),
                {"id": image_id, "sha": "b" * 64},
            )

            async def expect_rejected(values: dict[str, Any]) -> None:
                with pytest.raises(IntegrityError):
                    async with connection.begin_nested():
                        await connection.execute(
                            text(
                                "INSERT INTO catalog_cards "
                                "(id, code, name, cost, power, card_type, rarity, ability_id, "
                                "image_id, version, created_at) "
                                "VALUES (:id, :code, 'Test', :cost, 1, :type, 'COMUN', "
                                ":ability, :image, 1, now())"
                            ),
                            values,
                        )

            base = {
                "id": str(uuid.uuid4()),
                "code": "PKA-FUE-001",
                "cost": 0,
                "type": "FUE",
                "ability": "00000000-0000-0000-0000-000000000000",
                "image": image_id,
            }
            await expect_rejected({**base, "cost": 11})
            await expect_rejected({**base, "id": str(uuid.uuid4()), "code": "PKA-AGU-001"})
            await expect_rejected({**base, "id": str(uuid.uuid4()), "ability": "missing-ability"})
            await expect_rejected({**base, "id": str(uuid.uuid4()), "image": str(uuid.uuid4())})

            valid_card = {**base, "id": str(uuid.uuid4())}
            await connection.execute(
                text(
                    "INSERT INTO catalog_cards "
                    "(id, code, name, cost, power, card_type, rarity, ability_id, image_id, "
                    "version, created_at) VALUES (:id, :code, 'Test', :cost, 1, :type, "
                    "'COMUN', :ability, :image, 1, now())"
                ),
                valid_card,
            )

            second_image_id = str(uuid.uuid4())
            await connection.execute(
                text(
                    "INSERT INTO catalog_card_images "
                    "(id, original_storage_key, original_sha256, image_format, byte_size, "
                    "width, height, state, attempts, generation, created_at, updated_at) "
                    "VALUES (:id, 'y.webp', :sha, 'WEBP', 1, 600, 840, 'PENDING', "
                    "0, 0, now(), now())"
                ),
                {"id": second_image_id, "sha": "c" * 64},
            )
            await expect_rejected(
                {
                    **base,
                    "id": str(uuid.uuid4()),
                    "image": second_image_id,
                }
            )


@pytest.mark.asyncio
async def test_capacity_999_rejects_without_increment(migrated_database: AsyncEngine) -> None:
    async with migrated_database.connect() as connection:
        await connection.execute(
            text("UPDATE catalog_card_code_counters SET last_value = 999 WHERE card_type = 'PSI'")
        )
        await connection.commit()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        with pytest.raises(CardCodeCapacityExhaustedError):
            async with session.begin():
                await SqlCardCodeAllocator(session).allocate_next(CardType.PSIQUICO)
        persisted = await session.scalar(
            text("SELECT last_value FROM catalog_card_code_counters WHERE card_type = 'PSI'")
        )
        assert persisted == 999
        await session.close()


@pytest.mark.asyncio
async def test_image_claim_is_exclusive_and_stale_lease_cannot_finish(
    empty_migrated_database: AsyncEngine,
) -> None:
    factory = async_sessionmaker(
        empty_migrated_database, expire_on_commit=False, autoflush=False
    )
    card_id = await _create_pending_card(empty_migrated_database, CardType.AGUA)
    transactions = SqlCardImageProcessingTransactions(factory)

    first, competing = await asyncio.gather(
        transactions.claim_next(), transactions.claim_next()
    )
    claims = [claim for claim in (first, competing) if claim is not None]
    assert len(claims) == 1
    stale = claims[0]

    async with empty_migrated_database.begin() as connection:
        await connection.execute(
            text(
                "UPDATE catalog_card_images SET lease_expires_at = now() - interval '1 second' "
                "WHERE id = :image_id"
            ),
            {"image_id": stale.image_id},
        )

    current = await transactions.claim_next()
    assert current is not None
    assert current.image_id == stale.image_id
    assert current.generation > stale.generation
    thumbnail_metadata = CardThumbnailMetadata(
        image_format=CardImageFormat.WEBP, byte_size=128, width=200, height=280
    )

    assert not await transactions.complete(stale, "/uploads/old.webp", thumbnail_metadata)
    assert await transactions.complete(current, "/uploads/current.webp", thumbnail_metadata)
    status = await transactions.get_status(card_id)

    assert status is not None
    assert status.image_status == CardImageState.READY.value
    assert status.available_to_players is True
    assert status.thumbnail_url == "/uploads/current.webp"
    assert status.version == 2
    async with empty_migrated_database.connect() as connection:
        assert await connection.scalar(text("SELECT count(*) FROM shared_outbox")) == 1


@pytest.mark.asyncio
async def test_failed_image_requeue_reuses_same_card_and_code(
    empty_migrated_database: AsyncEngine,
) -> None:
    factory = async_sessionmaker(
        empty_migrated_database, expire_on_commit=False, autoflush=False
    )
    card_id = await _create_pending_card(empty_migrated_database, CardType.FUEGO)
    async with empty_migrated_database.begin() as connection:
        await connection.execute(
            text(
                "UPDATE catalog_card_images SET state = 'FAILED', attempts = 5, "
                "sanitized_error = 'fallo' WHERE id = ("
                "SELECT image_id FROM catalog_cards WHERE id = :card_id)"
            ),
            {"card_id": card_id},
        )

    transactions = SqlCardImageProcessingTransactions(factory)
    assert await transactions.requeue_failed(card_id) is True
    assert await transactions.requeue_failed(card_id) is False
    status = await transactions.get_status(card_id)

    assert status is not None
    assert status.code == "PKA-FUE-001"
    assert status.image_status == CardImageState.PENDING.value
    assert status.attempts == 0
    assert status.version == 2
    async with empty_migrated_database.connect() as connection:
        assert await connection.scalar(text("SELECT count(*) FROM catalog_cards")) == 1
        assert await connection.scalar(text("SELECT count(*) FROM shared_outbox")) == 1


@pytest.mark.asyncio
async def test_image_failures_use_five_attempts_then_move_to_failed(
    empty_migrated_database: AsyncEngine,
) -> None:
    factory = async_sessionmaker(
        empty_migrated_database, expire_on_commit=False, autoflush=False
    )
    card_id = await _create_pending_card(empty_migrated_database, CardType.PSIQUICO)
    transactions = SqlCardImageProcessingTransactions(factory)

    for attempt in range(1, 6):
        claim = await transactions.claim_next()
        assert claim is not None
        assert claim.attempts == attempt
        assert await transactions.record_failure(claim, "fallo simulado") is True
        status = await transactions.get_status(card_id)
        assert status is not None
        if attempt < 5:
            assert status.image_status == CardImageState.RETRY_PENDING.value
            async with empty_migrated_database.begin() as connection:
                await connection.execute(
                    text(
                        "UPDATE catalog_card_images SET next_attempt_at = now() "
                        "WHERE id = :image_id"
                    ),
                    {"image_id": claim.image_id},
                )

    final_status = await transactions.get_status(card_id)
    assert final_status is not None
    assert final_status.image_status == CardImageState.FAILED.value
    assert final_status.attempts == 5
    assert await transactions.claim_next() is None


@pytest.mark.asyncio
async def test_restarted_workers_recover_image_and_project_ready_version(
    empty_migrated_database: AsyncEngine,
    tmp_path: Path,
) -> None:
    factory = async_sessionmaker(
        empty_migrated_database, expire_on_commit=False, autoflush=False
    )
    storage = LocalFileStorage(str(tmp_path))
    processor = PillowImageProcessor()
    original = io.BytesIO()
    Image.new("RGB", (600, 840), "orange").save(original, format="PNG")
    raw = original.getvalue()
    original_key = await storage.save_file(raw, ".png", "cards/originals")
    metadata = processor.inspect_card_image(raw)
    card_id = str(uuid.uuid4())
    image_id = str(uuid.uuid4())

    async with factory() as session:
        ability_repository = SqlAbilityRepository(session)
        image_repository = SqlCardImageRepository(session)
        card_repository = SqlCardRepository(session)
        allocator = SqlCardCodeAllocator(session)
        async with SqlUnitOfWork(session):
            await ability_repository.ensure_none_ability()
            ability = await ability_repository.get_by_code(AbilityCode("HAB-000"))
            assert ability is not None
            await image_repository.save(
                CardImageRecordDTO(
                    id=image_id,
                    original_storage_key=original_key,
                    original_sha256=hashlib.sha256(raw).hexdigest(),
                    original_metadata=metadata,
                )
            )
            code = await allocator.allocate_next(CardType.FUEGO)
            card = Card.create(
                code=code.value,
                name="Recuperable",
                cost=0,
                power=0,
                card_type=CardType.FUEGO,
                rarity=CardRarity.COMUN,
                image_url=original_key,
                ability_code=ability.code,
                image_state=CardImageState.PENDING,
                image_metadata=metadata,
                card_id=card_id,
            )
            await card_repository.save(card, image_id)

    image_transactions = SqlCardImageProcessingTransactions(factory)
    abandoned_claim = await image_transactions.claim_next()
    assert abandoned_claim is not None
    async with empty_migrated_database.begin() as connection:
        await connection.execute(
            text(
                "UPDATE catalog_card_images SET lease_expires_at = now() - interval '1 second' "
                "WHERE id = :image_id"
            ),
            {"image_id": image_id},
        )

    # A fresh worker recovers the expired lease after a simulated process stop.
    restarted_image_worker = ProcessCardImageUseCase(
        image_transactions, storage, processor, processor
    )
    assert await restarted_image_worker.execute_once() is True
    status = await image_transactions.get_status(card_id)
    assert status is not None
    assert status.image_status == CardImageState.READY.value
    assert status.available_to_players is True
    assert status.version == 2
    assert status.thumbnail_url is not None

    mongo_db = get_mongo_db()
    collection = mongo_db["cards_projection"]
    await collection.delete_one({"_id": card_id})
    try:
        projection = MongoCardProjection(mongo_db)
        outbox_transactions = SqlOutboxProcessingTransactions(factory)
        abandoned_event = await outbox_transactions.claim_next()
        assert abandoned_event is not None
        assert abandoned_event.aggregate_version == 2
        await projection.project_versioned(abandoned_event)
        async with empty_migrated_database.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE shared_outbox SET lease_expires_at = now() - interval '1 second' "
                    "WHERE id = :event_id"
                ),
                {"event_id": abandoned_event.id},
            )

        # Mongo was written before the simulated crash; redelivery safely ACKs it.
        restarted_outbox_worker = ProcessOutboxEventUseCase(outbox_transactions, projection)
        assert await restarted_outbox_worker.execute_once() is True
        document = await collection.find_one({"_id": card_id})
        assert document is not None
        assert document["aggregate_version"] == 2
        assert document["image_status"] == CardImageState.READY.value
        assert document["available_to_players"] is True
    finally:
        await collection.delete_one({"_id": card_id})
        await storage.delete_file(original_key)
        if status.thumbnail_url is not None:
            await storage.delete_file(status.thumbnail_url)
