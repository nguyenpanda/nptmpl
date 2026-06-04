import requests
import time
import json
import logging
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
from requests.exceptions import RequestException, Timeout, HTTPError
from nptmpl.core.remote.base import RemoteTransport
from nptmpl.core.metadata import TemplateMetadata
from nptmpl.core.errors import AuthenticationError, NetworkError, TemplateNotFoundError, RegistryError

logger = logging.getLogger("nptmpl.http")

class HttpTransport(RemoteTransport):
    """
    Concrete implementation of RemoteTransport for HTTP/HTTPS protocols.
    
    Handles REST API interactions with support for authentication, retries, 
    and streaming downloads.
    """

    def __init__(self, base_url: str, auth_token: Optional[str] = None, timeout: int = 10, retries: int = 3):
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self.timeout = timeout
        self.retries = retries
        self.session = requests.Session()
        if self.auth_token:
            self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        """Helper for making robust HTTP requests with retries and connection pooling."""
        url = f"{self.base_url}/{path.lstrip('/')}"

        last_exception = None

        for attempt in range(self.retries):
            try:
                response = self.session.request(method, url, timeout=self.timeout, **kwargs)
                if response.status_code in (502, 503, 504):
                    response.raise_for_status()
                
                if response.status_code == 404:
                    raise TemplateNotFoundError(f"Resource not found on remote: {url}")
                
                response.raise_for_status()
                return response
            except Timeout as e:
                last_exception = e
                time.sleep(1 * (attempt + 1))
            except HTTPError as e:
                last_exception = e
                status_code = e.response.status_code
                if status_code == 409:
                    raise RegistryError(f"Conflict on remote: {e.response.text}")
                if status_code in (401, 403):
                    raise AuthenticationError(f"Authentication failed for {url}: {e.response.text}")
                if status_code == 400:
                    raise RegistryError(f"Bad request to remote: {e.response.text}")
                if status_code in (502, 503, 504):
                    time.sleep(1 * (attempt + 1))
                    continue
                raise NetworkError(f"HTTP error {status_code}: {e.response.text or e}")
            except RequestException as e:
                last_exception = e
                time.sleep(1 * (attempt + 1))

        raise last_exception or NetworkError(f"Failed to connect to {url}")

    def fetch_metadata(self, target: str) -> TemplateMetadata:
        base_target = target.split("@")[0]
        response = self._request("GET", f"api/v1/templates/{base_target}")
        data = response.json()
        meta_dict = data.get("metadata", data)
        return TemplateMetadata.from_dict(meta_dict)

    def download_tarball(self, target: str, dest_path: Path) -> None:
        parts = target.split("@")
        base_target = parts[0]
        params = {}
        if len(parts) > 1:
            params["v"] = parts[1]

        response = self._request("GET", f"api/v1/templates/{base_target}/download", params=params, stream=True)

        try:
            with open(dest_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        except Exception as e:
            if dest_path.exists():
                dest_path.unlink()
            raise RegistryError(f"Failed to save tarball: {e}")

    def push_template(self, target: str, metadata: TemplateMetadata, tarball_path: Path, overwrite: bool = False) -> None:
        """Uploads a template with metadata, streaming the tarball to handle large files."""
        meta_dict = metadata.to_dict()
        meta_dict["target"] = target.split("@")[0]

        data = {
            "metadata_json": json.dumps(meta_dict),
            "overwrite": "true" if overwrite else "false"
        }

        with open(tarball_path, "rb") as f:
            files = {
                "tarball": (tarball_path.name, f, "application/gzip")
            }
            try:
                self._request("POST", "api/v1/templates/push", data=data, files=files)
            except Exception as e:
                if isinstance(e, (AuthenticationError, RegistryError, TemplateNotFoundError)):
                    raise e
                raise NetworkError(f"Failed to push template: {e}")

    def list_templates(self, query: Optional[str] = None) -> List[Tuple[str, str, Dict[str, Any]]]:
        params = {"q": query} if query else {}
        response = self._request("GET", "api/v1/templates", params=params)
        data = response.json()

        results = []
        for item in data.get("templates", []):
            results.append((item["target"], item["version"], item["metadata"]))
        return results

    def get_details(self, target: str) -> Tuple[str, str, Dict[str, Any]]:
        base_target = target.split("@")[0]
        response = self._request("GET", f"api/v1/templates/{base_target}")
        data = response.json()
        return data["target"], data["version"], data["metadata"]
