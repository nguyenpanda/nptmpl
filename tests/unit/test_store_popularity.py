import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from nptmpl.core.store import TemplateStore
from nptmpl.core.metadata import TemplateMetadata, Version
from nptmpl.core.remote.base import RemoteTransport
from nptmpl.core.models import Template

@pytest.fixture
def store(tmp_path):
    store_path = tmp_path / "store"
    store_path.mkdir()
    return TemplateStore(store_path)

def test_clone_template_cached_signals_once(store, tmp_path):
    remote = MagicMock(spec=RemoteTransport)
    
    # 1. Setup a cached template
    group, name, version_str = "test", "template", "1.0.0"
    version = Version(version_str)
    template = Template(group, name, store.root_path)
    version_path = template.get_version_path(version)
    version_path.mkdir(parents=True)
    (version_path / "data.tar.gz").write_text("fake")
    (version_path / ".nptmpl").write_text("name: template\nversion: 1.0.0\nauthor: me\ndescription: desc\nlanguages: []")
    
    # 2. Mock remote metadata
    metadata = TemplateMetadata(name=name, version=version_str, author="me", description="desc", languages=["python"])
    remote.fetch_metadata.return_value = metadata
    
    # 3. Clone
    dest = tmp_path / "dest"
    with patch("nptmpl.core.engine.FileSystemEngine.decompress_and_render"):
        store.clone_template(f"{group}/{name}", str(dest), remote=remote)
    
    # 4. Verify signals
    calls = remote.fetch_metadata.call_args_list
    assert len(calls) == 2
    assert calls[1].kwargs.get("is_clone") is True

def test_clone_template_fetched_signals_once(store, tmp_path):
    remote = MagicMock(spec=RemoteTransport)
    
    # 1. Mock remote metadata (template NOT in cache)
    group, name, version_str = "test", "fetched", "1.0.0"
    metadata = TemplateMetadata(name=name, version=version_str, author="me", description="desc", languages=["python"])
    remote.fetch_metadata.return_value = metadata
    
    # 2. Mock fetch implementation
    def mock_fetch(target, dest):
        dest.write_text("fake")
        # Also need to create the .nptmpl file in the store that _fetch_from_remote usually handles
        # wait, _fetch_from_remote handles MetadataManager.save
    remote.download_tarball.side_effect = mock_fetch
    
    # 3. Clone
    dest = tmp_path / "dest"
    with patch("nptmpl.core.engine.FileSystemEngine.decompress_and_render"), \
         patch("tarfile.open"):
        store.clone_template(f"{group}/{name}", str(dest), remote=remote)
    
    # 4. Verify signals
    calls = remote.fetch_metadata.call_args_list
    
    # Check current store.py logic:
    # if not exists:
    #    _fetch_from_remote
    # else:
    #    fetch_metadata(is_clone=True)
    
    assert any(c.kwargs.get("is_clone") is True for c in calls) == False
    remote.download_tarball.assert_called_once()
