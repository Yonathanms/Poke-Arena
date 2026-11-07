"""Durable image and outbox processing leases.

Revision ID: 004_processing_recovery
Revises: 003_creation_idempotency_outbox
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "004_processing_recovery"
down_revision: str | None = "003_creation_idempotency_outbox"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "shared_outbox",
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("shared_outbox", sa.Column("next_attempt_at", sa.DateTime(timezone=True)))
    op.add_column("shared_outbox", sa.Column("lease_token", sa.String(36)))
    op.add_column("shared_outbox", sa.Column("lease_expires_at", sa.DateTime(timezone=True)))
    op.add_column("shared_outbox", sa.Column("sanitized_error", sa.String(500)))
    op.create_check_constraint("ck_shared_outbox_attempts", "shared_outbox", "attempts >= 0")
    op.create_index(
        "ix_shared_outbox_claim",
        "shared_outbox",
        ["status", "next_attempt_at", "lease_expires_at", "created_at"],
    )
    op.create_index(
        "ix_catalog_card_images_claim",
        "catalog_card_images",
        ["state", "next_attempt_at", "lease_expires_at", "created_at"],
    )
    op.alter_column("shared_outbox", "attempts", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_catalog_card_images_claim", table_name="catalog_card_images")
    op.drop_index("ix_shared_outbox_claim", table_name="shared_outbox")
    op.drop_constraint("ck_shared_outbox_attempts", "shared_outbox", type_="check")
    op.drop_column("shared_outbox", "sanitized_error")
    op.drop_column("shared_outbox", "lease_expires_at")
    op.drop_column("shared_outbox", "lease_token")
    op.drop_column("shared_outbox", "next_attempt_at")
    op.drop_column("shared_outbox", "attempts")
