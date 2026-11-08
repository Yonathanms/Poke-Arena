"""Añade un único administrador LOCAL y el presupuesto durable de autenticación."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "1g_local_master_admin"
down_revision: str = "1b2b_card_image_integrity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "identity_users"
_PROVIDER = "ck_identity_users_provider"


def upgrade() -> None:
    """Preserva identidades GOOGLE/TEST y habilita el aprovisionamiento explícito."""
    op.add_column(_TABLE, sa.Column("local_password_hash", sa.String(256)))
    op.add_column(_TABLE, sa.Column("local_failed_attempts", sa.Integer()))
    op.add_column(_TABLE, sa.Column("local_blocked_until", sa.DateTime(timezone=True)))
    op.drop_constraint(_PROVIDER, _TABLE, type_="check")
    op.create_check_constraint(
        "ck_identity_users_provider", _TABLE, "provider IN ('GOOGLE', 'TEST', 'LOCAL')"
    )
    op.create_check_constraint(
        "ck_identity_users_local_credentials",
        _TABLE,
        "(provider = 'LOCAL' AND local_password_hash IS NOT NULL "
        "AND local_failed_attempts IS NOT NULL AND local_failed_attempts BETWEEN 0 AND 5) OR "
        "(provider <> 'LOCAL' AND local_password_hash IS NULL AND local_failed_attempts IS NULL "
        "AND local_blocked_until IS NULL)",
    )
    op.create_index(
        "uq_identity_local_master",
        _TABLE,
        ["provider"],
        unique=True,
        postgresql_where=sa.text("provider = 'LOCAL'"),
    )


def downgrade() -> None:
    """Restituye el esquema previo si no hay una identidad LOCAL que preservar."""
    if op.get_bind().scalar(
        sa.text("SELECT EXISTS (SELECT 1 FROM identity_users WHERE provider = 'LOCAL')")
    ):
        raise RuntimeError("El administrador LOCAL requiere conciliación antes del downgrade")
    op.drop_index("uq_identity_local_master", table_name=_TABLE)
    op.drop_constraint("ck_identity_users_local_credentials", _TABLE, type_="check")
    op.drop_constraint(_PROVIDER, _TABLE, type_="check")
    op.create_check_constraint(_PROVIDER, _TABLE, "provider IN ('GOOGLE', 'TEST')")
    op.drop_column(_TABLE, "local_blocked_until")
    op.drop_column(_TABLE, "local_failed_attempts")
    op.drop_column(_TABLE, "local_password_hash")
