"""Verificación de la identidad observada en una conexión PostgreSQL original."""

from sqlalchemy import text

from src.shared.destinos_originales import PG_ORIGINAL, ROL_SQL_ORIGINAL, ProcesoOriginal

IDENTIDAD_SQL = text(
    "SELECT current_database(), current_user, inet_server_port(), rolsuper, "
    "rolcreatedb, rolcreaterole, rolreplication, rolbypassrls "
    "FROM pg_roles WHERE rolname = current_user"
)


def identidad_original_valida(datos: tuple[object, ...], rol: str) -> bool:
    """El servidor debe confirmar base, rol, puerto y ausencia de privilegios globales."""
    return datos[:3] == (PG_ORIGINAL[2], rol, PG_ORIGINAL[1]) and datos[3:] == (False,) * 5


def destino_original_activo(datos: tuple[object, ...], proceso: ProcesoOriginal) -> bool:
    """Un rol correcto también necesita el opt-in del proceso que abrió la conexión."""
    from src.shared.config import get_settings

    return (
        identidad_original_valida(datos, ROL_SQL_ORIGINAL)
        and get_settings().ORIGINAL_RUNTIME == proceso
    )
