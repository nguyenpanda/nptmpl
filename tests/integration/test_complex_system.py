import pytest
import subprocess
import os
import sys
import json
import shutil
import sqlite3
from pathlib import Path
from datetime import datetime

def run_nptmpl(args, config_path):
    cmd = [sys.executable, "-m", "nptmpl.cli"] + args
    env = os.environ.copy()
    env["PYTHONPATH"] = "src:."
    env["NPTMPL_CONFIG_PATH"] = str(config_path)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env
    )

@pytest.fixture
def clean_env(tmp_path):
    store_path = tmp_path / "store"
    store_path.mkdir()
    config_path = tmp_path / "config.yaml"
    
    # Initialize a professional config
    config_content = f"""
core:
  store_path: "{store_path}"
server:
  admin:
    username: "admin"
    password: "password"
"""
    config_path.write_text(config_content)
    
    # Force initialize the registry.db to trigger sync logic
    db_path = store_path / "registry.db"
    from nptmpl.server.db import DatabaseManager
    DatabaseManager(db_path)
    
    return {
        "store_path": store_path,
        "config_path": config_path,
        "db_path": db_path,
        "tmp_path": tmp_path
    }

def test_full_lifecycle_and_sync(clean_env):
    config_path = clean_env["config_path"]
    store_path = clean_env["store_path"]
    db_path = clean_env["db_path"]
    
    # 1. nptmpl init
    proj_dir = clean_env["tmp_path"] / "my-project"
    proj_dir.mkdir()
    res = run_nptmpl(["init", str(proj_dir)], config_path)
    assert res.returncode == 0
    assert (proj_dir / ".nptmpl").exists()
    
    # Customize .nptmpl
    with open(proj_dir / ".nptmpl", "r") as f:
        import yaml
        meta = yaml.safe_load(f)
    meta["author"] = "System Tester"
    meta["description"] = "Complex integration test template"
    meta["languages"] = ["python", "bash"]
    meta["tags"] = ["test", "integration"]
    with open(proj_dir / ".nptmpl", "w") as f:
        yaml.dump(meta, f)
    
    # 2. nptmpl add
    res = run_nptmpl(["add", str(proj_dir), "test/integrated"], config_path)
    assert res.returncode == 0
    
    # Verify disk
    assert (store_path / "test" / "integrated" / "1.0.0" / "data.tar.gz").exists()
    
    # Verify SQLite Sync
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM templates WHERE group_name='test' AND name='integrated'").fetchone()
    assert row is not None
    assert row["author"] == "System Tester"
    conn.close()
    
    # 3. nptmpl list
    res = run_nptmpl(["list"], config_path)
    assert res.returncode == 0
    assert "test/integrated" in res.stdout
    
    # 4. nptmpl search
    res = run_nptmpl(["search", "System Tester"], config_path)
    assert res.returncode == 0
    assert "test/integrated" in res.stdout
    
    # 5. nptmpl update (edge case: lower version)
    meta["version"] = "0.9.0"
    with open(proj_dir / ".nptmpl", "w") as f:
        yaml.dump(meta, f)
    res = run_nptmpl(["update", "test/integrated", str(proj_dir)], config_path)
    assert res.returncode != 0
    
    # nptmpl update (success: 1.1.0)
    meta["version"] = "1.1.0"
    with open(proj_dir / ".nptmpl", "w") as f:
        yaml.dump(meta, f)
    res = run_nptmpl(["update", "test/integrated", str(proj_dir)], config_path)
    assert res.returncode == 0
    
    # Verify DB has both versions
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT version FROM versions WHERE template_id = (SELECT id FROM templates WHERE name='integrated')").fetchall()
    assert len(rows) == 2
    conn.close()
    
    # 6. nptmpl remove (specific version) with interactive confirmation
    p = subprocess.Popen(
        [sys.executable, "-m", "nptmpl.cli", "remove", "test/integrated@1.0.0"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "PYTHONPATH": "src:.", "NPTMPL_CONFIG_PATH": str(config_path)}
    )
    p.communicate(input="y\n")
    assert p.returncode == 0
    
    # Verify disk: 1.0.0 is gone, 1.1.0 remains
    assert not (store_path / "test" / "integrated" / "1.0.0").exists()
    assert (store_path / "test" / "integrated" / "1.1.0").exists()
    
    # Verify DB Sync: Only 1.1.0 remains
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT version FROM versions WHERE template_id = (SELECT id FROM templates WHERE name='integrated')").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "1.1.0"
    conn.close()
    # Input 'y' for confirmation is handled by subprocess if we had a non-interactive mode, 
    # but here we might need to simulate 'y' via stdin if it prompts.
    # Actually CLIApp._confirm uses input(), so we need to pipe "y\n".
    
def test_cli_prompts_and_sync(clean_env):
    config_path = clean_env["config_path"]
    db_path = clean_env["db_path"]
    
    # Setup a template to remove
    proj_dir = clean_env["tmp_path"] / "to-remove"
    proj_dir.mkdir()
    run_nptmpl(["init", str(proj_dir)], config_path)
    run_nptmpl(["add", str(proj_dir), "rm/me"], config_path)
    
    # Verify in DB
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM templates WHERE name='me'").fetchone()[0] == 1
    conn.close()
    
    # rm me with confirmation
    p = subprocess.Popen(
        [sys.executable, "-m", "nptmpl.cli", "remove", "rm/me"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "PYTHONPATH": "src:.", "NPTMPL_CONFIG_PATH": str(config_path)}
    )
    stdout, stderr = p.communicate(input="y\n")
    assert p.returncode == 0
    
    # Verify Sync: Missing from DB
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM templates WHERE name='me'").fetchone()[0] == 0
    conn.close()

def test_edge_case_malformed_metadata(clean_env):
    config_path = clean_env["config_path"]
    proj_dir = clean_env["tmp_path"] / "bad-meta"
    proj_dir.mkdir()
    (proj_dir / ".nptmpl").write_text("this is not yaml: [ : }")
    
    res = run_nptmpl(["add", str(proj_dir), "bad/meta"], config_path)
    assert res.returncode != 0

def test_scale_registry_and_search(clean_env):
    config_path = clean_env["config_path"]
    db_path = clean_env["db_path"]
    
    # Batch add 50 templates
    for i in range(50):
        proj_dir = clean_env["tmp_path"] / f"proj-{i}"
        proj_dir.mkdir()
        (proj_dir / ".nptmpl").write_text(f"""
version: 1.0.0
author: dev-{i}
description: description for {i}
languages: [lang-{i % 5}]
""")
        run_nptmpl(["add", str(proj_dir), f"group/proj-{i}"], config_path)
    
    # Verify DB count
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM templates").fetchone()[0] == 50
    conn.close()
    
    # List and filter
    res = run_nptmpl(["list", "--language", "lang-2"], config_path)
    # lang-2 should appear for i=2, 7, 12, 17, 22, 27, 32, 37, 42, 47 (10 templates)
    assert res.stdout.count("group/proj-") == 10
    
    # Search efficiency
    res = run_nptmpl(["search", "proj-42"], config_path)
    assert "group/proj-42" in res.stdout

def test_path_traversal_mitigation(clean_env):
    config_path = clean_env["config_path"]
    # Try to add a template with a malicious name
    res = run_nptmpl(["add", ".", "../../etc/passwd"], config_path)
    assert res.returncode != 0

def test_config_introspection(clean_env):
    config_path = clean_env["config_path"]
    res = run_nptmpl(["config", "show"], config_path)
    assert res.returncode == 0
    assert "core.store_path" in res.stdout
    # Check that some part of the store path is there (to avoid absolute/relative issues with symlinks/macOS /private)
    assert "store" in res.stdout

def test_nptmpl_path_command(clean_env):
    config_path = clean_env["config_path"]
    res = run_nptmpl(["path", "--show-store"], config_path)
    assert res.returncode == 0
    assert str(clean_env["store_path"]) in res.stdout

    res = run_nptmpl(["path", "--show-config"], config_path)
    assert res.returncode == 0
    assert str(config_path) in res.stdout

def test_clone_with_injection(clean_env):
    config_path = clean_env["config_path"]
    
    # 1. Setup template with variables
    proj_dir = clean_env["tmp_path"] / "var-proj"
    proj_dir.mkdir()
    (proj_dir / ".nptmpl").write_text("""
version: 1.0.0
author: tester
description: desc
languages: [python]
variables:
  user_name: "Name of the user"
""")
    (proj_dir / "{{ user_name }}_file.txt").write_text("Hello {{ user_name }}!")
    
    run_nptmpl(["add", str(proj_dir), "test/vars"], config_path)
    
    # 2. Clone with variables
    dest_dir = clean_env["tmp_path"] / "cloned-vars"
    res = run_nptmpl(["clone", "test/vars", str(dest_dir), "-v", "user_name=Panda"], config_path)
    assert res.returncode == 0
    
    # Verify injection in filename
    assert (dest_dir / "Panda_file.txt").exists()
    # Verify injection in content
    assert "Hello Panda!" in (dest_dir / "Panda_file.txt").read_text()

def test_nptmpl_push_unreachable(clean_env):
    config_path = clean_env["config_path"]
    
    # Setup template
    proj_dir = clean_env["tmp_path"] / "push-proj"
    proj_dir.mkdir()
    (proj_dir / ".nptmpl").write_text("version: 1.0.0\nauthor: tester\ndescription: desc\nlanguages: [python]")
    run_nptmpl(["add", str(proj_dir), "test/push"], config_path)
    
    # Push to unreachable URL
    res = run_nptmpl(["push", "test/push", "http://0.0.0.0:12345"], config_path)
    # Should fail but exit cleanly
    assert res.returncode != 0
    assert "Error" in res.stdout + res.stderr
