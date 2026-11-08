"""Agrupa los submódulos del Bloque Catálogo."""
import importlib.util
import sys
from pathlib import Path

from fastapi import APIRouter

router = APIRouter()

_BASE = Path(__file__).parent  # → src/modules/catalogo/


def _cargar_ctrl(relativo: str, cache_key: str) -> object:
    if cache_key not in sys.modules:
        spec = importlib.util.spec_from_file_location(cache_key, _BASE / relativo)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[cache_key] = mod
        spec.loader.exec_module(mod)
    return sys.modules[cache_key]


# Siguiente paso: registrar router de ubicaciones
_ctrl = _cargar_ctrl(
    "gestion-ubicaciones/controllers/ubicaciones_controller.py",
    "_pk_ubicaciones_controller",
)
router.include_router(_ctrl.router, tags=["Ubicaciones"])

