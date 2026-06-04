from pathlib import Path
from typing import List, Optional
from nptmpl.core.metadata import Version, MetadataManager, TemplateMetadata

class Template:
    """Entity model representing a template uniquely identified by group and name."""

    def __init__(self, group: str, name: str, store_path: Path):
        """
        Initializes a template entity.

        Args:
            group: Template group namespace.
            name: Template name.
            store_path: Root path of the template registry.
        """
        self.group = group
        self.name = name
        self.base_path = store_path / group / name

    def exists(self) -> bool:
        """Checks if the template exists in the registry."""
        return self.base_path.exists() and self.base_path.is_dir()

    def get_versions(self) -> List[Version]:
        """Returns a sorted list of all available versions for this template."""
        if not self.exists():
            return []

        versions = []
        for d in self.base_path.iterdir():
            if d.is_dir() and Version.is_valid(d.name):
                versions.append(Version(d.name))
        return sorted(versions)

    def get_latest_version(self) -> Optional[Version]:
        """Returns the highest available version for this template."""
        versions = self.get_versions()
        return versions[-1] if versions else None

    def get_version_path(self, version: Version) -> Path:
        """Returns the filesystem path for a specific version."""
        return self.base_path / str(version)

    def get_metadata(self, version: Version) -> TemplateMetadata:
        """Loads and returns the metadata for a specific version."""
        return MetadataManager.load(self.get_version_path(version))

    def __str__(self) -> str:
        return f"{self.group}/{self.name}"
