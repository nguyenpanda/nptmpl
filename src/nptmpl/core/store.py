import os
import re
import tarfile
import logging
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
from datetime import datetime

from nptmpl.core.metadata import Version, MetadataManager, TemplateMetadata
from nptmpl.core.models import Template
from nptmpl.core.engine import FileSystemEngine
from nptmpl.core.cache import RegistryCache
from nptmpl.core.remote.base import RemoteTransport
from nptmpl.core.sync import RegistrySynchronizer
from nptmpl.core.errors import (
    TemplateNotFoundError, 
    TemplateAlreadyExistsError, 
    VersionConflictError, 
    ValidationError, 
    DestinationNotEmptyError,
    RegistryError
)

logger = logging.getLogger("nptmpl.store")

class TemplateStore:
    """
    Domain layer for managing the local template registry.
    
    Responsible for adding, updating, cloning, and listing templates while 
    maintaining an efficient metadata cache and optional external sync.
    """

    TARGET_REGEX = re.compile(r"^([^/@]+)/([^/@]+)(?:@([^/@]+))?$")

    def __init__(self, root_path: Path, 
                 global_ignore: Optional[List[str]] = None,
                 synchronizer: Optional[RegistrySynchronizer] = None):
        """
        Initializes the template store.

        Args:
            root_path: Filesystem path to the registry root.
            global_ignore: List of patterns to ignore across all templates.
            synchronizer: Optional object to handle external synchronization.
        """
        self.root_path = root_path
        self.global_ignore = global_ignore or []
        self.synchronizer = synchronizer

        FileSystemEngine.ensure_directory(self.root_path)

        if not os.access(self.root_path, os.W_OK):
            raise PermissionError(f"Permission denied: Storage directory {self.root_path} is not writable.")

        self.cache = RegistryCache(self.root_path)
        if not self.cache.load():
            logger.info("Cache not found or invalid. Rebuilding...")
            self.cache.rebuild()

    def _parse_target(self, target: str) -> Tuple[str, str, Optional[str]]:
        """Parses a target string into (group, name, version)."""
        match = self.TARGET_REGEX.match(target)
        if not match:
            raise ValidationError(f"Invalid target format: '{target}'. Expected <group>/<name>[@<version>].")
        return match.groups()

    def _trigger_sync(self) -> None:
        """Triggers the synchronizer if one is configured."""
        if self.synchronizer:
            self.synchronizer.sync(self.root_path)

    def add_template(self, source_dir: str, target_str: str, overwrite: bool = False) -> None:
        """Adds a new template or version to the store."""
        group, name, _ = self._parse_target(target_str)
        source_path = Path(source_dir)

        if not source_path.exists():
            raise FileNotFoundError(f"Source directory not found: {source_dir}")

        metadata = MetadataManager.load(source_path)

        if not metadata.added_date:
            added_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            metadata = metadata.copy_with(added_date=added_date)

        version = Version(metadata.version)
        template = Template(group, name, self.root_path)
        version_path = template.get_version_path(version)

        if version_path.exists():
            if not overwrite:
                raise TemplateAlreadyExistsError(f"Template {template} version {version} already exists.")
            FileSystemEngine.remove_directory(version_path)

        FileSystemEngine.ensure_directory(version_path)
        MetadataManager.save(version_path, metadata)

        combined_ignore = list(set(self.global_ignore + metadata.ignore))
        archive_path = version_path / "data.tar.gz"
        FileSystemEngine.compress_directory(source_path, archive_path, combined_ignore)

        self.cache.rebuild()
        self._trigger_sync()
        logger.info(f"Successfully added template '{template}' version {version}")

    def update_template(self, target_str: str, source_dir: str) -> None:
        """Updates a template by adding a new version (must be > latest)."""
        group, name, _ = self._parse_target(target_str)
        template = Template(group, name, self.root_path)
        
        if not template.exists():
            raise TemplateNotFoundError(f"Template {template} does not exist.")

        metadata = MetadataManager.load(Path(source_dir))
        new_version = Version(metadata.version)

        latest_version = template.get_latest_version()
        if latest_version and new_version <= latest_version:
            raise VersionConflictError(f"New version {new_version} must be > {latest_version}.")

        self.add_template(source_dir, f"{group}/{name}")

    def push_template(self, target_str: str, remote: RemoteTransport, overwrite: bool = False) -> None:
        """Uploads a local template to a remote registry."""
        group, name, version_str = self._parse_target(target_str)
        template = Template(group, name, self.root_path)

        if not template.exists():
            raise TemplateNotFoundError(f"Template {template} not found.")

        if version_str == "latest" or version_str is None:
            version = template.get_latest_version()
            if not version:
                raise TemplateNotFoundError(f"No versions found for template {template}")
        else:
            version = Version(version_str)

        version_path = template.get_version_path(version)
        if not version_path.exists():
            raise TemplateNotFoundError(f"Version {version} of template {template} not found.")

        metadata = template.get_metadata(version)
        archive_path = version_path / "data.tar.gz"

        if not archive_path.exists():
            raise RegistryError(f"Template data archive missing for {template} @{version}")

        logger.info(f"Pushing {template} @{version} to remote...")
        remote.push_template(f"{group}/{name}@{version}", metadata, archive_path, overwrite=overwrite)

    def clone_template(self, target_str: str, dest_dir: str, 
                       variables: Optional[Dict[str, Any]] = None, 
                       force: bool = False, 
                       remote: Optional[RemoteTransport] = None) -> None:
        """Clones a template, optionally fetching from remote if missing."""
        if remote:
            try:
                remote_meta = remote.fetch_metadata(target_str)
                group, name, _ = self._parse_target(target_str)
                version = Version(remote_meta.version)
                template = Template(group, name, self.root_path)
                
                if not template.get_version_path(version).exists():
                    logger.info(f"Fetching {group}/{name} @{version} from remote...")
                    self._fetch_from_remote(f"{group}/{name}@{version}", remote)
                else:
                    remote.fetch_metadata(target_str, is_clone=True)
                
                target_str = f"{group}/{name}@{version}"
            except Exception as e:
                logger.warning(f"Remote fetch failed: {e}. Falling back to local.")

        group, name, version_str = self._parse_target(target_str)
        template = Template(group, name, self.root_path)

        if not template.exists():
            raise TemplateNotFoundError(f"Template {template} not found in store.")

        if version_str == "latest" or version_str is None:
            version = template.get_latest_version()
            if not version: raise TemplateNotFoundError(f"No versions for {template}")
        else:
            version = Version(version_str)
            if version not in template.get_versions():
                raise TemplateNotFoundError(f"Version {version} of {template} not found.")

        source_path = template.get_version_path(version)
        metadata = template.get_metadata(version)
        archive_path = source_path / "data.tar.gz"

        if not archive_path.exists():
            raise RegistryError(f"Data archive missing for {template} @{version}")

        dest_path = Path(dest_dir)
        if not force and not FileSystemEngine.is_empty(dest_path):
            raise DestinationNotEmptyError(f"Destination '{dest_dir}' is not empty.")

        FileSystemEngine.ensure_directory(dest_path)
        FileSystemEngine.decompress_and_render(archive_path, dest_path, variables or {})

        if metadata.hooks:
            logger.info("Running post-clone hooks...")
            FileSystemEngine.run_hooks(dest_path, metadata.hooks)

        logger.info(f"Successfully cloned {template} @{version} to {dest_dir}")

    def _fetch_from_remote(self, target_str: str, remote: RemoteTransport) -> None:
        """Internal helper to download a template from remote into the store."""
        metadata = remote.fetch_metadata(target_str)
        group, name, _ = self._parse_target(target_str)
        version = Version(metadata.version)

        template = Template(group, name, self.root_path)
        version_path = template.get_version_path(version)
        FileSystemEngine.ensure_directory(version_path)

        try:
            tarball_path = version_path / "data.tar.gz"
            remote.download_tarball(target_str, tarball_path)
            
            with tarfile.open(tarball_path, "r:gz"): 
                pass

            MetadataManager.save(version_path, metadata)
            self.cache.rebuild()
            self._trigger_sync()
            logger.info(f"Fetched remote template '{template}' version {version}")
        except Exception as e:
            FileSystemEngine.remove_directory(version_path)
            raise e

    def remove_template(self, target_str: str) -> None:
        """Removes a template or a specific version and refreshes state."""
        group, name, version_str = self._parse_target(target_str)
        template = Template(group, name, self.root_path)

        if not template.exists():
            raise TemplateNotFoundError(f"Template {template} not found.")

        if version_str:
            version = Version(version_str)
            version_path = template.get_version_path(version)
            if not version_path.exists():
                raise TemplateNotFoundError(f"Version {version} of {template} not found.")
            FileSystemEngine.remove_directory(version_path)
            if template.base_path.exists() and not any(template.base_path.iterdir()):
                FileSystemEngine.remove_directory(template.base_path)
        else:
            FileSystemEngine.remove_directory(template.base_path)

        self.cache.rebuild()
        self._trigger_sync()

    def list_templates(self, target_str: Optional[str] = None, 
                       filter_dict: Optional[Dict[str, str]] = None) -> List[Tuple[Template, Version, TemplateMetadata]]:
        """Lists templates using the cache for high performance."""
        results = []
        if target_str:
            group, name, _ = self._parse_target(target_str)
            versions = self.cache.get_versions(target_str)
            for v_str, m_dict in versions:
                v, m = Version(v_str), TemplateMetadata.from_dict(m_dict)
                if self._matches_filter(m, filter_dict):
                    results.append((Template(group, name, self.root_path), v, m))
        else:
            all_latest = self.cache.get_all()
            for target, v_str, m_dict in all_latest:
                v, m = Version(v_str), TemplateMetadata.from_dict(m_dict)
                if self._matches_filter(m, filter_dict):
                    g, n = target.split("/", 1)
                    results.append((Template(g, n, self.root_path), v, m))
        return results

    def search_templates(self, query: str) -> List[Tuple[Template, Version, TemplateMetadata]]:
        """Searches templates using the keyword-optimized cache."""
        results = []
        for target, v_str, m_dict in self.cache.search(query):
            v, m = Version(v_str), TemplateMetadata.from_dict(m_dict)
            g, n = target.split("/", 1)
            results.append((Template(g, n, self.root_path), v, m))
        return results

    def _matches_filter(self, metadata: TemplateMetadata, filter_dict: Optional[Dict[str, str]]) -> bool:
        if not filter_dict: return True
        for key, value in filter_dict.items():
            if key == "languages":
                if not any(value.lower() == lang.lower() for lang in metadata.languages): return False
                continue
            meta_value = getattr(metadata, key, None)
            if meta_value is None:
                if key == "tags": meta_value = metadata.tags
                else: return False
            if isinstance(meta_value, list):
                if value.lower() not in [v.lower() for v in meta_value]: return False
            elif str(meta_value).lower() != value.lower(): return False
        return True

    def get_template_details(self, target_str: str) -> Tuple[Template, Version, TemplateMetadata]:
        """Fetches exhaustive metadata for a specific template version."""
        group, name, version_str = self._parse_target(target_str)
        template = Template(group, name, self.root_path)
        if not template.exists(): raise TemplateNotFoundError(f"Template {template} not found.")
        
        if version_str == "latest" or version_str is None:
            version = template.get_latest_version()
        else:
            version = Version(version_str)
            
        if not version or not template.get_version_path(version).exists():
            raise TemplateNotFoundError(f"Version {version} of {template} not found.")
        return template, version, template.get_metadata(version)

    def doctor(self) -> List[Tuple[str, str, bool]]:
        """Performs diagnostics on the store and returns (check, message, status)."""
        results = []
        is_writable = os.access(self.root_path, os.W_OK)
        results.append(("Store path permissions", f"Writable ({self.root_path})" if is_writable else "Read-only", is_writable))

        all_ok, corrupted = True, []
        for group_dir in self.root_path.iterdir():
            if not group_dir.is_dir() or group_dir.name.startswith("."): continue
            for name_dir in group_dir.iterdir():
                if not name_dir.is_dir(): continue
                template = Template(group_dir.name, name_dir.name, self.root_path)
                for version in template.get_versions():
                    try:
                        template.get_metadata(version)
                        if not (template.get_version_path(version) / "data.tar.gz").exists():
                            corrupted.append(f"{template}@{version}"); all_ok = False
                    except Exception: corrupted.append(f"{template}@{version}"); all_ok = False

        results.append(("Metadata integrity", "All valid" if all_ok else f"Corrupted: {', '.join(corrupted)}", all_ok))
        return results
