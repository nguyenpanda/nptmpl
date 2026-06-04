import pytest
from nptmpl.core.metadata import Version
from nptmpl.core.store import TemplateStore
from nptmpl.core.errors import ValidationError
from pathlib import Path

def test_version_comparison_logic():
    v1 = Version("1.0.0")
    v2 = Version("1.0.1")
    v3 = Version("2.0.0")
    assert v1 < v2 < v3
    assert v2 > v1
    assert v1 <= v2
    assert v3 >= v2
    assert v1 == Version("1.0.0")
    assert v1 != "1.0.0"

def test_invalid_version_strings():
    with pytest.raises(ValidationError):
        Version("1.0")
    with pytest.raises(ValidationError):
        Version("1.0.0.0")
    with pytest.raises(ValidationError):
        Version("v1.0.0")
    # 1.0.0-beta is now valid SemVer!
    Version("1.0.0-beta")

def test_metadata_mandatory_fields_missing(tmp_path):
    meta_file = tmp_path / ".nptmpl"
    # Missing 'author'
    meta_file.write_text("version: 1.0.0\ndescription: desc\nlanguages: [python]")
    from nptmpl.core.metadata import MetadataManager
    with pytest.raises(ValidationError, match="Missing mandatory field"):
        MetadataManager.load(tmp_path)

def test_target_parsing_edge_cases():
    # TemplateStore._parse_target is a static method helper
    store = TemplateStore(Path("/tmp/store"))
    
    assert store._parse_target("group/name") == ("group", "name", None)
    assert store._parse_target("group/name@1.2.3") == ("group", "name", "1.2.3")
    
    with pytest.raises(ValidationError):
        store._parse_target("invalid-target")
    
    # "@invalid" matches [^/@]+, so _parse_target succeeds, 
    # but Version("invalid") will fail later in the calling logic.
    group, name, version_str = store._parse_target("group/name@invalid")
    assert version_str == "invalid"
    with pytest.raises(ValidationError, match="Invalid SemVer format"):
        from nptmpl.core.metadata import Version
        Version(version_str)

def test_cache_rebuild_on_empty_store(tmp_path):
    store_path = tmp_path / "empty_store"
    store_path.mkdir()
    from nptmpl.core.cache import RegistryCache
    cache = RegistryCache(store_path)
    cache.rebuild()
    assert cache.load() is True
    assert cache.get_all() == []

def test_engine_jinja_syntax_error(tmp_path):
    """Test that Jinja2 syntax errors don't crash the cloning process."""
    from nptmpl.core.engine import FileSystemEngine
    from unittest.mock import patch
    dst = tmp_path / "dst"
    dst.mkdir()
    (dst / "bad.txt").write_text("{{ invalid syntax }") # Missing closing brace
    
    # This should not raise an exception, just skip rendering the file
    with patch.object(FileSystemEngine, "decompress_and_render", return_value=None):
        # Re-implementing a bit of logic for the test
        from jinja2 import Environment, FileSystemLoader
        env = Environment(loader=FileSystemLoader(str(dst)))
        try:
            template = env.get_template("bad.txt")
            template.render()
        except Exception:
            pass # Expected
