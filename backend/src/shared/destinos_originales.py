"""Validación local de destinos protegidos, sin abrir conexiones."""

import os
import sys
from typing import Literal
from urllib.parse import parse_qsl, urlsplit

from sqlalchemy.engine import URL

ProcesoOriginal = Literal["api", "outbox"]
PG_ORIGINAL = ("127.0.0.1", 5432, "pokearena_db")
MONGO_ORIGINAL = ("127.0.0.1", 27017, "pokearena_catalog")
ROL_SQL_ORIGINAL = "poke_api_user"
ROL_MIGRADOR_ORIGINAL = "pokearena_original_migrator"
ROLES_MONGO_ORIGINAL = {"api": "poke_api_mongo", "outbox": "poke_outbox_mongo"}
_LOOPBACK = {"127.0.0.1", "localhost", "::1"}


def postgres_protegido(url: URL) -> bool:
    """Detecta la base original, puertos locales originales y rutas alternativas."""
    if (url.database or "").startswith("pokearena_alembic_") or (url.database or "") in {"unused", "test"}:
        return False
    return (
        url.database == PG_ORIGINAL[2]
        or (
            url.host in _LOOPBACK | {"postgres", "pokearena-postgres", None}
            and url.port in {None, 5432}
        )
        or bool({"host", "port", "dbname", "user", "service"} & url.query.keys())
    )


def validar_acceso_original(
    pg: URL, mongo_url: str, mongo_db: str, entorno: str,
    modo: Literal["disabled", "api", "outbox"],
) -> None:
    """Exige un par original exacto o mantiene ambos destinos fuera de ese par."""
    from pymongo.errors import PyMongoError
    from pymongo.uri_parser import parse_uri

    try:
        mongo = parse_uri(mongo_url, warn=False) if mongo_url.startswith("mongodb://") else None
        uri = urlsplit(mongo_url)
    except (PyMongoError, ValueError):
        raise ValueError("destino_mongodb_invalido") from None
    destino_mongo = mongo["database"] if mongo is not None else uri.path.lstrip("/")
    es_mongo_aislado = (
        mongo_db.startswith("pokearena_catalog_frontend")
        or destino_mongo.startswith("pokearena_catalog_frontend")
    )
    mongo_protegido = (
        not es_mongo_aislado
        and (
            MONGO_ORIGINAL[2] in (mongo_db, destino_mongo)
            or (
                mongo is not None
                and any(
                    host in _LOOPBACK | {"mongo", "pokearena-mongo"} and port == 27017
                    for host, port in mongo["nodelist"]
                )
            )
        )
    )
    if modo == "disabled" and not (postgres_protegido(pg) or mongo_protegido):
        return
    if (
        modo == "disabled" or entorno != "development"
        or (pg.host, pg.port, pg.database) != PG_ORIGINAL
        or pg.drivername != "postgresql+asyncpg" or pg.username != ROL_SQL_ORIGINAL
        or not pg.password or pg.query
        or mongo is None or mongo["nodelist"] != [MONGO_ORIGINAL[:2]]
        or mongo["database"] != MONGO_ORIGINAL[2] or mongo_db != MONGO_ORIGINAL[2]
        or mongo["username"] != ROLES_MONGO_ORIGINAL[modo] or not mongo["password"]
        or len(parse_qsl(uri.query)) != 2
        or {k.lower() for k in mongo["options"]} != {"authsource", "directconnection"}
        or mongo["options"].get("authSource") != MONGO_ORIGINAL[2]
        or mongo["options"].get("directConnection") is not True
    ):
        raise ValueError("destinos_originales_no_autorizados")


def impedir_originales_en_pruebas() -> None:
    """Bloquea I/O original desde pytest, incluso con opt-in y entorno heredados."""
    if "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST"):
        raise ValueError("destinos_originales_bloqueados_en_pruebas")
