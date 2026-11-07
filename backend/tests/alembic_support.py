"""Inspección de solo lectura para comparar esquemas sin modelos ORM ni datos de negocio."""

import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

SCHEMA_QUERIES = {
    "tables": """SELECT c.relname AS name FROM pg_class c
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relkind='r' ORDER BY c.relname""",
    "columns": """SELECT c.relname AS table_name,a.attname AS name,a.attnum AS position,
        format_type(a.atttypid,a.atttypmod) AS type,a.attnotnull AS not_null,
        pg_get_expr(d.adbin,d.adrelid) AS default_value,
        a.attidentity AS identity,a.attgenerated AS generated
        FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        LEFT JOIN pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum
        WHERE n.nspname='public' AND c.relkind='r' AND a.attnum>0 AND NOT a.attisdropped
        ORDER BY c.relname,a.attnum""",
    "constraints": """SELECT c.relname AS table_name,k.conname AS name,k.contype AS type,
        pg_get_constraintdef(k.oid) AS definition,k.condeferrable AS deferrable,
        k.condeferred AS deferred,k.convalidated AS validated
        FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' ORDER BY c.relname,k.conname""",
    "indexes": """SELECT tablename AS table_name,indexname AS name,indexdef AS definition
        FROM pg_indexes WHERE schemaname='public' ORDER BY tablename,indexname""",
    "functions": """SELECT p.proname AS name,pg_get_functiondef(p.oid) AS definition
        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname='public' AND p.prokind='f' ORDER BY p.proname""",
    "triggers": """SELECT c.relname AS table_name,t.tgname AS name,
        pg_get_triggerdef(t.oid) AS definition
        FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND NOT t.tgisinternal ORDER BY c.relname,t.tgname""",
}


def normalize_sql(value: str) -> str:
    """Normaliza únicamente casts de arrays de literales de texto equivalentes.

    PostgreSQL puede deparsear ANY como cast de un array o casts por elemento.
    Se conservan sus literales y orden; tipos de columnas se comparan por separado.
    No se normalizan nombres, rangos, expresiones arbitrarias ni claves.
    """
    def canonical(match: re.Match[str]) -> str:
        """Retiene los valores y orden de cada array literal inspeccionado."""
        literals = re.findall(r"'(?:[^']|'')*'", match.group(1))
        return "ARRAY[" + ",".join(literals) + "]"

    value = re.sub(r"\(ARRAY\[([^\]]+)\]\)::text\[\]", canonical, value)
    return re.sub(r"ARRAY\[([^\]]+)\]", canonical, value)


def snapshot_schema(connection: Connection) -> dict[str, list[dict[str, Any]]]:
    """Lee tablas, columnas, constraints, índices, funciones y triggers de public.

    No ejecuta DDL/DML ni inspecciona registros de negocio. Excluye propietarios
    y ACL: el rol aislado y los permisos técnicos de 1A difieren intencionalmente.
    Requiere conexión SQLAlchemy abierta; propaga errores de lectura.
    """
    result = {}
    for name, query in SCHEMA_QUERIES.items():
        rows = [
            {
                key: value.decode() if isinstance(value, bytes) else value
                for key, value in row.items()
            }
            for row in connection.execute(text(query)).mappings()
        ]
        for row in rows:
            if isinstance(row.get("definition"), str):
                row["definition"] = normalize_sql(row["definition"])
        result[name] = rows
    return result
