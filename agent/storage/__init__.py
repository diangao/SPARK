from config.settings import STORAGE_BACKEND

from .base import StorageBackend

_storage_instance: StorageBackend | None = None


def get_storage() -> StorageBackend:
    """Get the configured storage backend (singleton)."""
    global _storage_instance

    if _storage_instance is not None:
        return _storage_instance

    if STORAGE_BACKEND == "github":
        from .github import GitHubStorage
        _storage_instance = GitHubStorage()
    else:
        from .local import LocalStorage
        _storage_instance = LocalStorage()

    return _storage_instance


__all__ = ["StorageBackend", "get_storage"]
