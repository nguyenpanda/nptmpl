import pytest
import os
import json
import io
import tarfile
from fastapi.testclient import TestClient
from nptmpl.server.main import create_app

@pytest.fixture
def test_storage(tmp_path):
    storage = tmp_path / "server_storage"
    storage.mkdir()
    return storage

@pytest.fixture
def client(test_storage):
    # Use a local environment override instead of modifying os.environ globally if possible
    # But since create_app reads from os.environ, we must set it.
    # We'll restore it after the test.
    old_token = os.environ.get("NPTMPL_SERVER_TOKEN")
    os.environ["NPTMPL_SERVER_TOKEN"] = "test-token"
    
    try:
        app = create_app(test_storage)
        yield TestClient(app)
    finally:
        if old_token is None:
            del os.environ["NPTMPL_SERVER_TOKEN"]
        else:
            os.environ["NPTMPL_SERVER_TOKEN"] = old_token

def create_mock_tarball(files: dict = None):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        if not files:
            files = {"README.md": b"hello world"}
        for name, content in files.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            tar.addfile(tarinfo=info, fileobj=io.BytesIO(content))
    return buf.getvalue()

def test_push_path_traversal(client):
    """Test that path traversal attempts in push endpoint are rejected."""
    meta = {
        "target": "../../../etc/shadow",
        "version": "1.0.0",
        "author": "hacker",
        "description": "desc",
        "languages": ["python"],
        "added_date": "2024-01-01 00:00:00"
    }
    
    response = client.post(
        "/api/v1/templates/push",
        data={"metadata_json": json.dumps(meta)},
        files={"tarball": ("data.tar.gz", create_mock_tarball(), "application/gzip")},
        headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 400
    assert "Invalid path component" in response.json()["detail"] or "Invalid version" in response.json()["detail"]

    # Test path traversal in version
    meta2 = {
        "target": "test/valid",
        "version": "../../../etc/shadow",
        "author": "hacker",
        "description": "desc",
        "languages": ["python"],
        "added_date": "2024-01-01 00:00:00"
    }
    response2 = client.post(
        "/api/v1/templates/push",
        data={"metadata_json": json.dumps(meta2)},
        files={"tarball": ("data.tar.gz", create_mock_tarball(), "application/gzip")},
        headers={"Authorization": "Bearer test-token"}
    )
    assert response2.status_code == 400

def test_inspect_path_traversal(client):
    """Test that path traversal attempts in inspect endpoint are rejected."""
    # First push a valid template
    meta = {
        "target": "test/valid",
        "version": "1.0.0",
        "author": "tester",
        "description": "desc",
        "languages": ["python"],
        "added_date": "2024-01-01 00:00:00"
    }
    client.post(
        "/api/v1/templates/push",
        data={"metadata_json": json.dumps(meta)},
        files={"tarball": ("data.tar.gz", create_mock_tarball(), "application/gzip")},
        headers={"Authorization": "Bearer test-token"}
    )
    
    # Try traversing in group/name/version with urlencoded dots to bypass client-side resolution
    resp = client.get("/api/v1/inspect/%2e%2e/test/1.0.0?path=README.md")
    assert resp.status_code in (400, 404)
    
    resp2 = client.get("/api/v1/inspect/test/valid/%2e%2e%2f%2e%2e%2fetc?path=README.md")
    assert resp2.status_code in (400, 404)

def test_tarball_inspector_memory_limit(client):
    """Test that inspecting a large file does not load the entire file into memory."""
    # Create a 2MB file
    large_content = b"a" * (2 * 1024 * 1024)
    tarball = create_mock_tarball({"README.md": large_content})
    
    meta = {
        "target": "test/large",
        "version": "1.0.0",
        "author": "tester",
        "description": "desc",
        "languages": ["python"],
        "added_date": "2024-01-01 00:00:00"
    }
    
    push_resp = client.post(
        "/api/v1/templates/push",
        data={"metadata_json": json.dumps(meta)},
        files={"tarball": ("data.tar.gz", tarball, "application/gzip")},
        headers={"Authorization": "Bearer test-token"}
    )
    assert push_resp.status_code == 200

    # Inspect the file
    inspect_resp = client.get("/api/v1/inspect/test/large/1.0.0?path=README.md")
    assert inspect_resp.status_code == 200
    
    data = inspect_resp.json()
    # The content should be limited to 1MB
    assert len(data["content"]) == 1024 * 1024
