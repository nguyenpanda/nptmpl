import tarfile
import logging

from pathlib import Path
from typing import List, Dict, Any, Optional


logger = logging.getLogger("nptmpl.inspector")

class TarballInspector:
    """
    Helper to inspect and validate compressed templates without extracting them.
    
    Useful for Web UI previews and server-side integrity checks.
    """

    @staticmethod
    def verify_integrity(archive_path: Path) -> bool:
        """Checks if the archive is a valid Gzip-compressed tarball."""
        try:
            with tarfile.open(archive_path, "r:gz") as tar:
                tar.getmembers()
                return True
        except Exception:
            return False

    @staticmethod
    def extract_readme(archive_path: Path) -> Optional[str]:
        """Attempts to find and extract README.md from the archive root."""
        try:
            with tarfile.open(archive_path, "r:gz") as tar:
                for member in tar.getmembers():
                    if member.name.lower() == "readme.md":
                        f = tar.extractfile(member)
                        if f:
                            content = f.read(1024 * 1024)
                            try:
                                return content.decode("utf-8")
                            except UnicodeDecodeError:
                                return None
        except Exception as e:
            logger.debug(f"Failed to extract README from {archive_path}: {e}")
        return None

    @staticmethod
    def list_files(archive_path: Path) -> List[Dict[str, Any]]:
        """
        Lists all files in the archive with their types and sizes.
        
        Returns a sorted list of dictionaries containing path, size, and type.
        """
        if not archive_path.exists():
            return []

        files = []
        try:
            with tarfile.open(archive_path, "r:gz") as tar:
                for member in tar.getmembers():
                    if member.name == ".nptmpl":
                        continue

                    files.append({
                        "path": member.name,
                        "size": member.size,
                        "type": "directory" if member.isdir() else "file"
                    })
        except Exception as e:
            logger.error(f"Error inspecting archive {archive_path}: {e}")

        return sorted(files, key=lambda x: (x["type"] != "directory", x["path"]))

    @staticmethod
    def get_file_content(archive_path: Path, file_path: str) -> Optional[str]:
        """Reads the content of a specific file from the archive as a UTF-8 string."""
        if not archive_path.exists():
            return None

        try:
            with tarfile.open(archive_path, "r:gz") as tar:
                member = tar.getmember(file_path)
                if member.isfile():
                    f = tar.extractfile(member)
                    if f:
                        content = f.read(1024 * 1024)
                        try:
                            return content.decode("utf-8")
                        except UnicodeDecodeError:
                            return "[Binary File]"
        except Exception as e:
            logger.error(f"Error reading file {file_path} from {archive_path}: {e}")

        return None
