import logging
from pathlib import Path

from nptmpl.core.sync import RegistrySynchronizer
from nptmpl.server.db import DatabaseManager
from nptmpl.server.reindexer import ServerReindexer


logger = logging.getLogger("nptmpl.server.sync")

class SqliteRegistrySynchronizer(RegistrySynchronizer):
    """Synchronizes the template store with the server SQLite database."""
    
    def sync(self, root_path: Path) -> None:
        db_path = root_path / "registry.db"
        if not db_path.exists():
            return

        try:
            db = DatabaseManager(db_path)
            ServerReindexer.reindex(root_path, db)
        except Exception as e:
            logger.warning(f"Failed to synchronize SQLite database: {e}")
