import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
from nptmpl.server.routes.admin import router as admin_router
from nptmpl.server.routes.public import router as public_router
from nptmpl.server.db import DatabaseManager
from nptmpl.server.auth import get_admin_user
from nptmpl.server.main import create_app
from nptmpl.server.deps import get_config

@pytest.fixture(scope="module")
def temp_storage(tmp_path_factory):
    storage = tmp_path_factory.mgettemp("storage")
    (storage / "static").mkdir(exist_ok=True)
    return storage

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
    app = create_app(mock_storage)
    app.dependency_overrides[get_admin_user] = lambda: "admin"
    
    mock_config = MagicMock()
    mock_config.get_ui_config.return_value = {
        "title": "Test Server",
        "theme_color": "emerald-500",
        "logo_text": "nptmpl",
        "github_url": "#",
        "author_name": "Tester"
    }
    mock_config.get_public_url.return_value = "http://localhost:9090"
    app.dependency_overrides[get_config] = lambda: mock_config
    
    app.state.db = mock_db
    app.state.storage_path = mock_storage
    
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

def test_home_route(client, mock_db):
    mock_db.list_templates.return_value = []
    mock_db.get_stats.return_value = {"total_templates": 0, "total_downloads": 0}
    mock_db.get_filter_options.return_value = {"languages": [], "tags": [], "licenses": [], "authors": []}
    
    response = client.get("/")
    assert response.status_code == 200
    assert "nptmpl" in response.text

def test_about_route(client):
    response = client.get("/about")
    assert response.status_code == 200
    assert "About" in response.text

def test_template_detail_route(client, mock_db, mock_storage):
    mock_db.get_template.return_value = {
        "group_name": "g1", "name": "n1", "added_date": "2024-01-01 00:00:00", "versions": [{"version": "1.0.0", "readme_content": "# Hello"}]
    }
    mock_db.get_related_templates.return_value = []
    
    version_dir = mock_storage / "g1" / "n1" / "1.0.0"
    version_dir.mkdir(parents=True)
    (version_dir / "data.tar.gz").write_text("fake")
    
    with patch("nptmpl.server.inspector.TarballInspector.list_files", return_value=[]):
        response = client.get("/g1/n1")
    
    assert response.status_code == 200
    assert "n1" in response.text

def test_admin_dashboard(client, mock_db):
    mock_db.get_stats.return_value = {}
    mock_db.list_templates.return_value = []
    
    response = client.get("/admin")
    assert response.status_code == 200
    assert "Admin Dashboard" in response.text

def test_admin_delete(client, mock_db, mock_storage):
    version_dir = mock_storage / "g1" / "n1" / "1.0.0"
    version_dir.mkdir(parents=True)
    
    mock_db.delete_version.return_value = True
    
    response = client.post("/admin/delete/g1/n1/1.0.0", follow_redirects=False)
    assert response.status_code == 303 # Redirect to /admin
    assert not version_dir.exists()

def test_docs_route(client):
    with patch("nptmpl.server.routes.public.Path.exists", return_value=True), \
         patch("nptmpl.server.routes.public.open", create=True) as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = "# Docs Content"
        response = client.get("/docs/README")
    
    assert response.status_code == 200
    assert "Docs Content" in response.text or "<h1>Docs Content</h1>" in response.text
