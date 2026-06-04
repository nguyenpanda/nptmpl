from abc import ABC, abstractmethod
from pathlib import Path

class RegistrySynchronizer(ABC):
    """Interface for synchronizing the template registry with external stores (e.g. SQLite)."""
    
    @abstractmethod
    def sync(self, root_path: Path) -> None:
        """Triggers a synchronization of the registry state."""
        pass
