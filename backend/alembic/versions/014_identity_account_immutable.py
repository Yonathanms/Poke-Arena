"""Protege el tipo permanente y la identidad estable de la cuenta."""

from alembic import op

revision = "014_identity_account_immutable"
down_revision = "013_initial_pack_opened_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Protege cuentas futuras e históricas sin reescribir sus datos."""
    op.execute("""
        CREATE FUNCTION public.reject_identity_account_change() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'El tipo y la clave de identidad son permanentes'
                USING ERRCODE = '23514', CONSTRAINT = 'identity_account_immutable';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_identity_account_immutable
        AFTER UPDATE ON public.identity_users
        FOR EACH ROW
        WHEN ((OLD.id, OLD.provider, OLD.provider_subject, OLD.role)
              IS DISTINCT FROM (NEW.id, NEW.provider, NEW.provider_subject, NEW.role))
        EXECUTE FUNCTION public.reject_identity_account_change()
    """)
    op.execute("""
        DO $$
        DECLARE rol_aplicacion name;
        BEGIN
            FOR rol_aplicacion IN
                SELECT rolname FROM pg_roles WHERE rolname IN ('orm_media_test', 'poke_api_user')
            LOOP
                EXECUTE format(
                    'REVOKE UPDATE, DELETE, TRUNCATE ON public.identity_users FROM %I',
                    rol_aplicacion
                );
                EXECUTE format(
                    'REVOKE UPDATE (id, provider, provider_subject, role, created_at,
                                    local_password_hash)
                     ON public.identity_users FROM %I', rol_aplicacion
                );
                EXECUTE format(
                    'GRANT UPDATE (email, updated_at, local_failed_attempts, local_blocked_until)
                     ON public.identity_users TO %I', rol_aplicacion
                );
            END LOOP;
        END;
        $$
    """)


def downgrade() -> None:
    """Retira el trigger y conserva los permisos de aplicación restringidos."""
    op.execute("DROP TRIGGER trg_identity_account_immutable ON public.identity_users")
    op.execute("DROP FUNCTION public.reject_identity_account_change()")
