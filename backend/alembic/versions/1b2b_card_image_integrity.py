"""Enforce the original aspect ratio and complete READY thumbnails.

Revision ID: 1b2b_card_image_integrity
Revises: 008_flex_card_img_dims
"""

from alembic import op

revision = "1b2b_card_image_integrity"
down_revision = "008_flex_card_img_dims"
branch_labels = None
depends_on = None

TABLE = "catalog_card_images"


def upgrade() -> None:
    """Replace two validated checks atomically without rewriting any rows.

    PostgreSQL validates existing rows when adding each check. A violation
    aborts the transaction, including any constraint replacement already done.
    """
    op.drop_constraint("ck_catalog_card_images_aspect", TABLE, type_="check")
    op.create_check_constraint(
        "ck_catalog_card_images_aspect",
        TABLE,
        "width >= 600 AND height >= 840 "
        "AND CAST(width AS bigint) * 7 = CAST(height AS bigint) * 5",
    )
    op.drop_constraint("ck_catalog_card_images_ready_thumbnail", TABLE, type_="check")
    op.create_check_constraint(
        "ck_catalog_card_images_ready_thumbnail",
        TABLE,
        "state <> 'READY' OR (thumbnail_storage_key IS NOT NULL "
        "AND thumbnail_format IS NOT NULL AND thumbnail_byte_size IS NOT NULL "
        "AND thumbnail_byte_size > 0 AND thumbnail_width IS NOT NULL "
        "AND thumbnail_height IS NOT NULL AND thumbnail_width = 200 AND thumbnail_height = 280)",
    )


def downgrade() -> None:
    """Restore 008 checks, including its integer arithmetic and NULL semantics.

    Very large dimensions accepted by the new check can overflow 008's
    arithmetic. In that case PostgreSQL aborts the downgrade without data loss.
    """
    op.drop_constraint("ck_catalog_card_images_aspect", TABLE, type_="check")
    op.create_check_constraint(
        "ck_catalog_card_images_aspect",
        TABLE,
        "width >= 300 AND height >= 420 "
        "AND width * 28 >= height * 19 AND width * 28 <= height * 21",
    )
    op.drop_constraint("ck_catalog_card_images_ready_thumbnail", TABLE, type_="check")
    op.create_check_constraint(
        "ck_catalog_card_images_ready_thumbnail",
        TABLE,
        "state <> 'READY' OR (thumbnail_storage_key IS NOT NULL "
        "AND thumbnail_format IS NOT NULL AND thumbnail_byte_size > 0 "
        "AND thumbnail_width = 200 AND thumbnail_height = 280)",
    )
