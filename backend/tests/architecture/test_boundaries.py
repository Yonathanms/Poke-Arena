"""Pruebas de Arquitectura y Fronteras Modulares (RNF-ARQ-01, RNF-ARQ-03, RNF-ARQ-04).

Valida que las capas respeten la Ley de Dependencia de la Arquitectura Hexagonal:
presentation -> application -> domain <- infrastructure
"""

import ast
from pathlib import Path


def test_domain_has_no_framework_dependencies() -> None:
    """Regla 2: El dominio no debe depender de FastAPI, SQLAlchemy, Motor ni infraestructura."""
    domain_path = Path("src/modules/content/domain")
    prohibited_imports = {"fastapi", "sqlalchemy", "motor", "infrastructure", "presentation"}

    for py_file in domain_path.glob("*.py"):
        with open(py_file, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(py_file))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_pkg = alias.name.split(".")[0]
                    assert (
                        root_pkg not in prohibited_imports
                    ), f"{py_file} importa el paquete prohibido en Dominio: {alias.name}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                root_pkg = node.module.split(".")[0]
                assert (
                    root_pkg not in prohibited_imports
                ), f"{py_file} importa el módulo prohibido en Dominio: {node.module}"


def test_contracts_exists_in_content_module() -> None:
    """Regla 1 (RNF-ARQ-03): El módulo content debe exponer contracts.py como frontera pública."""
    contracts_file = Path("src/modules/content/contracts.py")
    assert contracts_file.exists(), "Falta contracts.py en src/modules/content/"
