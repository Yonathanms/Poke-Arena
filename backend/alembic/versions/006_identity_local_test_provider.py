"""Allow isolated local/test Identity sessions.

Revision ID: 006_identity_local_test_provider
Revises: 005_identity_sessions
"""

from collections.abc import Sequence

from alembic import op

revision: str = "006_identity_local_test_provider"
down_revision: str | None = "005_identity_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_identity_users_provider", "identity_users", type_="check")
    op.create_check_constraint(
        "ck_identity_users_provider",
        "identity_users",
        "provider IN ('GOOGLE', 'TEST')",
    )


def downgrade() -> None:
    # Reinstating the GOOGLE-only constraint fails safely if TEST identities remain.
    op.drop_constraint("ck_identity_users_provider", "identity_users", type_="check")
    op.create_check_constraint(
        "ck_identity_users_provider", "identity_users", "provider = 'GOOGLE'"
    )
