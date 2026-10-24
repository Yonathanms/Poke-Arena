"""Local persistent file adapter used by Content and Location images."""

import asyncio
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

from src.shared.application.ports import IFileStoragePort, StoredObjectDTO
from src.shared.infrastructure.config import get_settings

settings = get_settings()


class LocalFileStorage(IFileStoragePort):
    """Local storage with asynchronous file I/O and guarded storage keys."""

    def __init__(self, base_dir: str | None = None) -> None:
        self.base_dir = Path(base_dir or settings.UPLOAD_DIR)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def save_file(self, content: bytes, extension: str, subfolder: str = "") -> str:
        return await asyncio.to_thread(self._save_file, content, extension, subfolder)

    def _save_file(self, content: bytes, extension: str, subfolder: str) -> str:
        target_dir = self.base_dir / subfolder if subfolder else self.base_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / f"{uuid.uuid4().hex}{extension}"
        file_path.write_bytes(content)
        relative_path = os.path.relpath(file_path, self.base_dir)
        return f"/uploads/{relative_path.replace(os.sep, '/')}"

    async def save_file_at(self, content: bytes, storage_key: str) -> str:
        return await asyncio.to_thread(self._save_file_at, content, storage_key)

    def _save_file_at(self, content: bytes, storage_key: str) -> str:
        target = self._resolve_file(storage_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as output:
            output.write(content)
        relative_path = os.path.relpath(target, self.base_dir)
        return f"/uploads/{relative_path.replace(os.sep, '/')}"

    async def read_file(self, storage_key: str) -> bytes:
        return await asyncio.to_thread(self._resolve_file(storage_key).read_bytes)

    async def delete_file(self, file_url: str) -> None:
        await asyncio.to_thread(self._delete_file, file_url)

    def _delete_file(self, file_url: str) -> None:
        self._resolve_file(file_url).unlink(missing_ok=True)

    async def list_files(
        self, subfolder: str, modified_before: datetime
    ) -> list[StoredObjectDTO]:
        return await asyncio.to_thread(self._list_files, subfolder, modified_before)

    def _list_files(self, subfolder: str, modified_before: datetime) -> list[StoredObjectDTO]:
        root = self._resolve_file(f"/uploads/{subfolder}")
        if not root.exists():
            return []
        cutoff = modified_before.timestamp()
        found: list[StoredObjectDTO] = []
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            stat = path.stat()
            if stat.st_mtime >= cutoff:
                continue
            relative_path = os.path.relpath(path, self.base_dir)
            found.append(
                StoredObjectDTO(
                    storage_key=f"/uploads/{relative_path.replace(os.sep, '/')}",
                    modified_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
                )
            )
        return found

    def _resolve_file(self, storage_key: str) -> Path:
        clean_path = storage_key.lstrip("/")
        if clean_path.startswith("uploads/"):
            clean_path = clean_path[len("uploads/") :]
        base = self.base_dir.resolve()
        target = (self.base_dir / clean_path).resolve()
        if not target.is_relative_to(base):
            raise ValueError("La clave de almacenamiento no es válida.")
        return target


def get_file_storage() -> LocalFileStorage:
    return LocalFileStorage()
