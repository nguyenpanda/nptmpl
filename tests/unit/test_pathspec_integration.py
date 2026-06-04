import tarfile
from nptmpl.core.engine import FileSystemEngine

def test_compress_directory_respects_ignore(tmp_path):
    # Setup source directory
    src = tmp_path / "src"
    src.mkdir()
    (src / "include.txt").write_text("keep")
    (src / ".DS_Store").write_text("ignore me")
    (src / ".idea").mkdir()
    (src / ".idea" / "config.xml").write_text("ignore me")
    (src / "Icon\r").write_text("ignore me")
    
    # Nested ignored dir
    (src / "node_modules").mkdir()
    (src / "node_modules" / "some_pkg").mkdir()
    (src / "node_modules" / "some_pkg" / "index.js").write_text("ignore me")

    archive_path = tmp_path / "data.tar.gz"
    # We test that the default patterns in engine.py and these extras work
    ignore_patterns = ["node_modules/"]

    # Run compression
    FileSystemEngine.compress_directory(src, archive_path, ignore_patterns)

    # Verify contents of archive
    with tarfile.open(archive_path, "r:gz") as tar:
        names = tar.getnames()
        assert "include.txt" in names
        assert ".DS_Store" not in names
        assert ".idea" not in names
        assert ".idea/config.xml" not in names
        assert not any("Icon" in name for name in names)
        assert "node_modules" not in names
        assert "node_modules/some_pkg/index.js" not in names

def test_compress_directory_respects_gitignore(tmp_path):
    # Setup source directory
    src = tmp_path / "src_git"
    src.mkdir()
    (src / "include.txt").write_text("keep")
    (src / "secret.env").write_text("hide me")
    (src / ".gitignore").write_text("secret.env\ntemp/")
    
    temp_dir = src / "temp"
    temp_dir.mkdir()
    (temp_dir / "file.tmp").write_text("ignore me")

    archive_path = tmp_path / "git_data.tar.gz"

    # Run compression
    FileSystemEngine.compress_directory(src, archive_path)

    # Verify contents of archive
    with tarfile.open(archive_path, "r:gz") as tar:
        names = tar.getnames()
        assert "include.txt" in names
        assert ".gitignore" in names
        assert "secret.env" not in names
        assert "temp" not in names
        assert "temp/file.tmp" not in names
