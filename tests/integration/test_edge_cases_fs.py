import pytest
import os
from pathlib import Path
from nptmpl.core.store import TemplateStore
from nptmpl.core.errors import EngineError, DestinationNotEmptyError

@pytest.fixture
def store(tmp_path):
    store_path = tmp_path / "store"
    return TemplateStore(store_path)

def test_symlink_loop(store, tmp_path):
    """Test handling of templates containing symlink loops."""
    template_dir = tmp_path / "my_template"
    template_dir.mkdir()
    
    # Create a symlink loop: loop -> .
    loop_link = template_dir / "loop"
    os.symlink(".", loop_link)
    
    # Initialize metadata
    from nptmpl.core.metadata import MetadataManager
    MetadataManager.create_default(template_dir)
    
    # Add to store
    store.add_template(str(template_dir), "test/loop")
    
    # Clone it
    dest = tmp_path / "clone_dst"
    store.clone_template("test/loop", str(dest))
    
    assert dest.exists()
    assert (dest / "loop").is_symlink()

def test_max_path_length(store, tmp_path):
    """Test handling of extremely deep directory structures."""
    # Create a very deep path. MAX_PATH on Linux/Mac is usually 4096, but individual components are 255.
    # We'll create a path with many levels.
    template_dir = tmp_path / "deep_template"
    curr = template_dir
    for i in range(50): # 50 levels deep
        curr = curr / f"level_{i}"
    curr.mkdir(parents=True)
    (curr / "leaf.txt").write_text("hello")
    
    from nptmpl.core.metadata import MetadataManager
    MetadataManager.create_default(template_dir)
    
    store.add_template(str(template_dir), "test/deep")
    
    dest = tmp_path / "deep_clone"
    store.clone_template("test/deep", str(dest))
    
    assert (dest / Path(*[f"level_{i}" for i in range(50)]) / "leaf.txt").read_text() == "hello"

def test_zero_byte_tarball(store, tmp_path):
    """Test handling of a corrupted (zero-byte) data.tar.gz in the store."""
    template_dir = tmp_path / "empty_template"
    template_dir.mkdir()
    from nptmpl.core.metadata import MetadataManager
    MetadataManager.create_default(template_dir)
    
    store.add_template(str(template_dir), "test/zerobyte")
    
    # Corrupt it manually
    target_path = store.root_path / "test" / "zerobyte" / "1.0.0" / "data.tar.gz"
    target_path.write_bytes(b"")
    
    dest = tmp_path / "zerobyte_clone"
    with pytest.raises(EngineError):
        store.clone_template("test/zerobyte", str(dest))

def test_readonly_dest_dir(store, tmp_path):
    """Test cloning into a read-only directory."""
    template_dir = tmp_path / "template"
    template_dir.mkdir()
    (template_dir / "file.txt").write_text("data")
    from nptmpl.core.metadata import MetadataManager
    MetadataManager.create_default(template_dir)
    store.add_template(str(template_dir), "test/readonly")
    
    dest = tmp_path / "readonly_dst"
    dest.mkdir()
    os.chmod(dest, 0o555) # Read and execute, no write
    
    try:
        with pytest.raises(EngineError):
            store.clone_template("test/readonly", str(dest))
    finally:
        os.chmod(dest, 0o755) # Cleanup

def test_non_empty_dest_no_force(store, tmp_path):
    """Test cloning into a non-empty directory without force."""
    template_dir = tmp_path / "template"
    template_dir.mkdir()
    from nptmpl.core.metadata import MetadataManager
    MetadataManager.create_default(template_dir)
    store.add_template(str(template_dir), "test/nonempty")
    
    dest = tmp_path / "nonempty_dst"
    dest.mkdir()
    (dest / "existing.txt").write_text("i am here")
    
    with pytest.raises(DestinationNotEmptyError):
        store.clone_template("test/nonempty", str(dest))

def test_add_template_with_absolute_symlink(store, tmp_path):
    """Test adding a template that contains an absolute symlink."""
    external_file = tmp_path / "external.txt"
    external_file.write_text("external content")
    
    template_dir = tmp_path / "abs_symlink_template"
    template_dir.mkdir()
    os.symlink(external_file, template_dir / "abs_link")
    
    from nptmpl.core.metadata import MetadataManager
    from nptmpl.core.errors import EngineError
    MetadataManager.create_default(template_dir)
    
    with pytest.raises(EngineError):
        store.add_template(str(template_dir), "test/abs_link")
