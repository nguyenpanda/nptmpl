import pytest
import subprocess
import os
import sys
import time
import requests
import sqlite3
import json
from pathlib import Path
from fastapi.testclient import TestClient
from nptmpl.server.main import create_app

# Helper to run CLI
def run_nptmpl(args, env_overrides=None):
    cmd = [sys.executable, "-m", "nptmpl.cli"] + args
    env = os.environ.copy()
    env["PYTHONPATH"] = "src:."
    # Ensure no leaking server token
    if "NPTMPL_SERVER_TOKEN" in env:
        del env["NPTMPL_SERVER_TOKEN"]
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env
    )

@pytest.fixture
def server_env(tmp_path):
    # Clear environment variables that might leak
    for env_var in ["NPTMPL_SERVER_TOKEN", "NPTMPL_AUTH_TOKEN", "NPTMPL_ADMIN_USER", "NPTMPL_ADMIN_PASS"]:
        if env_var in os.environ:
            del os.environ[env_var]

    storage = tmp_path / "server_storage"
    storage.mkdir()
    # Create a config with known credentials
    config_path = tmp_path / "test_server_config.yaml"
    config_path.write_text("""
server:
  admin:
    username: "testadmin"
    password: "testpassword"
""")
    from nptmpl.core.config import ConfigManager
    config = ConfigManager(config_path=str(config_path))

    app = create_app(storage, config=config)
    client = TestClient(app)
    return {"client": client, "storage": storage, "tmp_path": tmp_path, "config": config}

def test_api_public_endpoints(server_env):
    client = server_env["client"]
    # List templates (empty)
    response = client.get("/api/v1/templates")
    assert response.status_code == 200
    assert "templates" in response.json()
    assert len(response.json()["templates"]) == 0

def test_api_token_authentication(server_env):
    client = server_env["client"]
    # We need to ensure the app state has a token
    server_env["config"].config_data["core"] = {"auth_token": "secret-token"}

    # Try push without token
    response = client.post("/api/v1/templates/push")
    assert response.status_code == 401

    # Try push with wrong token
    headers = {"Authorization": "Bearer wrong-token"}
    response = client.post("/api/v1/templates/push", headers=headers)
    assert response.status_code == 401

def test_admin_session_auth(server_env):
    client = server_env["client"]
    # Redirects to login
    response = client.get("/admin", follow_redirects=False)
    assert response.status_code in (302, 303, 307)
    assert "/login" in response.headers["location"]

    # Login
    response = client.post("/login", data={
        "username": "testadmin",
        "password": "testpassword"
    }, follow_redirects=False)
    assert response.status_code in (302, 303, 307)
    assert "/admin" in response.headers["location"]

    # Access admin with session
    response = client.get("/admin")
    assert response.status_code == 200
    assert "System_Overview" in response.text

@pytest.mark.skipif(os.environ.get("CI") == "true", reason="Skipping full network test in CI")
def test_remote_cli_workflow(tmp_path):
    # 1. Setup Server
    server_storage = tmp_path / "remote_storage"
    server_storage.mkdir()
    port = 8889 # Use different port to avoid conflicts
    token = "test-remote-token"

    server_config_path = tmp_path / "remote_server_config.yaml"
    server_config_path.write_text(f"""
core:
  auth_token: "{token}"
""")

    # Start server in background
    env = os.environ.copy()
    env["PYTHONPATH"] = "src:."
    # CRITICAL: Clear any leaked token from other tests
    if "NPTMPL_SERVER_TOKEN" in env:
        del env["NPTMPL_SERVER_TOKEN"]

    server_proc = subprocess.Popen(
        [sys.executable, "-m", "nptmpl.cli", "--config", str(server_config_path), "serve", "--port", str(port), "--storage", str(server_storage)],
        env=env
    )

    time.sleep(3)

    try:
        # 2. Setup Client
        client_root = tmp_path / "client"
        client_root.mkdir()
        config_path = client_root / "config.yaml"
        client_store = client_root / "store"
        client_store.mkdir()

        config_content = f"""
core:
  store_path: "{client_store}"
  auth_token: "{token}"
"""
        config_path.write_text(config_content)

        # 3. Add local template
        proj_dir = client_root / "my-template"
        proj_dir.mkdir()
        (proj_dir / "README.md").write_text("Template README")
        (proj_dir / "main.py").write_text("print('hello')")

        run_nptmpl(["init", str(proj_dir)], {"NPTMPL_CONFIG_PATH": str(config_path)})
        run_nptmpl(["add", str(proj_dir), "web/starter"], {"NPTMPL_CONFIG_PATH": str(config_path)})

        # 4. Push to remote
        res = run_nptmpl(["push", "web/starter", f"http://localhost:{port}"], {"NPTMPL_CONFIG_PATH": str(config_path)})
        assert res.returncode == 0, f"STDOUT: {res.stdout}\nSTDERR: {res.stderr}"

        # 5. Search remote
        res = run_nptmpl(["search", "web", "--remote", f"http://localhost:{port}"], {"NPTMPL_CONFIG_PATH": str(config_path)})
        assert res.returncode == 0, f"STDOUT: {res.stdout}\nSTDERR: {res.stderr}"
        assert "web/starter" in res.stdout

        # 6. Clone from remote
        cloned_dir = tmp_path / "cloned_remote"
        # We MUST ensure NPTMPL_STORE_PATH is set so it doesn't try to use default
        res = run_nptmpl(["clone", f"http://localhost:{port}/api/v1/templates/web/starter", str(cloned_dir)], 
                       {"NPTMPL_STORE_PATH": str(tmp_path / "new_machine_store")})

        assert res.returncode == 0, f"STDOUT: {res.stdout}\nSTDERR: {res.stderr}"
        assert (cloned_dir / "main.py").exists()
        assert (cloned_dir / "main.py").read_text() == "print('hello')"

    finally:
        server_proc.terminate()
        server_proc.wait()

def test_web_ui_rendering(server_env):
    client = server_env["client"]
    # Check About page renders site_meta
    response = client.get("/about")
    assert response.status_code == 200
    assert "nguyenpanda" in response.text or "Author Name" in response.text
    
    # Check theme color is in CSS
    assert "--theme-color" in response.text
