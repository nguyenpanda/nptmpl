import json
import logging
from pathlib import Path
from typing import List, Tuple, Dict, Any
from nptmpl.core.metadata import Version
from nptmpl.core.models import Template

logger = logging.getLogger("nptmpl.cache")

class RegistryCache:
    """
    Manages a JSON cache of all template metadata for fast indexing and searching.
    
    Avoids expensive filesystem traversal by persisting a flat view of the registry.
    """

    CACHE_FILE = "cache.json"

    def __init__(self, store_path: Path):
        """
        Initializes the cache.

        Args:
            store_path: Root path of the template registry.
        """
        self.store_path = store_path
        self.cache_path = store_path / self.CACHE_FILE
        self._data: Dict[str, Any] = {}

    def load(self) -> bool:
        """
        Loads the cache from disk.
        
        Returns:
            True if the cache was successfully loaded, False otherwise.
        """
        if not self.cache_path.exists():
            return False
        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
            return True
        except Exception as e:
            logger.debug(f"Failed to load cache: {e}")
            return False

    def save(self) -> None:
        """Saves the current in-memory cache to disk."""
        try:
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")

    def rebuild(self) -> None:
        """
        Exhaustively scans the storage directory and rebuilds the metadata cache.
        
        This is an expensive operation and should be called after modifying the registry.
        """
        logger.debug("Rebuilding template cache...")
        new_data = {}
        if not self.store_path.exists():
            self._data = {}
            return

        for group_dir in self.store_path.iterdir():
            if not group_dir.is_dir() or group_dir.name.startswith("."):
                continue
            for name_dir in group_dir.iterdir():
                if not name_dir.is_dir():
                    continue

                template = Template(group_dir.name, name_dir.name, self.store_path)
                versions = template.get_versions()
                if not versions:
                    continue

                template_key = str(template)
                new_data[template_key] = {
                    "versions": {}
                }

                for version in versions:
                    try:
                        metadata = template.get_metadata(version)
                        new_data[template_key]["versions"][str(version)] = metadata.to_dict()
                    except Exception as e:
                        logger.warning(f"Skipping corrupted metadata for {template} @ {version}: {e}")
                        continue

        self._data = new_data
        self.save()

    def get_all(self) -> List[Tuple[str, str, Dict[str, Any]]]:
        """
        Returns a list of all templates with their latest version metadata.
        
        Returns:
            List of (target_string, version_string, metadata_dict), sorted by target.
        """
        results = []
        for target, info in sorted(self._data.items()):
            versions = sorted([Version(v) for v in info["versions"].keys()])
            if versions:
                latest = versions[-1]
                results.append((target, str(latest), info["versions"][str(latest)]))
        return results

    def get_versions(self, target: str) -> List[Tuple[str, Dict[str, Any]]]:
        """
        Returns all available versions for a specific template.

        Args:
            target: Template identifier (group/name).

        Returns:
            List of (version_string, metadata_dict), sorted by version descending.
        """
        if target not in self._data:
            return []

        versions = sorted([Version(v) for v in self._data[target]["versions"].keys()], reverse=True)
        return [(str(v), self._data[target]["versions"][str(v)]) for v in versions]

    def search(self, query: str) -> List[Tuple[str, str, Dict[str, Any]]]:
        """
        Performs a fast keyword search across cached template metadata.

        Args:
            query: The search term.

        Returns:
            List of matching templates with their latest version metadata, sorted by target.
        """
        query = query.lower()
        results = []
        for target, info in sorted(self._data.items()):
            versions = sorted([Version(v) for v in info["versions"].keys()])
            if not versions:
                continue

            latest_str = str(versions[-1])
            meta = info["versions"][latest_str]

            search_fields = [
                target.lower(),
                meta.get("description", "").lower(),
                meta.get("author", "").lower(),
                *[lang.lower() for lang in meta.get("languages", [])],
                *[t.lower() for t in meta.get("tags", [])]
            ]

            if any(query in f for f in search_fields):
                results.append((target, latest_str, meta))
        return results
