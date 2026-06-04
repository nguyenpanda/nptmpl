import pytest
import os
import stat
from nptmpl.core.metadata import Version
from nptmpl.core.store import TemplateStore
from nptmpl.core.engine import FileSystemEngine
from nptmpl.core.errors import ValidationError, DestinationNotEmptyError

@pytest.fixture
def setup_dirs(tmp_path):
    test_root = tmp_path / "test_complex_root"
    test_root.mkdir()
    store_path = test_root / "store"
    store_path.mkdir()
    src = test_root / "src"
    src.mkdir()
    dst = test_root / "dst"
    dst.mkdir()
    return {"store_path": store_path, "src": src, "dst": dst}

def test_integer_semver_sorting():
    v1 = Version("1.2.0")
    v2 = Version("1.9.0")
    v3 = Version("1.10.0")
    assert v1 < v2 < v3
    assert max([v1, v3, v2]) == v3

def test_nptmpl_is_directory(setup_dirs):
    (setup_dirs["src"] / ".nptmpl").mkdir()
    from nptmpl.core.metadata import MetadataManager
    with pytest.raises(IsADirectoryError):
        MetadataManager.load(setup_dirs["src"])

def test_symlink_preservation(setup_dirs):
    src = setup_dirs["src"]
    dst = setup_dirs["dst"]
    store_path = setup_dirs["store_path"]
    
    target_file = src / "target.txt"
    target_file.write_text("content")
    link_file = src / "link.txt"
    os.symlink("target.txt", link_file)
    
    # Add to store (this will compress it)
    (src / ".nptmpl").write_text("version: 1.0.0\nauthor: x\ndescription: y\nlanguages: [python]")
    store = TemplateStore(root_path=store_path)
    store.add_template(str(src), "group/name")
    
    # Clone it back
    store.clone_template("group/name", str(dst))
    
    assert (dst / "link.txt").is_symlink()
    assert os.readlink(dst / "link.txt") == "target.txt"

def test_read_only_file_removal(setup_dirs):
    src = setup_dirs["src"]
    ro_file = src / "readonly.txt"
    ro_file.write_text("readonly")
    os.chmod(ro_file, stat.S_IREAD) # Make read-only
    
    FileSystemEngine.remove_directory(src)
    assert not src.exists()

def test_destination_not_empty(setup_dirs):
    dst = setup_dirs["dst"]
    store_path = setup_dirs["store_path"]
    (dst / "somefile.txt").write_text("exists")
    
    # Mock a template in the store
    template_dir = store_path / "group" / "name" / "1.0.0"
    template_dir.mkdir(parents=True)
    (template_dir / ".nptmpl").write_text("version: 1.0.0\nauthor: x\ndescription: y\nlanguages: [python]")
    (template_dir / "data.tar.gz").touch() # Mock archive
    
    store = TemplateStore(root_path=store_path)
    with pytest.raises(DestinationNotEmptyError):
        store.clone_template("group/name", str(dst))

def test_regex_validation(setup_dirs):
    store = TemplateStore(root_path=setup_dirs["store_path"])
    # Valid
    store._parse_target("group/name")
    store._parse_target("group/name@1.0.0")
    
    # Invalid
    with pytest.raises(ValidationError):
        store._parse_target("group-no-name")
    with pytest.raises(ValidationError):
        store._parse_target("group/name@1.0.0@extra")
