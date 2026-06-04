from fastapi import Request
from pathlib import Path

from nptmpl.core.config import ConfigManager
from nptmpl.server.db import DatabaseManager


def get_db(request: Request) -> DatabaseManager:
    """Dependency to get the database manager instance."""
    return request.app.state.db

def get_storage(request: Request) -> Path:
    """Dependency to get the storage path."""
    return request.app.state.storage_path

def get_config(request: Request) -> ConfigManager:
    """Dependency to get the configuration manager."""
    return request.app.state.config
