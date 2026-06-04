import pytest
from pathlib import Path
from nptmpl.core.store import TemplateStore
from nptmpl.core.errors import EngineError
import os

def test_store_path_to_dev_null(tmp_path):
    """Test behavior when store_path points to /dev/null."""
    # Note: On macOS/Linux, /dev/null exists and is writable, but you can't create directories in it.
    dev_null = Path("/dev/null/mystore")
    with pytest.raises(EngineError):
        TemplateStore(dev_null)

def test_store_path_no_permission(tmp_path):
    """Test behavior when store_path is not writable."""
    no_perm = tmp_path / "no_perm"
    no_perm.mkdir()
    os.chmod(no_perm, 0o444) # Read only
    
    try:
        # TemplateStore constructor checks os.access(..., os.W_OK) and raises PermissionError
        with pytest.raises(PermissionError):
            TemplateStore(no_perm)
    finally:
        os.chmod(no_perm, 0o755)

def test_store_path_is_file(tmp_path):
    """Test behavior when store_path points to an existing file."""
    file_path = tmp_path / "not_a_dir"
    file_path.write_text("i am a file")
    
    with pytest.raises(EngineError):
        TemplateStore(file_path)

def test_doctor_with_corrupted_metadata(tmp_path):
    """Test the doctor command with corrupted metadata files."""
    store_path = tmp_path / "corrupted_store"
    store = TemplateStore(store_path)
    
    # Create a valid template
    template_dir = tmp_path / "valid_template"
    template_dir.mkdir()
    (template_dir / "file.txt").write_text("data")
    from nptmpl.core.metadata import MetadataManager
    MetadataManager.create_default(template_dir)
    store.add_template(str(template_dir), "test/corrupted")
    
    # Corrupt metadata manually
    meta_file = store_path / "test" / "corrupted" / "1.0.0" / ".nptmpl"
    meta_file.write_text("not: valid: yaml: : :")
    
    results = store.doctor()
    # Find the Metadata integrity check
    integrity_check = next(r for r in results if r[0] == "Metadata integrity")
    assert integrity_check[2] is False
    assert "Corrupted: test/corrupted@1.0.0" in integrity_check[1]
