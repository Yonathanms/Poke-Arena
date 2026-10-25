"""Add description, card_limit and energy_bonus_spec to catalog_locations.

Revision ID: 009_location_extended_fields
Revises: 008_flex_card_img_dims
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "009_location_extended_fields"
down_revision: str = "008_flex_card_img_dims"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "catalog_locations",
        sa.Column("description", sa.String(500), nullable=False, server_default=""),
    )
    op.add_column(
        "catalog_locations",
        sa.Column("card_limit", sa.SmallInteger, nullable=False, server_default="5"),
    )
    op.add_column(
        "catalog_locations",
        sa.Column("energy_bonus_spec", sa.JSON, nullable=True),
    )
    op.create_check_constraint(
        "ck_catalog_locations_card_limit",
        "catalog_locations",
        "card_limit BETWEEN 0 AND 5",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_catalog_locations_card_limit", "catalog_locations", type_="check"
    )
    op.drop_column("catalog_locations", "energy_bonus_spec")
    op.drop_column("catalog_locations", "card_limit")
    op.drop_column("catalog_locations", "description")
