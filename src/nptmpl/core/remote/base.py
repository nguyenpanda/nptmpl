from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
from nptmpl.core.metadata import TemplateMetadata

class RemoteTransport(ABC):
    """Abstract base class defining the interface for remote template operations."""

    @abstractmethod
    def fetch_metadata(self, target: str, is_clone: bool = False) -> TemplateMetadata:
        """Fetches metadata for a remote template."""
        pass

    @abstractmethod
    def download_tarball(self, target: str, dest_path: Path) -> None:
        """Downloads the compressed template tarball to a local destination."""
        pass

    @abstractmethod
    def push_template(self, target: str, metadata: TemplateMetadata, tarball_path: Path, overwrite: bool = False) -> None:
        """Uploads a local template and its metadata to the remote registry."""
        pass

    @abstractmethod
    def list_templates(self, query: Optional[str] = None) -> List[Tuple[str, str, Dict[str, Any]]]:
        """Lists or searches templates available on the remote registry."""
        pass

    @abstractmethod
    def get_details(self, target: str) -> Tuple[str, str, Dict[str, Any]]:
        """Fetches detailed information for a specific remote template version."""
        pass
