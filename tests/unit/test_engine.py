import pytest
import os
import tarfile
from pathlib import Path
from nptmpl.core.engine import FileSystemEngine
from nptmpl.core.errors import EngineError, ExtractionError

def test_copy_template(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "file.txt").write_text("hello")
    (src / "subdir").mkdir()
    (src / "subdir" / "inner.txt").write_text("world")
    
    dst = tmp_path / "dst"
    FileSystemEngine.copy_template(src, dst)
    
    assert (dst / "file.txt").read_text() == "hello"
    assert (dst / "subdir" / "inner.txt").read_text() == "world"

def test_compress_directory(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "file.txt").write_text("hello")
    (src / ".git").mkdir()
    (src / ".git" / "config").write_text("secret")
    
    archive = tmp_path / "archive.tar.gz"
    FileSystemEngine.compress_directory(src, archive)
    
    assert archive.exists()
    with tarfile.open(archive, "r:gz") as tar:
        names = tar.getnames()
        assert "file.txt" in names
        assert ".git/config" not in names

def test_decompress_and_render(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "file_{{ name }}.txt").write_text("Hello {{ name }}!")
    
    archive = tmp_path / "archive.tar.gz"
    FileSystemEngine.compress_directory(src, archive)
    
    dst = tmp_path / "dst"
    FileSystemEngine.decompress_and_render(archive, dst, {"name": "world"})
    
    assert (dst / "file_world.txt").exists()
    assert (dst / "file_world.txt").read_text() == "Hello world!"

def test_decompress_unsafe_path(tmp_path):
    archive = tmp_path / "unsafe.tar.gz"
    archive.write_bytes(b"")  # Truly empty file
    
    with pytest.raises(EngineError, match="Archive is missing or empty"):
        FileSystemEngine.decompress_and_render(archive, tmp_path / "dst", {})

def test_run_hooks(tmp_path):
    (tmp_path / "script.sh").write_text("echo 'hello' > hook_out.txt")
    (tmp_path / "script.sh").chmod(0o755)
    
    FileSystemEngine.run_hooks(tmp_path, ["sh script.sh"])
    assert (tmp_path / "hook_out.txt").read_text().strip() == "hello"

def test_run_hooks_fail(tmp_path):
    with pytest.raises(EngineError, match="Post-clone hook failed"):
        FileSystemEngine.run_hooks(tmp_path, ["exit 1"])

def test_remove_directory(tmp_path):
    d = tmp_path / "to_remove"
    d.mkdir()
    (d / "file.txt").write_text("data")
    
    FileSystemEngine.remove_directory(d)
    assert not d.exists()

def test_is_empty(tmp_path):
    d = tmp_path / "dir"
    d.mkdir()
    assert FileSystemEngine.is_empty(d)
    
    (d / "file.txt").write_text("data")
    assert not FileSystemEngine.is_empty(d)

def test_ensure_directory(tmp_path):
    d = tmp_path / "new" / "dir"
    FileSystemEngine.ensure_directory(d)
    assert d.is_dir()

def test_binary_file_skips_rendering(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    # Create a dummy "binary" file by extension
    img = src / "test.png"
    img.write_text("{{ should_not_render }}")
    
    archive = tmp_path / "archive.tar.gz"
    FileSystemEngine.compress_directory(src, archive)
    
    dst = tmp_path / "dst"
    FileSystemEngine.decompress_and_render(archive, dst, {"should_not_render": "oops"})
    
    assert (dst / "test.png").read_text() == "{{ should_not_render }}"

def test_decompress_path_traversal_relative(tmp_path):
    archive_path = tmp_path / "traversal.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tar:
        # Create a member with '..' in it
        info = tarfile.TarInfo(name="../../etc/passwd")
        tar.addfile(info)
    
    dst = tmp_path / "dst"
    with pytest.raises(ExtractionError, match="Unsafe path detected"):
        FileSystemEngine.decompress_and_render(archive_path, dst, {})

def test_decompress_path_traversal_absolute(tmp_path):
    archive_path = tmp_path / "absolute.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tar:
        info = tarfile.TarInfo(name="/../etc/passwd")
        tar.addfile(info)
    
    dst = tmp_path / "dst"
    with pytest.raises(ExtractionError, match="Unsafe path detected"):
        FileSystemEngine.decompress_and_render(archive_path, dst, {})

def test_decompress_unsafe_symlink(tmp_path):
    archive_path = tmp_path / "symlink.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tar:
        # Absolute symlink
        info = tarfile.TarInfo(name="link")
        info.type = tarfile.SYMTYPE
        info.linkname = "/etc/passwd"
        tar.addfile(info)
    
    dst = tmp_path / "dst"
    with pytest.raises(EngineError, match="Absolute link detected"):
        FileSystemEngine.decompress_and_render(archive_path, dst, {})

def test_render_tree_invalid_syntax(tmp_path):
    root = tmp_path / "render_root"
    root.mkdir()
    (root / "bad.txt").write_text("{{ invalid syntax }")
    
    # Should not raise exception but log a warning (which we don't check here)
    # The file should remain unrendered
    FileSystemEngine._render_tree(root, {"var": "val"})
    assert (root / "bad.txt").read_text() == "{{ invalid syntax }"
