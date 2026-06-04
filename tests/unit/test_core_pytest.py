import pytest
import yaml
from nptmpl.core.metadata import Version, MetadataManager
from nptmpl.core.store import TemplateStore
from nptmpl.core.errors import ValidationError

def test_version_comparison():
    v1 = Version("1.0.0")
    v2 = Version("1.1.0")
    v3 = Version("1.1.1")
    v4 = Version("2.0.0")
    
    assert v1 < v2
    assert v2 < v3
    assert v3 < v4
    assert v2 > v1
    assert Version("1.0.0") == Version("1.0.0")
    assert v2 >= v1
    assert v1 <= v2

def test_invalid_version():
    with pytest.raises(ValidationError):
        Version("1.0")
    with pytest.raises(ValidationError):
        Version("v1.0.0")

def test_parse_target(tmp_path):
    store = TemplateStore(root_path=tmp_path / "test_store")
    assert store._parse_target("latex/diary") == ("latex", "diary", None)
    assert store._parse_target("latex/diary@1.0.0") == ("latex", "diary", "1.0.0")
    
    with pytest.raises(ValidationError):
        store._parse_target("invalid_target")
    with pytest.raises(ValidationError):
        store._parse_target("group/name@1.0.0@latest")

@pytest.fixture
def metadata_dir(tmp_path):
    d = tmp_path / "test_metadata_dir"
    d.mkdir()
    return d

def test_load_metadata(metadata_dir):
    data = {
        "version": "1.0.0",
        "author": "Test Author",
        "description": "Test Description",
        "languages": ["python"]
    }
    with open(metadata_dir / ".nptmpl", "w") as f:
        yaml.dump(data, f)
        
    metadata = MetadataManager.load(metadata_dir)
    assert metadata.version == "1.0.0"
    assert metadata.author == "Test Author"
    assert metadata.description == "Test Description"
    assert metadata.languages == ["python"]

def test_create_default(metadata_dir):
    init_dir = metadata_dir / "init_test"
    init_dir.mkdir()
    MetadataManager.create_default(init_dir)
    
    metadata_file = init_dir / ".nptmpl"
    assert metadata_file.exists()
    
    with open(metadata_file, "r") as f:
        data = yaml.safe_load(f)
        assert data["name"] == "init_test"
        assert data["version"] == "1.0.0"
        assert data["languages"] == ["python"]
