import paramiko
import os
import yaml
import logging
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
from nptmpl.core.remote.base import RemoteTransport
from nptmpl.core.metadata import TemplateMetadata, Version
from nptmpl.core.errors import AuthenticationError, NetworkError, TemplateNotFoundError

logger = logging.getLogger("nptmpl.ssh")

class SshTransport(RemoteTransport):
    """
    Concrete implementation of RemoteTransport for SSH/SFTP protocols.
    
    Uses paramiko for secure communication. Requires host verification 
    via system known_hosts for security.
    """

    def __init__(self, host: str, user: str, remote_store_path: str, port: int = 22, password: Optional[str] = None):
        self.host = host
        self.user = user
        self.port = port
        self.remote_store_path = remote_store_path.rstrip("/")
        self.password = password
        self.client: Optional[paramiko.SSHClient] = None
        self.sftp: Optional[paramiko.SFTPClient] = None

    def _connect(self):
        """Initializes SSH and SFTP connections."""
        if self.client:
            return

        try:
            self.client = paramiko.SSHClient()
            self.client.load_system_host_keys()
            self.client.set_missing_host_key_policy(paramiko.RejectPolicy())
            
            self.client.connect(
                self.host, 
                port=self.port, 
                username=self.user, 
                password=self.password,
                timeout=10,
                allow_agent=True,
                look_for_keys=True
            )
            self.sftp = self.client.open_sftp()
        except paramiko.AuthenticationException:
            raise AuthenticationError(f"SSH authentication failed for {self.user}@{self.host}")
        except paramiko.SSHException as e:
            if "not found in known_hosts" in str(e):
                raise NetworkError(f"Host {self.host} not found in known_hosts. Manual verification required for security.")
            raise NetworkError(f"SSH connection failed to {self.host}: {e}")
        except Exception as e:
            raise NetworkError(f"Failed to connect to {self.host}: {e}")

    def _close(self):
        """Safely closes active connections."""
        if self.sftp:
            self.sftp.close()
        if self.client:
            self.client.close()
        self.client = None
        self.sftp = None

    def fetch_metadata(self, target: str) -> TemplateMetadata:
        self._connect()
        try:
            group, name, version = self._resolve_target(target)
            remote_path = f"{self.remote_store_path}/{group}/{name}/{version}/.nptmpl"

            try:
                with self.sftp.open(remote_path, "r") as f:
                    data = yaml.safe_load(f)
                    return TemplateMetadata.from_dict(data)
            except FileNotFoundError:
                raise TemplateNotFoundError(f"Metadata not found on remote: {remote_path}")
        finally:
            self._close()

    def download_tarball(self, target: str, dest_path: Path) -> None:
        self._connect()
        try:
            group, name, version = self._resolve_target(target)
            remote_path = f"{self.remote_store_path}/{group}/{name}/{version}/data.tar.gz"

            try:
                self.sftp.get(remote_path, str(dest_path))
            except FileNotFoundError:
                raise TemplateNotFoundError(f"Tarball not found on remote: {remote_path}")
        finally:
            self._close()

    def push_template(self, target: str, metadata: TemplateMetadata, tarball_path: Path, overwrite: bool = False) -> None:
        self._connect()
        try:
            group, name, version = self._resolve_target(target)
            remote_base = f"{self.remote_store_path}/{group}/{name}/{version}"

            try:
                self.sftp.stat(remote_base)
                if not overwrite:
                    raise ValueError(f"Conflict: Version {version} of {group}/{name} already exists on remote.")
            except FileNotFoundError:
                pass

            self._mkdir_p(remote_base)

            with self.sftp.open(f"{remote_base}/.nptmpl", "w") as f:
                yaml.dump(metadata.to_dict(), f, sort_keys=False)

            self.sftp.put(str(tarball_path), f"{remote_base}/data.tar.gz")
        finally:
            self._close()

    def list_templates(self, query: Optional[str] = None) -> List[Tuple[str, str, Dict[str, Any]]]:
        self._connect()
        results = []

        try:
            for group in self.sftp.listdir(self.remote_store_path):
                group_path = f"{self.remote_store_path}/{group}"
                try:
                    for name in self.sftp.listdir(group_path):
                        name_path = f"{group_path}/{name}"
                        try:
                            versions = self.sftp.listdir(name_path)
                            valid_versions = [v for v in versions if Version.is_valid(v)]
                            if not valid_versions:
                                continue
                            latest_v = str(sorted([Version(v) for v in valid_versions])[-1])

                            meta_path = f"{name_path}/{latest_v}/.nptmpl"
                            with self.sftp.open(meta_path, "r") as f:
                                meta = yaml.safe_load(f)
                                target = f"{group}/{name}"
                                if not query or query.lower() in target.lower() or query.lower() in meta.get("description", "").lower():
                                    results.append((target, latest_v, meta))
                        except Exception:
                            continue
                except Exception:
                    continue
        except FileNotFoundError:
            pass
        finally:
            self._close()
        return results

    def get_details(self, target: str) -> Tuple[str, str, Dict[str, Any]]:
        self._connect()
        try:
            group, name, version = self._resolve_target(target)
            meta_path = f"{self.remote_store_path}/{group}/{name}/{version}/.nptmpl"
            with self.sftp.open(meta_path, "r") as f:
                meta = yaml.safe_load(f)
            return f"{group}/{name}", version, meta
        finally:
            self._close()

    def _resolve_target(self, target: str) -> Tuple[str, str, str]:
        if "@" in target:
            base, version = target.split("@", 1)
        else:
            base, version = target, None

        group, name = base.split("/", 1)

        if not version:
            path = f"{self.remote_store_path}/{group}/{name}"
            try:
                versions = self.sftp.listdir(path)
                valid_versions = [v for v in versions if Version.is_valid(v)]
                if not valid_versions:
                    raise TemplateNotFoundError(f"No versions found for {target}")
                version = str(sorted([Version(v) for v in valid_versions])[-1])
            except FileNotFoundError:
                raise TemplateNotFoundError(f"Template {target} not found on remote.")

        return group, name, version

    def _mkdir_p(self, remote_directory: str):
        dirs = remote_directory.split("/")
        current_dir = ""
        if remote_directory.startswith("/"):
            current_dir = "/"

        for dir_name in dirs:
            if not dir_name:
                continue
            current_dir = os.path.join(current_dir, dir_name)
            try:
                self.sftp.mkdir(current_dir)
            except IOError:
                pass
