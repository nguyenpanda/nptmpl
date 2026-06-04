import pytest
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from nptmpl.cli.app import CLIApp
from nptmpl.core.metadata import MetadataManager

@pytest.fixture
def cli_store_path(tmp_path):
    store = tmp_path / "cli_store"
    store.mkdir()
    return store

@pytest.fixture
def cli_config_path(tmp_path, cli_store_path):
    config = tmp_path / "config.yaml"
    config.write_text(f"""
core:
  store_path: "{cli_store_path}"
  auth_token: "test-token"
""")
    return config

def run_cli(*args):
    app = CLIApp(list(args))
    app.run()
    return app

def test_cli_help(capsys):
    with pytest.raises(SystemExit) as e:
        CLIApp(["--help"])
    assert e.value.code == 0
    captured = capsys.readouterr()
    assert "nptmpl - A Professional Local Template Manager" in captured.out

def test_cli_version(capsys):
    with pytest.raises(SystemExit) as e:
        CLIApp(["--version"])
    assert e.value.code == 0
    captured = capsys.readouterr()
    assert "nptmpl" in captured.out

def test_cli_init(tmp_path, cli_config_path):
    target = tmp_path / "new_template"
    target.mkdir()
    run_cli("--config", str(cli_config_path), "init", str(target))
    assert (target / ".nptmpl").exists()

def test_cli_add_and_list(tmp_path, cli_config_path, capsys):
    target = tmp_path / "my_template"
    target.mkdir()
    MetadataManager.create_default(target)
    
    run_cli("--config", str(cli_config_path), "add", str(target), "group/name")
    
    # Test list
    run_cli("--config", str(cli_config_path), "list")
    captured = capsys.readouterr()
    assert "group/name" in captured.out

def test_cli_search(tmp_path, cli_config_path, capsys):
    target = tmp_path / "my_template"
    target.mkdir()
    MetadataManager.create_default(target)
    run_cli("--config", str(cli_config_path), "add", str(target), "search/target")
    
    run_cli("--config", str(cli_config_path), "search", "search")
    captured = capsys.readouterr()
    assert "search/target" in captured.out

def test_cli_detail(tmp_path, cli_config_path, capsys):
    target = tmp_path / "my_template"
    target.mkdir()
    MetadataManager.create_default(target)
    run_cli("--config", str(cli_config_path), "add", str(target), "detail/target")
    
    run_cli("--config", str(cli_config_path), "detail", "detail/target")
    captured = capsys.readouterr()
    assert "detail/target" in captured.out

def test_cli_remove(tmp_path, cli_config_path, capsys):
    target = tmp_path / "my_template"
    target.mkdir()
    MetadataManager.create_default(target)
    run_cli("--config", str(cli_config_path), "add", str(target), "remove/target")
    
    with patch('nptmpl.cli.app.confirm', return_value=True):
        run_cli("--config", str(cli_config_path), "remove", "remove/target")
    
    run_cli("--config", str(cli_config_path), "list")
    captured = capsys.readouterr()
    assert "remove/target" not in captured.out

def test_cli_doctor(cli_config_path, capsys):
    run_cli("--config", str(cli_config_path), "doctor")
    captured = capsys.readouterr()
    assert "System diagnostics" in captured.out or "System diagnostics" in captured.err or "OK" in captured.out

def test_cli_path(cli_config_path, capsys):
    run_cli("--config", str(cli_config_path), "path", "--show-config")
    captured = capsys.readouterr()
    assert str(cli_config_path) in captured.out

def test_cli_update(tmp_path, cli_config_path):
    target = tmp_path / "my_template"
    target.mkdir()
    MetadataManager.create_default(target)
    run_cli("--config", str(cli_config_path), "add", str(target), "update/target")
    
    # Modify version and update
    meta_path = target / ".nptmpl"
    content = meta_path.read_text().replace("1.0.0", "1.1.0")
    meta_path.write_text(content)
    
    run_cli("--config", str(cli_config_path), "update", "update/target", str(target))
    
    app = CLIApp(["--config", str(cli_config_path), "list"])
    _, versions, _ = app.store.get_template_details("update/target")
    assert str(versions) == "1.1.0"

def test_cli_serve(cli_config_path):
    with patch("nptmpl.server.main.start_server") as mock_start:
        run_cli("--config", str(cli_config_path), "serve", "--port", "9091")
        mock_start.assert_called_once()
        args, kwargs = mock_start.call_args
        # port is the second positional argument
        assert args[1] == 9091

def test_cli_ui(cli_config_path):
    with patch("nptmpl.server.main.start_server") as mock_start, \
         patch("webbrowser.open") as mock_open:
        # We need to be careful with the thread in _handle_ui
        # but mocking start_server should be enough to stop it
        run_cli("--config", str(cli_config_path), "ui", "--port", "8081")
        mock_start.assert_called_once()
        args, kwargs = mock_start.call_args
        # port is the second positional argument
        assert args[1] == 8081

