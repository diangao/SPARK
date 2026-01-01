from abc import ABC, abstractmethod


class StorageBackend(ABC):
    """Abstract base class for Think OS storage backends."""

    @abstractmethod
    async def read(self, path: str) -> str:
        """Read file content.

        Args:
            path: Full resolved path to the file.

        Returns:
            File content as string.

        Raises:
            FileNotFoundError: If file doesn't exist.
            IOError: If read fails.
        """
        pass

    @abstractmethod
    async def write(self, path: str, content: str) -> None:
        """Write content to file.

        Args:
            path: Full resolved path to the file.
            content: Content to write.

        Raises:
            IOError: If write fails.
        """
        pass

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """Check if file exists.

        Args:
            path: Full resolved path to the file.

        Returns:
            True if file exists, False otherwise.
        """
        pass
