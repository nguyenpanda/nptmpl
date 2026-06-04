import logging
from pathlib import Path

from nptmpl.core.metadata import MetadataManager, Version


logger = logging.getLogger("nptmpl.reindexer")

class ServerReindexer:
    """Utility to scan a storage directory and sync metadata with the server database."""

    @staticmethod
    def reindex(storage_path: Path, db):
        """Scans the storage directory and synchronizes the database (adds new, updates existing, prunes missing)."""
        if not storage_path.exists():
            return

        logger.info(f"Reindexing templates in {storage_path}...")
        found_versions = set()

        count = 0
        for group_dir in storage_path.iterdir():
            if not group_dir.is_dir() or group_dir.name.startswith("."):
                continue

            for name_dir in group_dir.iterdir():
                if not name_dir.is_dir():
                    continue

                for version_dir in name_dir.iterdir():
                    if not version_dir.is_dir() or not Version.is_valid(version_dir.name):
                        continue

                    metadata_file = version_dir / ".nptmpl"
                    if metadata_file.exists():
                        try:
                            metadata = MetadataManager.load(version_dir)
                            meta_dict = metadata.to_dict()
                            group, name, version = group_dir.name, name_dir.name, version_dir.name
                            meta_dict["target"] = f"{group}/{name}"
                            
                            found_versions.add((group, name, version))

                            from nptmpl.server.inspector import TarballInspector
                            readme = None
                            tarball_path = version_dir / "data.tar.gz"
                            if tarball_path.exists():
                                readme = TarballInspector.extract_readme(tarball_path)

                            db.add_template_version(meta_dict, readme)
                            count += 1
                        except Exception as e:
                            logger.warning(f"Skipping {version_dir}: {e}")

        pruned_count = 0
        try:
            with db._get_connection() as conn:
                rows = conn.execute("""
                    SELECT t.group_name, t.name, v.version 
                    FROM templates t 
                    JOIN versions v ON t.id = v.template_id
                """).fetchall()
                
                for row in rows:
                    if (row['group_name'], row['name'], row['version']) not in found_versions:
                        db.delete_version(row['group_name'], row['name'], row['version'])
                        pruned_count += 1
        except Exception as e:
            logger.error(f"Failed to prune database: {e}")

        logger.info(f"Reindex complete. Synchronized {count} versions, pruned {pruned_count} missing versions.")
