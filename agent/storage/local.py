import logging
from pathlib import Path

from .base import StorageBackend

logger = logging.getLogger(__name__)


class LocalStorage(StorageBackend):
    """Local filesystem storage backend."""

    async def read(self, path: str) -> str:
        """Read file from local filesystem."""
        file_path = Path(path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        if not file_path.is_file():
            raise IOError(f"Not a file: {path}")

        content = file_path.read_text(encoding="utf-8")
        logger.debug(f"LocalStorage.read: {path} ({len(content)} chars)")
        return content

    async def write(self, path: str, content: str) -> None:
        """Write file to local filesystem."""
        file_path = Path(path)

        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        logger.debug(f"LocalStorage.write: {path} ({len(content)} chars)")

    async def exists(self, path: str) -> bool:
        """Check if file exists on local filesystem."""
        return Path(path).exists()
