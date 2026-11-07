"""Transactional idempotency and versioned outbox envelope.

Revision ID: 003_creation_idempotency_outbox
Revises: 002_content_card_persistence
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "003_creation_idempotency_outbox"
down_revision: str | None = "002_content_card_persistence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("shared_idempotency_records", sa.Column("id", sa.String(36), nullable=True))
    op.add_column(
        "shared_idempotency_records", sa.Column("actor_id", sa.String(128), nullable=True)
    )
    op.add_column(
        "shared_idempotency_records", sa.Column("operation", sa.String(200), nullable=True)
    )
    op.add_column(
        "shared_idempotency_records", sa.Column("request_hash", sa.String(64), nullable=True)
    )
    op.add_column(
        "shared_idempotency_records", sa.Column("resource_id", sa.String(36), nullable=True)
    )
    op.execute(
        "UPDATE shared_idempotency_records SET id = md5(idempotency_key), "
        "actor_id = '__legacy__', operation = endpoint, request_hash = repeat('0', 64)"
    )
    op.alter_column("shared_idempotency_records", "id", nullable=False)
    op.alter_column("shared_idempotency_records", "actor_id", nullable=False)
    op.alter_column("shared_idempotency_records", "operation", nullable=False)
    op.alter_column("shared_idempotency_records", "request_hash", nullable=False)
    op.drop_constraint(
        "shared_idempotency_records_pkey", "shared_idempotency_records", type_="primary"
    )
    op.create_primary_key("pk_shared_idempotency_records", "shared_idempotency_records", ["id"])
    op.create_unique_constraint(
        "uq_shared_idempotency_scope",
        "shared_idempotency_records",
        ["actor_id", "operation", "idempotency_key"],
    )
    op.alter_column("shared_idempotency_records", "response_status", nullable=True)
    op.alter_column(
        "shared_idempotency_records",
        "response_body",
        type_=postgresql.JSONB(),
        existing_type=sa.JSON(),
        postgresql_using="response_body::jsonb",
    )
    op.alter_column("shared_idempotency_records", "response_body", nullable=True)
    op.create_check_constraint(
        "ck_shared_idempotency_response_pair",
        "shared_idempotency_records",
        "(response_status IS NULL AND response_body IS NULL) OR "
        "(response_status IS NOT NULL AND response_body IS NOT NULL)",
    )

    op.add_column("shared_outbox", sa.Column("aggregate_type", sa.String(60), nullable=True))
    op.add_column("shared_outbox", sa.Column("aggregate_id", sa.String(36), nullable=True))
    op.add_column("shared_outbox", sa.Column("aggregate_version", sa.Integer(), nullable=True))
    op.add_column("shared_outbox", sa.Column("schema_version", sa.Integer(), nullable=True))
    op.add_column("shared_outbox", sa.Column("correlation_id", sa.String(36), nullable=True))
    op.alter_column(
        "shared_outbox",
        "payload",
        type_=postgresql.JSONB(),
        existing_type=sa.JSON(),
        postgresql_using="payload::jsonb",
    )
    op.execute(
        "UPDATE shared_outbox SET aggregate_type = 'legacy', aggregate_id = id, "
        "aggregate_version = 1, schema_version = 1"
    )
    for column in ("aggregate_type", "aggregate_id", "aggregate_version", "schema_version"):
        op.alter_column("shared_outbox", column, nullable=False)
    op.create_unique_constraint(
        "uq_shared_outbox_aggregate_version",
        "shared_outbox",
        ["aggregate_type", "aggregate_id", "aggregate_version"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_shared_outbox_aggregate_version", "shared_outbox", type_="unique")
    op.alter_column(
        "shared_outbox",
        "payload",
        type_=sa.JSON(),
        existing_type=postgresql.JSONB(),
        postgresql_using="payload::json",
    )
    op.drop_column("shared_outbox", "correlation_id")
    op.drop_column("shared_outbox", "schema_version")
    op.drop_column("shared_outbox", "aggregate_version")
    op.drop_column("shared_outbox", "aggregate_id")
    op.drop_column("shared_outbox", "aggregate_type")
    op.drop_constraint(
        "ck_shared_idempotency_response_pair", "shared_idempotency_records", type_="check"
    )
    op.alter_column("shared_idempotency_records", "response_body", nullable=False)
    op.alter_column(
        "shared_idempotency_records",
        "response_body",
        type_=sa.JSON(),
        existing_type=postgresql.JSONB(),
        postgresql_using="response_body::json",
    )
    op.alter_column("shared_idempotency_records", "response_status", nullable=False)
    op.drop_constraint("uq_shared_idempotency_scope", "shared_idempotency_records", type_="unique")
    op.drop_constraint(
        "pk_shared_idempotency_records", "shared_idempotency_records", type_="primary"
    )
    op.create_primary_key(
        "shared_idempotency_records_pkey", "shared_idempotency_records", ["idempotency_key"]
    )
    op.drop_column("shared_idempotency_records", "resource_id")
    op.drop_column("shared_idempotency_records", "request_hash")
    op.drop_column("shared_idempotency_records", "operation")
    op.drop_column("shared_idempotency_records", "actor_id")
    op.drop_column("shared_idempotency_records", "id")
