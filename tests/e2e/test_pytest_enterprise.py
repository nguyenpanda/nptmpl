import pytest
import os
import io
import json
import tarfile
from fastapi.testclient import TestClient
from nptmpl.server.main import create_app
from nptmpl.core.store import TemplateStore
from nptmpl.core.remote.http import HttpTransport
import requests_mock

@pytest.fixture
def test_storage(tmp_path):
    storage = tmp_path / "server_storage"
    storage.mkdir()
    return storage

@pytest.fixture
def client(test_storage):
    # Set a test token
    os.environ["NPTMPL_SERVER_TOKEN"] = "test-token"
    app = create_app(test_storage)
    return TestClient(app)

def create_mock_tarball(content: bytes = b"mock content") -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        info = tarfile.TarInfo(name="README.md")
        info.size = len(content)
        tar.addfile(tarinfo=info, fileobj=io.BytesIO(content))
    return buf.getvalue()

def test_push_auth_bypass(client):
    # Access without header
    response = client.post("/api/v1/templates/push", data={"metadata_json": "{}"})
    assert response.status_code == 401

def test_push_malformed_tarball(client):
    meta = {
        "target": "test/malformed",
        "version": "1.0.0",
        "author": "tester",
        "description": "desc",
        "languages": ["python"],
        "added_date": "2024-01-01 00:00:00"
    }
    # Send random bytes as tarball
    files = {"tarball": ("data.tar.gz", b"not a tarball", "application/gzip")}
    response = client.post(
        "/api/v1/templates/push",
        data={"metadata_json": json.dumps(meta)},
        files=files,
        headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 400
    assert "Corrupted or invalid tarball" in response.json()["detail"]

def test_push_immutability_breach(client):
    meta = {
        "target": "test/immutable",
        "version": "1.0.0",
        "author": "tester",
        "description": "desc",
        "languages": ["python"],
        "added_date": "2024-01-01 00:00:00"
    }
    tarball = create_mock_tarball()
    
    # 1st push
    response = client.post(
        "/api/v1/templates/push",
        data={"metadata_json": json.dumps(meta)},
        files={"tarball": ("data.tar.gz", tarball, "application/gzip")},
        headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 200

    # 2nd push (same version)
    response = client.post(
        "/api/v1/templates/push",
        data={"metadata_json": json.dumps(meta)},
        files={"tarball": ("data.tar.gz", tarball, "application/gzip")},
        headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]

def test_metadata_xss_protection(client):
    xss_payload = "<script>alert('xss')</script>"
    meta = {
        "target": "test/xss",
        "version": "1.0.0",
        "author": xss_payload,
        "description": xss_payload,
        "languages": ["python"],
        "added_date": "2024-01-01 00:00:00"
    }
    tarball = create_mock_tarball()
    response = client.post(
        "/api/v1/templates/push",
        data={"metadata_json": json.dumps(meta)},
        files={"tarball": ("data.tar.gz", tarball, "application/gzip")},
        headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 200
    
    # Verify escaping in Web UI
    resp_web = client.get("/")
    assert xss_payload not in resp_web.text
    assert "&lt;script&gt;alert(&#39;xss&#39;)&lt;/script&gt;" in resp_web.text

def test_client_partial_network_failure(tmp_path):
    # Mocking client behavior during network drop mid-stream
    store_path = tmp_path / "client_store"
    store_path.mkdir()
    store = TemplateStore(store_path)
    
    remote = HttpTransport("http://fake-registry", auth_token="token")
    
    with requests_mock.Mocker() as m:
        # Mock metadata response
        m.get("http://fake-registry/api/v1/templates/test/broken", json={
            "metadata": {
                "name": "broken", "version": "1.0.0", "author": "x", 
                "description": "y", "languages": ["z"], "added_date": "2024-01-01 00:00:00"
            }
        })
        # Mock tarball download with a connection error
        m.get("http://fake-registry/api/v1/templates/test/broken/download", exc=Exception("Network drop"))
        
        with pytest.raises(Exception):
            store.clone_template("test/broken", str(tmp_path / "dst"), remote=remote)
            
        # Verify no corrupted files or empty directories left in store
        version_dir = store_path / "test" / "broken" / "1.0.0"
        assert not version_dir.exists()
