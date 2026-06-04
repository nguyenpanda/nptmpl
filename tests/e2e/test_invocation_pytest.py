import pytest
import subprocess
import os
import sys

def run_command(args):
    cmd = [sys.executable, "-m", "nptmpl.cli"] + args
    env = os.environ.copy()
    env["PYTHONPATH"] = "src:."
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env
    )

def test_main_help():
    result = run_command(["--help"])
    assert result.returncode == 0
    assert "nptmpl - A Professional Local Template Manager" in result.stdout
    assert "Available Commands" in result.stdout

@pytest.mark.parametrize("cmd", ["init", "add", "update", "clone", "list", "search", "detail", "remove", "doctor", "path", "serve"])
def test_subcommand_help(cmd):
    result = run_command([cmd, "--help"])
    assert result.returncode == 0
    assert "usage:" in result.stdout
    assert "--help" in result.stdout

def test_invalid_command():
    result = run_command(["nonexistent-command"])
    assert result.returncode != 0
    assert "invalid choice: 'nonexistent-command'" in result.stderr

def test_missing_required_args():
    result = run_command(["add"])
    assert result.returncode != 0
    assert "the following arguments are required: source_dir" in result.stderr

def test_version_logic_error_clean_exit():
    result = run_command(["add", "./invalid_path", "test/target"])
    assert result.returncode != 0
    assert "Error:" in result.stdout + result.stderr
    assert "Traceback" not in result.stdout + result.stderr
