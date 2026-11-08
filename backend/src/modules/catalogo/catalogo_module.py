import importlib
from fastapi import APIRouter

catalogo_router = APIRouter()

# Enlazar controlador de cartas
_cartas_ctrl = importlib.import_module(
    "src.modules.catalogo.gestion-cartas.controllers.cartas_controller"
)
catalogo_router.include_router(_cartas_ctrl.router)

__all__ = ["catalogo_router"]
