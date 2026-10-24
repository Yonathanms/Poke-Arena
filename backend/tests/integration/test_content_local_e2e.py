"""Local full lifecycle test using an isolated schema, Mongo database, and storage root."""

import io
import os
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient
from PIL import Image
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from alembic import command
from src.modules.content.application.use_cases.create_card import CreateCardUseCase
from src.modules.content.application.use_cases.list_abilities import ListCardAbilitiesUseCase
from src.modules.content.application.use_cases.process_card_image import ProcessCardImageUseCase
from src.modules.content.application.use_cases.process_durable_work import (
    GetCardImageStatusUseCase,
    ProcessOutboxEventUseCase,
)
from src.modules.content.composition import (
    build_card_persistence_adapters,
    get_card_image_status_use_case,
    get_create_card_use_case,
    get_list_card_abilities_use_case,
)
from src.modules.content.infrastructure.repositories.mongo_card_projection import (
    MongoCardProjection,
)
from src.modules.content.infrastructure.repositories.sql_ability_repository import (
    SqlAbilityRepository,
)
from src.modules.content.infrastructure.repositories.sql_creation_records import (
    SqlCardCreationIdempotencyAdapter,
    SqlOutboxWriter,
)
from src.modules.content.infrastructure.repositories.sql_processing_transactions import (
    SqlCardImageProcessingTransactions,
    SqlOutboxProcessingTransactions,
)
from src.modules.content.infrastructure.services.pillow_image_processor import PillowImageProcessor
from src.modules.content.presentation.routers import content_router
from src.modules.identity.application.service import IdentityApplicationService
from src.modules.identity.composition import (
    get_identity_application_service,
    register_identity_module,
)
from src.modules.identity.infrastructure.google_identity_provider import GoogleIdentityProvider
from src.modules.identity.infrastructure.opaque_access_token_factory import OpaqueAccessTokenFactory
from src.modules.identity.infrastructure.sql_identity_persistence import SqlIdentityPersistence
from src.modules.identity.presentation.routers import local_test_identity_router
from src.shared.infrastructure.config import get_settings
from src.shared.infrastructure.storage import LocalFileStorage
from src.shared.presentation.exception_handlers import register_exception_handlers

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_CONFIG = BACKEND_ROOT / "alembic.ini"


def _upgrade(connection: Connection) -> None:
    config = Config(str(ALEMBIC_CONFIG))
    config.attributes["connection"] = connection
    command.upgrade(config, "head")


@pytest_asyncio.fixture(loop_scope="function")
async def isolated_postgres() -> AsyncIterator[
    tuple[AsyncEngine, async_sessionmaker[AsyncSession]]
]:
    if os.getenv("RUN_LOCAL_CONTENT_E2E") != "1":
        pytest.skip("Defina RUN_LOCAL_CONTENT_E2E=1 para ejecutar la prueba E2E local aislada.")
    database_url = os.getenv("CONTENT_MIGRATION_TEST_URL") or get_settings().DATABASE_WRITE_URL
    schema = f"content_local_e2e_{uuid.uuid4().hex}"
    admin_engine = create_async_engine(database_url)
    async with admin_engine.begin() as connection:
        await connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    engine = create_async_engine(
        database_url,
        connect_args={"server_settings": {"search_path": schema}},
    )
    try:
        async with engine.connect() as connection:
            await connection.run_sync(_upgrade)
            await connection.commit()
        yield engine, async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    finally:
        await engine.dispose()
        async with admin_engine.begin() as connection:
            await connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
        await admin_engine.dispose()


def _png_image() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (600, 840), color="orange").save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_local_admin_creates_card_processes_image_and_projects_ready_snapshot(
    isolated_postgres: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    tmp_path: Path,
) -> None:
    _, session_factory = isolated_postgres
    settings = get_settings()
    mongo_client = AsyncIOMotorClient(settings.MONGO_URL, serverSelectionTimeoutMS=3000)
    mongo_name = f"pokearena_e2e_{uuid.uuid4().hex}"
    mongo_db = mongo_client[mongo_name]
    storage = LocalFileStorage(str(tmp_path / "uploads"))
    processor = PillowImageProcessor()
    identity_service = IdentityApplicationService(
        google_provider=GoogleIdentityProvider(None),
        persistence=SqlIdentityPersistence(session_factory),
        token_factory=OpaqueAccessTokenFactory(),
        platform_admin_subjects=frozenset(),
        access_token_ttl_seconds=900,
        allow_test_identity=True,
    )
    test_app = FastAPI()
    register_exception_handlers(test_app)
    register_identity_module(test_app, identity_service)
    test_app.include_router(content_router, prefix="/api/v1")
    test_app.include_router(local_test_identity_router, prefix="/api/v1")

    async def provide_identity() -> IdentityApplicationService:
        return identity_service

    async def provide_create_card() -> AsyncIterator[CreateCardUseCase]:
        async with session_factory() as session:
            adapters = build_card_persistence_adapters(session)
            yield CreateCardUseCase(
                uow=adapters.uow,
                card_repo=adapters.card_repository,
                code_allocator=adapters.code_allocator,
                ability_repo=adapters.ability_repository,
                image_repo=adapters.image_repository,
                idempotency=SqlCardCreationIdempotencyAdapter(session, session_factory),
                outbox=SqlOutboxWriter(session),
                image_inspector=processor,
                file_storage=storage,
            )

    async def provide_abilities() -> AsyncIterator[ListCardAbilitiesUseCase]:
        async with session_factory() as session:
            yield ListCardAbilitiesUseCase(SqlAbilityRepository(session))

    def provide_status() -> GetCardImageStatusUseCase:
        return GetCardImageStatusUseCase(SqlCardImageProcessingTransactions(session_factory))

    test_app.dependency_overrides[get_identity_application_service] = provide_identity
    test_app.dependency_overrides[get_create_card_use_case] = provide_create_card
    test_app.dependency_overrides[get_list_card_abilities_use_case] = provide_abilities
    test_app.dependency_overrides[get_card_image_status_use_case] = provide_status

    try:
        await mongo_client.admin.command("ping")
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://local-test") as client:
            login = await client.post("/api/v1/identity/test-session", json={})
            assert login.status_code == 201
            assert login.json()["role"] == "PLATFORM_ADMIN"
            auth_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            abilities = await client.get("/api/v1/content/abilities", headers=auth_headers)
            assert abilities.status_code == 200
            assert any(item["code"] == "HAB-000" for item in abilities.json())

            created = await client.post(
                "/api/v1/content/cards",
                headers={**auth_headers, "Idempotency-Key": "local-e2e-create-card"},
                data={
                    "name": "Pikachu local",
                    "cost": "0",
                    "power": "4",
                    "card_type": "FUE",
                    "rarity": "COMUN",
                    "ability_code": "HAB-000",
                },
                files={"image": ("pikachu.png", _png_image(), "image/png")},
            )
            assert created.status_code == 201, created.text
            pending = created.json()
            assert pending["image_status"] == "PENDING"
            assert pending["available_to_players"] is False
            assert pending["code"] == "PKA-FUE-001"

            image_worker = ProcessCardImageUseCase(
                SqlCardImageProcessingTransactions(session_factory), storage, processor, processor
            )
            assert await image_worker.execute_once() is True
            outbox_worker = ProcessOutboxEventUseCase(
                SqlOutboxProcessingTransactions(session_factory), MongoCardProjection(mongo_db)
            )
            for _ in range(4):
                if not await outbox_worker.execute_once():
                    break

            status_response = await client.get(pending["status_url"], headers=auth_headers)
            assert status_response.status_code == 200
            ready = status_response.json()
            assert ready["image_status"] == "READY"
            assert ready["available_to_players"] is True
            assert ready["thumbnail_url"]

            projection = await mongo_db["cards_projection"].find_one({"_id": pending["id"]})
            assert projection is not None
            assert projection["image_status"] == "READY"
            assert projection["aggregate_version"] == 2
            assert projection["code"] == pending["code"]
    finally:
        await mongo_client.drop_database(mongo_name)
        mongo_client.close()
