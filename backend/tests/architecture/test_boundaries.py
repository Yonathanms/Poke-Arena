"""Pruebas de Arquitectura y Fronteras Modulares (RNF-ARQ-01, RNF-ARQ-03, RNF-ARQ-04).

Valida que se respete la Ley de Dependencia de la Arquitectura Hexagonal:
presentation -> application -> domain <- infrastructure

El análisis es estático (AST) y recorre TODOS los módulos de `src/` de forma dinámica,
por lo que los módulos futuros (identity, players, game, tournaments) quedan cubiertos
automáticamente apenas tengan código.

Reglas verificadas:
  R1. Un módulo solo puede importar de otro módulo su `contracts.py` (RNF-ARQ-03).
  R2. domain / application / presentation / infrastructure respetan la dirección de
      dependencias y no importan frameworks que no les corresponden.
  R3. `shared` nunca importa de `modules`.
  R4. `game/domain/engine` es puro: sin I/O, reloj, azar sin semilla ni frameworks.
"""

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).resolve().parent.parent.parent / "src"

LAYERS = {"domain", "application", "presentation", "infrastructure"}

# Capas internas (del proyecto) que NO puede importar cada capa.
FORBIDDEN_LAYERS: dict[str, set[str]] = {
    "domain": {"application", "presentation", "infrastructure"},
    "application": {"presentation", "infrastructure"},
    "infrastructure": {"presentation"},
    "presentation": {"infrastructure"},
}

# Librerías externas que NO puede importar cada capa.
FORBIDDEN_EXTERNAL: dict[str, set[str]] = {
    "domain": {
        "fastapi", "starlette", "sqlalchemy", "motor", "pymongo", "asyncpg",
        "alembic", "PIL", "pydantic", "httpx",
    },
    "application": {
        "fastapi", "starlette", "sqlalchemy", "motor", "pymongo", "asyncpg",
        "alembic", "PIL",
    },
    "presentation": {"sqlalchemy", "motor", "pymongo", "asyncpg", "alembic", "PIL"},
}

# Regla 3 (RNF-ARQ-01/02): pureza del motor del juego.
ENGINE_FORBIDDEN_EXTERNAL = {
    "os", "sys", "time", "random", "datetime", "socket", "subprocess", "pathlib",
    "sqlalchemy", "fastapi", "starlette", "httpx", "motor", "pymongo", "requests",
    "asyncpg", "PIL", "logging",
}


@dataclass(frozen=True)
class FileInfo:
    """Ubicación arquitectónica de un archivo fuente."""

    module: str | None  # None si pertenece a shared
    layer: str | None  # None si está en la raíz del módulo (contracts.py, composition.py)
    is_engine: bool = False


def classify(path: Path, src_root: Path = SRC_ROOT) -> FileInfo | None:
    """Devuelve la ubicación del archivo, o None si no pertenece a un módulo/shared."""
    parts = path.relative_to(src_root).parts
    if len(parts) >= 3 and parts[0] == "modules":
        layer = parts[2] if parts[2] in LAYERS else None
        is_engine = (
            parts[1] == "game" and len(parts) >= 5 and parts[2] == "domain" and parts[3] == "engine"
        )
        return FileInfo(module=parts[1], layer=layer, is_engine=is_engine)
    if len(parts) >= 3 and parts[0] == "shared":
        layer = parts[1] if parts[1] in LAYERS else None
        return FileInfo(module=None, layer=layer)
    return None


def collect_imports(path: Path, src_root: Path = SRC_ROOT) -> list[tuple[int, str]]:
    """Retorna (línea, nombre-completo) de cada import; resuelve imports relativos."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    package_parts = ["src", *path.relative_to(src_root).parts[:-1]]
    found: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package_parts[: len(package_parts) - (node.level - 1)]
                module = ".".join([*base, *(node.module.split(".") if node.module else [])])
            else:
                module = node.module or ""
            found.append((node.lineno, module))
            # `from pkg import sub` también puede importar un submódulo (pkg.sub)
            found.extend((node.lineno, f"{module}.{alias.name}") for alias in node.names)
    return found


def check_import(info: FileInfo, name: str) -> str | None:
    """Devuelve el motivo de violación si `name` no es un import permitido para `info`."""
    parts = name.split(".")
    root = parts[0]

    # Pureza del motor
    if info.is_engine and root in ENGINE_FORBIDDEN_EXTERNAL:
        return f"el motor puro no puede importar '{name}' (RNF-ARQ-01)"

    # Librerías externas prohibidas por capa
    if info.layer and root in FORBIDDEN_EXTERNAL.get(info.layer, set()):
        return f"la capa {info.layer} no puede importar la librería '{name}'"

    if root != "src":
        return None

    # R3: shared no importa de modules
    if info.module is None and len(parts) >= 2 and parts[1] == "modules":
        return f"shared no puede depender de módulos de negocio: '{name}'"

    # R1: fronteras entre módulos -> solo `contracts`
    if len(parts) >= 4 and parts[1] == "modules" and parts[2] != info.module:
        if parts[3] != "contracts":
            return f"importa internos de otro módulo ('{name}'); usar solo '{parts[2]}.contracts'"

    # R2: dirección de dependencias entre capas
    imported_layer: str | None = None
    if len(parts) >= 4 and parts[1] == "modules" and parts[3] in LAYERS:
        imported_layer = parts[3]
    elif len(parts) >= 3 and parts[1] == "shared" and parts[2] in LAYERS:
        imported_layer = parts[2]
    if info.layer and imported_layer in FORBIDDEN_LAYERS.get(info.layer, set()):
        return f"la capa {info.layer} no puede importar la capa {imported_layer}: '{name}'"

    return None


def find_violations(src_root: Path = SRC_ROOT) -> list[str]:
    violations: list[str] = []
    for py_file in sorted(src_root.rglob("*.py")):
        info = classify(py_file, src_root)
        if info is None:
            continue
        for lineno, name in collect_imports(py_file, src_root):
            reason = check_import(info, name)
            if reason:
                rel = py_file.relative_to(src_root.parent)
                violations.append(f"{rel}:{lineno} -> {reason}")
    return sorted(set(violations))


# ------------------------------------------------------------------------------
# Pruebas sobre el código real del proyecto
# ------------------------------------------------------------------------------
def test_source_tree_is_discovered() -> None:
    """Evita falsos verdes: debe encontrar archivos en cada capa de `content`."""
    seen: set[str | None] = set()
    for py_file in SRC_ROOT.rglob("*.py"):
        info = classify(py_file)
        if info and info.module == "content":
            seen.add(info.layer)
    assert {"domain", "application", "infrastructure", "presentation"} <= seen


def test_architecture_has_no_dependency_violations() -> None:
    """R1 + R2 + R3: fronteras entre módulos y ley de dependencia en capas."""
    violations = find_violations()
    assert not violations, "Violaciones de arquitectura:\n" + "\n".join(violations)


def test_contracts_exists_in_content_module() -> None:
    """RNF-ARQ-03: el módulo content debe exponer contracts.py como frontera pública."""
    contracts_file = SRC_ROOT / "modules" / "content" / "contracts.py"
    assert contracts_file.exists(), f"Falta contracts.py en {contracts_file}"


def test_game_engine_is_pure() -> None:
    """R4 (RNF-ARQ-01): el motor del juego no tiene I/O, reloj ni frameworks."""
    engine_dir = SRC_ROOT / "modules" / "game" / "domain" / "engine"
    if not engine_dir.exists():
        pytest.skip("El motor del juego aún no existe (Sprint posterior).")
    assert any(engine_dir.rglob("*.py")), "engine/ existe pero no contiene código"
    assert not find_violations(), "Violaciones de arquitectura en el motor"


# ------------------------------------------------------------------------------
# Auto-pruebas del verificador: garantizan que el test SÍ detecta violaciones
# ------------------------------------------------------------------------------
def _write(root: Path, rel: str, content: str) -> None:
    file = root / "src" / rel
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(content, encoding="utf-8")


@pytest.mark.parametrize(
    ("rel_path", "code", "expected"),
    [
        (
            "modules/content/domain/a.py",
            "from src.modules.content.infrastructure.models import CardModel\n",
            "no puede importar la capa infrastructure",
        ),
        (
            "modules/content/domain/a.py",
            "import sqlalchemy\n",
            "no puede importar la librería",
        ),
        (
            "modules/content/application/a.py",
            "from src.shared.infrastructure.storage import LocalFileStorage\n",
            "no puede importar la capa infrastructure",
        ),
        (
            "modules/content/application/a.py",
            "from fastapi import FastAPI\n",
            "no puede importar la librería",
        ),
        (
            "modules/content/presentation/a.py",
            "from src.modules.content.infrastructure.unit_of_work import SqlUnitOfWork\n",
            "no puede importar la capa infrastructure",
        ),
        (
            "modules/content/infrastructure/a.py",
            "from src.modules.content.presentation.schemas import X\n",
            "no puede importar la capa presentation",
        ),
        (
            "modules/game/application/a.py",
            "from src.modules.content.infrastructure.models import CardModel\n",
            "importa internos de otro módulo",
        ),
        (
            "modules/game/application/a.py",
            "from src.modules.content import infrastructure\n",
            "importa internos de otro módulo",
        ),
        (
            "shared/application/a.py",
            "from src.modules.content.contracts import CardPublicDTO\n",
            "shared no puede depender",
        ),
        (
            "modules/game/domain/engine/a.py",
            "import random\n",
            "motor puro",
        ),
        (
            "modules/game/domain/engine/a.py",
            "from datetime import datetime\n",
            "motor puro",
        ),
    ],
)
def test_checker_detects_violations(
    tmp_path: Path, rel_path: str, code: str, expected: str
) -> None:
    _write(tmp_path, rel_path, code)
    violations = find_violations(tmp_path / "src")
    assert violations, f"El verificador no detectó la violación en: {code!r}"
    assert expected in violations[0]


@pytest.mark.parametrize(
    ("rel_path", "code"),
    [
        ("modules/game/application/a.py", "from src.modules.content.contracts import X\n"),
        ("modules/content/application/a.py", "from src.modules.content.domain.entities import C\n"),
        ("modules/content/application/a.py", "from src.shared.application.unit_of_work import U\n"),
        (
            "modules/content/infrastructure/a.py",
            "from src.modules.content.application.ports import P\n",
        ),
        ("modules/content/presentation/a.py", "from src.modules.content.composition import f\n"),
        (
            "modules/content/composition.py",
            "from src.modules.content.infrastructure.models import M\n",
        ),
        ("modules/game/domain/engine/a.py", "from dataclasses import dataclass\n"),
    ],
)
def test_checker_allows_valid_imports(tmp_path: Path, rel_path: str, code: str) -> None:
    _write(tmp_path, rel_path, code)
    assert find_violations(tmp_path / "src") == []
