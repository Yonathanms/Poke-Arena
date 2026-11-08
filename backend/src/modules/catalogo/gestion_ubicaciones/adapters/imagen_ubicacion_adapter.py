"""Adaptador Pillow: valida proporción 4:3 y genera WebP grande + miniatura 320×240."""
import io
import uuid
from pathlib import Path

from fastapi import HTTPException, status
from PIL import Image

from src.shared.config import get_settings

settings = get_settings()

_RATIO_TARGET = 4 / 3
_RATIO_TOLERANCIA = 0.02
_MIN_ANCHO = 800
_MIN_ALTO = 600
_MAX_BYTES = settings.MAX_IMAGE_SIZE_MB * 1024 * 1024
_TIPOS_PERMITIDOS = {"image/png", "image/jpeg", "image/webp"}
_THUMB_W, _THUMB_H = 320, 240


class ImagenUbicacionAdapter:
    async def procesar(self, archivo_bytes: bytes, content_type: str) -> tuple[str, str]:
        # Siguiente paso: validar formato, tamaño y proporciones
        if content_type not in _TIPOS_PERMITIDOS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Formato de imagen inválido. Se aceptan PNG, JPG o WebP.",
            )
        if len(archivo_bytes) > _MAX_BYTES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"La imagen supera el límite de {settings.MAX_IMAGE_SIZE_MB} MB.",
            )

        try:
            imagen = Image.open(io.BytesIO(archivo_bytes))
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No se pudo leer el archivo de imagen.",
            )

        ancho, alto = imagen.size
        if ancho < _MIN_ANCHO or alto < _MIN_ALTO:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"La imagen debe ser al menos {_MIN_ANCHO}×{_MIN_ALTO} píxeles.",
            )
        if abs(ancho / alto - _RATIO_TARGET) > _RATIO_TOLERANCIA:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="La imagen debe tener proporción 4:3 exacta.",
            )

        # Siguiente paso: guardar versión grande y miniatura en WebP
        base_nombre = uuid.uuid4().hex
        carpeta = Path(settings.UPLOAD_DIR) / "locations"
        carpeta.mkdir(parents=True, exist_ok=True)

        imagen_rgb = imagen.convert("RGB")
        nombre_grande = f"{base_nombre}_grande.webp"
        imagen_rgb.save(carpeta / nombre_grande, format="WEBP", quality=85)

        miniatura = imagen_rgb.resize((_THUMB_W, _THUMB_H), Image.LANCZOS)
        nombre_tablero = f"{base_nombre}_tablero.webp"
        miniatura.save(carpeta / nombre_tablero, format="WEBP", quality=80)

        return f"/media/locations/{nombre_grande}", f"/media/locations/{nombre_tablero}"
