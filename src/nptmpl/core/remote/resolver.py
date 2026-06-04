import re
from pathlib import Path
from typing import Tuple, Optional, Union
from nptmpl.core.remote.base import RemoteTransport
from nptmpl.core.remote.http import HttpTransport
from nptmpl.core.remote.ssh import SshTransport

from enum import Enum, auto

class TargetType(Enum):
    LOCAL_PATH = auto()
    LOCAL_REGISTRY = auto()
    HTTP = auto()
    SSH = auto()

class TargetResolver:
    """Parses and resolves target strings into local or remote contexts."""

    HTTP_PATTERN = re.compile(r"^https?://")
    SSH_PATTERN = re.compile(r"^ssh://(?P<user>[^@]+)@(?P<host>[^:/]+)(?::(?P<port>\d+))?(?P<path>/.*)?$")
    REGISTRY_PATTERN = re.compile(r"^([^/@]+)/([^/@]+)(?:@([^/@]+))?$")

    @staticmethod
    def resolve(target: str, auth_token: Optional[str] = None) -> Tuple[TargetType, Union[Path, str, RemoteTransport], Optional[str]]:
        """
        Resolves target string.
        Returns: (type, context, remote_target)
        """

        if TargetResolver.HTTP_PATTERN.match(target):
            if "/api/v1/templates/" in target:
                base_url, remote_target = target.split("/api/v1/templates/", 1)
                return TargetType.HTTP, HttpTransport(base_url, auth_token=auth_token), remote_target
            
            parts = target.rstrip("/").split("/")
            if len(parts) >= 5:
                remote_target = f"{parts[-2]}/{parts[-1]}"
                base_url = "/".join(parts[:-2])
                return TargetType.HTTP, HttpTransport(base_url, auth_token=auth_token), remote_target
            
            return TargetType.HTTP, HttpTransport(target, auth_token=auth_token), None

        ssh_match = TargetResolver.SSH_PATTERN.match(target)
        if ssh_match:
            user = ssh_match.group("user")
            host = ssh_match.group("host")
            port = int(ssh_match.group("port")) if ssh_match.group("port") else 22
            full_path = ssh_match.group("path").rstrip("/") if ssh_match.group("path") else ""

            path_parts = full_path.split("/")
            if len(path_parts) >= 3:
                 remote_store = "/".join(path_parts[:-2])
                 remote_target = "/".join(path_parts[-2:])
                 return TargetType.SSH, SshTransport(host, user, remote_store, port), remote_target
            else:
                return TargetType.SSH, SshTransport(host, user, full_path, port), None

        local_path = Path(target)
        if target.startswith(".") or target.startswith("/") or local_path.exists():
            return TargetType.LOCAL_PATH, local_path, None

        if TargetResolver.REGISTRY_PATTERN.match(target):
            return TargetType.LOCAL_REGISTRY, target, None

        raise ValueError(f"Could not resolve target: {target}")
