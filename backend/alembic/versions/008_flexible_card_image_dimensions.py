"""Allow moderately flexible card image dimensions and aspect ratio.

Revision ID: 008_flex_card_img_dims
Revises: 007_cards_without_image
"""

from collections.abc import Sequence

from alembic import op

revision: str = "008_flex_card_img_dims"
down_revision: str | None = "007_cards_without_image"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_catalog_card_images_aspect", "catalog_card_images", type_="check"
    )
    op.create_check_constraint(
        "ck_catalog_card_images_aspect",
        "catalog_card_images",
        "width >= 300 AND height >= 420 "
        "AND width * 28 >= height * 19 AND width * 28 <= height * 21",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_catalog_card_images_aspect", "catalog_card_images", type_="check"
    )
    op.create_check_constraint(
        "ck_catalog_card_images_aspect",
        "catalog_card_images",
        "width >= 600 AND height >= 840 AND width * 7 = height * 5",
    )
