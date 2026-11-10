"""Persiste la apertura del paquete inicial de forma independiente del premio."""

import sqlalchemy as sa
from alembic import op

revision = "013_initial_pack_opened_at"
down_revision = "012_player_profiles_inventory"
branch_labels = None
depends_on = None

_TABLA = "player_profiles"
_CHECK = "ck_player_profiles_initial_pack_opened"


def upgrade() -> None:
    """Conserva los premios históricos y deja la apertura pendiente."""
    op.add_column(_TABLA, sa.Column("initial_pack_opened_at", sa.DateTime(timezone=True)))
    op.create_check_constraint(
        "ck_player_profiles_initial_pack_opened",
        _TABLA,
        "initial_pack_opened_at IS NULL OR has_received_initial_collection",
    )


def downgrade() -> None:
    """Retira solo el estado de apertura."""
    op.drop_constraint(_CHECK, _TABLA, type_="check")
    op.drop_column(_TABLA, "initial_pack_opened_at")
