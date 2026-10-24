import os
import uuid
from pathlib import Path

from src.shared.infrastructure.config import get_settings

settings = get_settings()


class LocalFileStorage:
    """Adaptador de almacenamiento local de archivos e imágenes."""

    def __init__(self, base_dir: str | None = None) -> None:
        self.base_dir = Path(base_dir or settings.UPLOAD_DIR)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def save_file(self, content: bytes, extension: str, subfolder: str = "") -> str:
        """
        Guarda un archivo binario en el sistema de archivos local y retorna su ruta relativa.
        """
        target_dir = self.base_dir / subfolder if subfolder else self.base_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{uuid.uuid4().hex}{extension}"
        file_path = target_dir / filename

        with open(file_path, "wb") as f:
            f.write(content)

        relative_path = os.path.relpath(file_path, self.base_dir)
        return f"/uploads/{relative_path.replace(os.sep, '/')}"

    async def delete_file(self, file_url: str) -> None:
        """Elimina un archivo del almacenamiento local a partir de su URL pública relativa."""
        clean_path = file_url.lstrip("/")
        if clean_path.startswith("uploads/"):
            clean_path = clean_path[len("uploads/") :]
        target_file = self.base_dir / clean_path
        if target_file.exists():
            target_file.unlink(missing_ok=True)


def get_file_storage() -> LocalFileStorage:
    return LocalFileStorage()
