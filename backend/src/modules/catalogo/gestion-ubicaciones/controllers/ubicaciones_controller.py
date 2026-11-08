"""Endpoint POST /api/v1/content/locations con multipart, Bearer JWT e Idempotency-Key."""
import importlib.util
import json
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.postgresql.connection import get_db

router = APIRouter()

# Seguridad y admin
_bearer = HTTPBearer(auto_error=False)

async def _require_admin(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere autenticación. Envíe un Bearer token válido.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Siguiente paso: validar JWT y verificar rol admin con Google OAuth
    # Placeholder: cualquier token no vacío se acepta mientras el módulo identidad esté pendiente
    if not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol Administrador.",
        )
    return creds.credentials


# Carga de módulos
_BASE = Path(__file__).parent.parent  # → gestion-ubicaciones/


def _cargar(relativo: str, cache_key: str):
    if cache_key not in sys.modules:
        spec = importlib.util.spec_from_file_location(cache_key, _BASE / relativo)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[cache_key] = mod
        spec.loader.exec_module(mod)
    return sys.modules[cache_key]


def _get_service(db: AsyncSession):
    _img_mod = _cargar("adapters/imagen_ubicacion_adapter.py", "_pk_img_adapter")
    _sql_mod = _cargar("adapters/sql_ubicacion_repository.py", "_pk_sql_repo")
    _svc_mod = _cargar("services/ubicaciones_service.py", "_pk_ubicacion_svc")

    imagen_adapter = _img_mod.ImagenUbicacionAdapter()
    sql_repo = _sql_mod.SqlUbicacionRepository(db)
    return _svc_mod.UbicacionesService(imagen_adapter, sql_repo)


# Respuesta DTO
_dto_mod = _cargar("controllers/ubicaciones_dtos.py", "_pk_ubicacion_dtos")
UbicacionResponseDTO = _dto_mod.UbicacionResponseDTO


# Ruta
@router.post(
    "/content/locations",
    status_code=status.HTTP_201_CREATED,
    response_model=UbicacionResponseDTO,
    summary="Crear una nueva ubicación de arena",
)
# 
async def crear_ubicacion(
    nombre: str = Form(..., max_length=100),
    descripcion: str = Form(..., max_length=500),
    card_limit: int = Form(..., ge=0, le=5),
    energia_tipo: str = Form(...),
    energia_valor: int = Form(..., ge=0),
    efecto_tipo: str = Form(...),
    efecto_params: str = Form(...),
    imagen: UploadFile = File(...),
    idempotency_key: str = Header(..., alias="idempotency-key"),
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(_require_admin),
) -> UbicacionResponseDTO:
    # Siguiente paso: parsear efecto_params JSON
    try:
        params_dict = json.loads(efecto_params)
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="efecto_params debe ser un JSON válido.",
        )

    datos = {
        "nombre": nombre,
        "descripcion": descripcion,
        "card_limit": card_limit,
        "energia_tipo": energia_tipo,
        "energia_valor": energia_valor,
        "efecto_tipo": efecto_tipo,
        "efecto_params": params_dict,
    }

    imagen_bytes = await imagen.read()
    service = _get_service(db)

    # Siguiente paso: orquestar creación de la ubicación
    resultado = await service.crear(datos, imagen_bytes, imagen.content_type or "", idempotency_key)
    return UbicacionResponseDTO(**resultado)
