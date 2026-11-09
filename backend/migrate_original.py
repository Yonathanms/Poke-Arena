"""Punto de entrada del corte PostgreSQL 008 → 014."""

import argparse
import sys

from src.database.postgresql.migracion_original import ejecutar_upgrade_original


def main() -> int:
    """Ejecuta la única operación de corte, con diagnóstico sin credenciales."""
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        ejecutar_upgrade_original()
    except Exception:
        print(
            "Upgrade original detenido. Verifique configuración, revisión y estado SQL.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
