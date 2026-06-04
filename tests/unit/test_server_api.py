import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
from nptmpl.server.api import router, download_router, inspect_router
from nptmpl.server.db import DatabaseManager
from nptmpl.server.deps import get_db, get_storage, get_config
from nptmpl.server.auth import get_api_key

app = FastAPI()
app.include_router(router)
app.include_router(download_router)
app.include_router(inspect_router)

@pytest.fixture
def mock_db():
    return MagicMock(spec=DatabaseManager)

@pytest.fixture
def mock_storage(tmp_path):
    storage = tmp_path / "storage"
    storage.mkdir()
    return storage

@pytest.fixture
def client(mock_db, mock_storage):
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_storage] = lambda: mock_storage
    app.dependency_overrides[get_config] = lambda: MagicMock()
    app.dependency_overrides[get_api_key] = lambda: "test-token"
    
    # Also set app.state for inspect_router
    app.state.storage_path = mock_storage
    app.state.db = mock_db
    
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

def test_list_templates(client, mock_db):
    mock_db.list_templates.return_value = [
        {"group_name": "group1", "name": "name1", "version": "1.0.0"}
    ]
    response = client.get("/api/v1/templates")
    assert response.status_code == 200
    data = response.json()
    assert len(data["templates"]) == 1
    assert data["templates"][0]["target"] == "group1/name1"

def test_get_template(client, mock_db):
    mock_db.get_template.return_value = {
        "group_name": "group1", "name": "name1", "versions": [{"version": "1.0.0"}]
    }
    response = client.get("/api/v1/templates/group1/name1")
    assert response.status_code == 200
    assert response.json()["target"] == "group1/name1"

def test_get_template_not_found(client, mock_db):
    mock_db.get_template.return_value = None
    response = client.get("/api/v1/templates/non/existent")
    assert response.status_code == 404

def test_download_template(client, mock_db, mock_storage):
    mock_db.get_template.return_value = {
        "versions": [{"version": "1.0.0"}]
    }
    
    version_dir = mock_storage / "group1" / "name1" / "1.0.0"
    version_dir.mkdir(parents=True)
    tarball = version_dir / "data.tar.gz"
    tarball.write_text("fake tarball content")
    
    response = client.get("/api/v1/templates/group1/name1/download")
    assert response.status_code == 200
    assert response.content == b"fake tarball content"

def test_push_template(client, mock_db, mock_storage):
    metadata = {
        "target": "new/template",
        "version": "1.0.0"
    }
    
    with patch("nptmpl.server.api.TarballInspector.verify_integrity", return_value=True), \
         patch("nptmpl.server.api.TarballInspector.extract_readme", return_value="# Readme"):
        
        response = client.post(
            "/api/v1/templates/push",
            data={"metadata_json": json.dumps(metadata), "overwrite": "false"},
            files={"tarball": ("data.tar.gz", b"fake tarball", "application/gzip")}
        )
        
    assert response.status_code == 200
    assert response.json()["message"] == "Template pushed successfully"
    assert (mock_storage / "new" / "template" / "1.0.0" / "data.tar.gz").exists()
    mock_db.add_template_version.assert_called()

def test_delete_version(client, mock_db, mock_storage):
    version_dir = mock_storage / "group1" / "name1" / "1.0.0"
    version_dir.mkdir(parents=True)
    
    mock_db.delete_version.return_value = True # Fully deleted
    
    response = client.delete("/api/v1/templates/group1/name1/1.0.0")
    assert response.status_code == 200
    assert not version_dir.exists()
    mock_db.delete_version.assert_called_with("group1", "name1", "1.0.0")

def test_inspect_file(client, mock_db, mock_storage):
    version_dir = mock_storage / "group1" / "name1" / "1.0.0"
    version_dir.mkdir(parents=True)
    tarball = version_dir / "data.tar.gz"
    tarball.write_text("fake")
    
    with patch("nptmpl.server.api.TarballInspector.get_file_content", return_value="print('hello')"):
        response = client.get("/api/v1/inspect/group1/name1/1.0.0?path=test.py")
    
    assert response.status_code == 200
    assert response.json()["content"] == "print('hello')"
    assert "highlight" in response.json()["html_content"]
