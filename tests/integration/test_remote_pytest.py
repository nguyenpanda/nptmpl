import pytest
import tarfile
from unittest.mock import patch
from nptmpl.core.store import TemplateStore
from nptmpl.core.metadata import TemplateMetadata
from nptmpl.core.remote.resolver import TargetResolver, TargetType
from nptmpl.core.remote.http import HttpTransport
from nptmpl.core.remote.ssh import SshTransport

@pytest.fixture
def remote_setup(tmp_path):
    store_path = tmp_path / "store"
    store_path.mkdir()
    store = TemplateStore(root_path=store_path)
    return {"store": store, "store_path": store_path}

def test_target_resolver_logic():
    # HTTP
    t, context, target = TargetResolver.resolve("http://example.com/api/v1/templates/web/flask")
    assert t == TargetType.HTTP
    assert target == "web/flask"
    
    # SSH
    t, context, target = TargetResolver.resolve("ssh://user@host/path/to/store/web/flask")
    assert t == TargetType.SSH
    assert target == "web/flask"

    # Local
    t, context, target = TargetResolver.resolve("web/flask")
    assert t == TargetType.LOCAL_REGISTRY

@patch("nptmpl.core.remote.http.HttpTransport")
def test_fetch_from_remote_mock(MockHttp, remote_setup):
    store = remote_setup["store"]
    store_path = remote_setup["store_path"]
    
    mock_remote = MockHttp()
    mock_remote.fetch_metadata.return_value = TemplateMetadata(
        name="remote-test",
        version="1.0.0",
        author="tester",
        description="desc",
        languages=["python"]
    )
    
    def side_effect(target, dest):
        with tarfile.open(dest, "w:gz"):
            pass
    mock_remote.download_tarball.side_effect = side_effect
    
    store._fetch_from_remote("web/flask", mock_remote)
    
    assert (store_path / "web" / "flask" / "1.0.0").exists()
    assert (store_path / "web" / "flask" / "1.0.0" / "data.tar.gz").exists()
