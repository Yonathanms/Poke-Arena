"""Allow creating card drafts before the image V2 integration.

Revision ID: 007_cards_without_image
Revises: 006_identity_local_test_provider
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "007_cards_without_image"
down_revision: str | None = "006_identity_local_test_provider"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "catalog_cards",
        "image_id",
        existing_type=sa.String(length=36),
        nullable=True,
    )


def downgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM catalog_cards WHERE image_id IS NULL) "
        "THEN RAISE EXCEPTION "
        "'No se puede volver a exigir imagen mientras existan cartas sin imagen'; "
        "END IF; END $$"
    )
    op.alter_column(
        "catalog_cards",
        "image_id",
        existing_type=sa.String(length=36),
        nullable=False,
    )
