import pytest
import os
import shutil
import json
import tarfile
import yaml
import sqlite3
from pathlib import Path
from fastapi.testclient import TestClient
from fastapi.concurrency import run_in_threadpool
from nptmpl.server.main import create_app
from nptmpl.core.metadata import TemplateMetadata, Version
from nptmpl.server.db import DatabaseManager

# --- HELPERS ---

def create_mock_template_tarball(path: Path, metadata: dict, files: dict = None):
    """Creates a .tar.gz archive with .nptmpl and optional dummy files."""
    with tarfile.open(path, "w:gz") as tar:
        # Add metadata
        meta_path = path.parent / ".nptmpl"
        with open(meta_path, "w") as f:
            yaml.dump(metadata, f)
        tar.add(meta_path, arcname=".nptmpl")
        meta_path.unlink()
        
        # Add extra files
        if files:
            for f_name, content in files.items():
                f_path = path.parent / f_name
                f_path.write_text(content)
                tar.add(f_path, arcname=f_name)
                f_path.unlink()

# --- FIXTURES ---

@pytest.fixture
def server_context(tmp_path):
    """Provides a fresh TestClient, storage path, and DB manager for each test."""
    storage = tmp_path / "server_storage"
    storage.mkdir()
    
    db_path = tmp_path / "test_registry.db"
    
    from nptmpl.core.config import ConfigManager
    config_path = tmp_path / "config.yaml"
    token = "test-token"
    config_path.write_text(f"""
core:
  auth_token: "{token}"
server:
  admin:
    username: "admin"
    password: "password"
""")
    config = ConfigManager(config_path=str(config_path))
    
    app = create_app(storage, config=config)
    db_manager = DatabaseManager(db_path)
    app.state.db = db_manager
    
    client = TestClient(app)
    return {
        "client": client,
        "db": db_manager,
        "storage": storage,
        "tmp": tmp_path,
        "token": token
    }

# --- TESTS ---

def test_push_and_db_persistence(server_context):
    client = server_context["client"]
    db = server_context["db"]
    token = server_context["token"]
    
    target = "web/react-app"
    version = "1.0.0"
    metadata = {
        "name": "react-app",
        "version": version,
        "author": "Panda",
        "description": "A clean React template",
        "languages": ["javascript", "typescript"],
        "tags": ["frontend", "web"],
        "added_date": "2026-05-20 10:00:00",
        "target": target
    }
    
    tar_path = server_context["tmp"] / "upload.tar.gz"
    create_mock_template_tarball(tar_path, metadata, {"README.md": "# React App"})
    
    with open(tar_path, "rb") as f:
        response = client.post(
            "/api/v1/templates/push",
            headers={"Authorization": f"Bearer {token}"},
            data={"metadata_json": json.dumps(metadata)},
            files={"tarball": ("upload.tar.gz", f, "application/gzip")}
        )
    
    assert response.status_code == 200
    t_row = db.get_template("web", "react-app")
    assert t_row is not None
    assert t_row["author"] == "Panda"
    assert "javascript" in t_row["languages"]
    assert len(t_row["versions"]) == 1
    assert t_row["versions"][0]["version"] == "1.0.0"
    assert "# React App" in t_row["versions"][0]["readme_content"]
    assert (server_context["storage"] / "web" / "react-app" / "1.0.0" / "data.tar.gz").exists()

def test_delete_last_version_cleans_template_and_fs(server_context):
    client = server_context["client"]
    db = server_context["db"]
    token = server_context["token"]
    storage = server_context["storage"]
    
    target = "test/to-delete"
    version = "1.2.3"
    metadata = {"target": target, "version": version, "author": "X", "description": "Y", "languages": ["C"], "added_date": "2026-01-01"}
    
    tar_path = server_context["tmp"] / "del.tar.gz"
    create_mock_template_tarball(tar_path, metadata)
    with open(tar_path, "rb") as f:
        client.post("/api/v1/templates/push", headers={"Authorization": f"Bearer {token}"},
                    data={"metadata_json": json.dumps(metadata)}, files={"tarball": ("del.tar.gz", f)})
    
    response = client.delete(f"/api/v1/templates/test/to-delete/{version}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert db.get_template("test", "to-delete") is None
    assert not (storage / "test" / "to-delete").exists()
    assert not (storage / "test").exists()

def test_repush_after_deletion_fix(server_context):
    client = server_context["client"]
    token = server_context["token"]
    
    target = "bug/repush"
    version = "2.0.0"
    metadata = {"target": target, "version": version, "author": "A", "description": "B", "languages": ["Go"], "added_date": "2026-02-02"}
    
    tar_path = server_context["tmp"] / "repush1.tar.gz"
    create_mock_template_tarball(tar_path, metadata)
    with open(tar_path, "rb") as f:
        client.post("/api/v1/templates/push", headers={"Authorization": f"Bearer {token}"},
                    data={"metadata_json": json.dumps(metadata)}, files={"tarball": ("repush1.tar.gz", f)})
    
    client.delete(f"/api/v1/templates/bug/repush/{version}", headers={"Authorization": f"Bearer {token}"})
    
    tar_path2 = server_context["tmp"] / "repush2.tar.gz"
    create_mock_template_tarball(tar_path2, metadata)
    with open(tar_path2, "rb") as f:
        response = client.post(
            "/api/v1/templates/push",
            headers={"Authorization": f"Bearer {token}"},
            data={"metadata_json": json.dumps(metadata)},
            files={"tarball": ("repush2.tar.gz", f)}
        )
    
    assert response.status_code == 200
    assert response.json()["message"] == "Template pushed successfully"

def test_push_overwrite_behaviour(server_context):
    client = server_context["client"]
    db = server_context["db"]
    token = server_context["token"]
    
    target = "web/overwrite"
    version = "1.0.0"
    meta1 = {"target": target, "version": version, "author": "Old", "description": "Old", "languages": ["L1"], "added_date": "2026-01-01"}
    meta2 = {"target": target, "version": version, "author": "New", "description": "New", "languages": ["L2"], "added_date": "2026-01-02"}
    
    tar1 = server_context["tmp"] / "tar1.tar.gz"
    create_mock_template_tarball(tar1, meta1, {"file.txt": "old content"})
    with open(tar1, "rb") as f:
        client.post("/api/v1/templates/push", headers={"Authorization": f"Bearer {token}"},
                    data={"metadata_json": json.dumps(meta1)}, files={"tarball": ("tar1.tar.gz", f)})
    
    tar2 = server_context["tmp"] / "tar2.tar.gz"
    create_mock_template_tarball(tar2, meta2, {"file.txt": "new content"})
    with open(tar2, "rb") as f:
        response = client.post(
            "/api/v1/templates/push",
            headers={"Authorization": f"Bearer {token}"},
            data={"metadata_json": json.dumps(meta2), "overwrite": "true"},
            files={"tarball": ("tar2.tar.gz", f)}
        )
    
    assert response.status_code == 200
    t = db.get_template("web", "overwrite")
    assert t["author"] == "New"
    assert t["versions"][0]["added_date"] == "2026-01-02"

def test_push_invalid_metadata_rejected(server_context):
    client = server_context["client"]
    db = server_context["db"]
    token = server_context["token"]
    
    bad_meta = {"target": "fail/test", "author": "X"}
    tar = server_context["tmp"] / "fail.tar.gz"
    create_mock_template_tarball(tar, {})
    with open(tar, "rb") as f:
        response = client.post(
            "/api/v1/templates/push",
            headers={"Authorization": f"Bearer {token}"},
            data={"metadata_json": json.dumps(bad_meta)},
            files={"tarball": ("fail.tar.gz", f)}
        )
    assert response.status_code == 400
    assert db.get_template("fail", "test") is None

def test_push_corrupted_tarball_cleanup(server_context):
    client = server_context["client"]
    db = server_context["db"]
    token = server_context["token"]
    storage = server_context["storage"]
    
    target = "fail/corrupt"
    metadata = {"target": target, "version": "1.0.0", "author": "X", "description": "D", "languages": ["L"], "added_date": "T"}
    corrupt_file = server_context["tmp"] / "not_a_tar.gz"
    corrupt_file.write_text("I am definitely not a tarball")
    
    with open(corrupt_file, "rb") as f:
        response = client.post(
            "/api/v1/templates/push",
            headers={"Authorization": f"Bearer {token}"},
            data={"metadata_json": json.dumps(metadata)},
            files={"tarball": ("corrupt.tar.gz", f)}
        )
    
    assert response.status_code == 400
    assert db.get_template("fail", "corrupt") is None
    # Now this should pass with the enhanced cleanup
    assert not (storage / "fail").exists()

def test_path_traversal_prevention(server_context):
    client = server_context["client"]
    token = server_context["token"]
    
    malicious_metadata = {"target": "../../etc/passwd", "version": "1.0.0", "author": "H", "description": "E", "languages": ["B"], "added_date": "N"}
    tar = server_context["tmp"] / "evil.tar.gz"
    create_mock_template_tarball(tar, malicious_metadata)
    with open(tar, "rb") as f:
        response = client.post(
            "/api/v1/templates/push",
            headers={"Authorization": f"Bearer {token}"},
            data={"metadata_json": json.dumps(malicious_metadata)},
            files={"tarball": ("evil.tar.gz", f)}
        )
    assert response.status_code == 400

@pytest.mark.asyncio
async def test_push_multiple_versions_ordering(server_context):
    client = server_context["client"]
    db = server_context["db"]
    token = server_context["token"]
    
    target = "multi/ver"
    versions = ["1.0.0", "1.1.0", "2.0.0", "0.9.0"]
    for v in versions:
        meta = {"target": target, "version": v, "author": "V", "description": "D", "languages": ["L"], "added_date": f"2026-01-{v[0]}"}
        tar = server_context["tmp"] / f"v{v}.tar.gz"
        create_mock_template_tarball(tar, meta)
        with open(tar, "rb") as f:
            client.post("/api/v1/templates/push", headers={"Authorization": f"Bearer {token}"},
                        data={"metadata_json": json.dumps(meta)}, files={"tarball": (f"v{v}.tar.gz", f)})
    
    t = await run_in_threadpool(db.get_template, "multi", "ver")
    assert t["versions"][0]["version"] == "0.9.0" 
    
    all_t = await run_in_threadpool(db.list_templates)
    match = next(item for item in all_t if item["name"] == "ver")
    assert match["version"] == "0.9.0"

def test_list_templates_filtering_and_search_sync(server_context):
    client = server_context["client"]
    token = server_context["token"]
    
    templates_data = [
        {"target": "web/react", "author": "A1", "lang": ["js"], "tags": ["t1"]},
        {"target": "web/vue", "author": "A2", "lang": ["js"], "tags": ["t2"]},
        {"target": "cli/python", "author": "A1", "lang": ["py"], "tags": ["t1", "t3"]},
    ]
    for t in templates_data:
        meta = {"target": t["target"], "version": "1.0.0", "author": t["author"], "description": "desc", "languages": t["lang"], "tags": t["tags"], "added_date": "2026-01-01"}
        tar = server_context["tmp"] / f"{t['target'].replace('/', '_')}.tar.gz"
        create_mock_template_tarball(tar, meta)
        with open(tar, "rb") as f:
            client.post("/api/v1/templates/push", headers={"Authorization": f"Bearer {token}"},
                        data={"metadata_json": json.dumps(meta)}, files={"tarball": (tar.name, f)})

    res = client.get("/api/v1/templates?lang=js")
    assert len(res.json()["templates"]) == 2
    res = client.get("/api/v1/templates?author=A1")
    assert len(res.json()["templates"]) == 2
    res = client.get("/api/v1/templates?q=python")
    assert len(res.json()["templates"]) == 1
    assert res.json()["templates"][0]["target"] == "cli/python"

def test_push_handles_phantom_directory(server_context):
    """Ensures push succeeds if a directory exists but no DB record is found (phantom directory)."""
    client = server_context["client"]
    token = server_context["token"]
    storage = server_context["storage"]
    
    target = "phantom/test"
    version = "1.0.0"
    metadata = {"target": target, "version": version, "author": "X", "description": "D", "languages": ["L"], "added_date": "T"}
    
    # 1. Manually create a phantom directory on disk
    phantom_dir = storage / "phantom" / "test" / "1.0.0"
    phantom_dir.mkdir(parents=True)
    (phantom_dir / "orphaned.txt").write_text("I should not be here")
    
    # 2. Push (Should NOT return 409, should instead auto-cleanup and succeed)
    tar = server_context["tmp"] / "phantom_fix.tar.gz"
    create_mock_template_tarball(tar, metadata, {"fixed.txt": "content"})
    
    with open(tar, "rb") as f:
        response = client.post(
            "/api/v1/templates/push",
            headers={"Authorization": f"Bearer {token}"},
            data={"metadata_json": json.dumps(metadata)},
            files={"tarball": ("phantom_fix.tar.gz", f)}
        )
    
    assert response.status_code == 200
    assert response.json()["message"] == "Template pushed successfully"
    assert (phantom_dir / "data.tar.gz").exists()
    assert not (phantom_dir / "orphaned.txt").exists()
