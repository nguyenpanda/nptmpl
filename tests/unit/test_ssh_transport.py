import pytest
import yaml
from pathlib import Path
from unittest.mock import MagicMock, patch
from nptmpl.core.remote.ssh import SshTransport
from nptmpl.core.metadata import TemplateMetadata
from nptmpl.core.errors import AuthenticationError, NetworkError, TemplateNotFoundError
import paramiko

@pytest.fixture
def mock_paramiko():
    with patch("paramiko.SSHClient") as mock_client:
        client_instance = mock_client.return_value
        sftp_instance = MagicMock()
        client_instance.open_sftp.return_value = sftp_instance
        yield mock_client, sftp_instance

@pytest.fixture
def ssh_transport():
    return SshTransport(
        host="example.com",
        user="testuser",
        remote_store_path="/remote/store",
        port=22,
        password="password"
    )

def test_ssh_connect_success(ssh_transport, mock_paramiko):
    mock_client_cls, _ = mock_paramiko
    ssh_transport._connect()
    
    mock_client_cls.return_value.connect.assert_called_once_with(
        "example.com",
        port=22,
        username="testuser",
        password="password",
        timeout=10,
        allow_agent=True,
        look_for_keys=True
    )
    assert ssh_transport.client is not None
    assert ssh_transport.sftp is not None

def test_ssh_connect_auth_failure(ssh_transport, mock_paramiko):
    mock_client_cls, _ = mock_paramiko
    mock_client_cls.return_value.connect.side_effect = paramiko.AuthenticationException("Auth failed")
    
    with pytest.raises(AuthenticationError):
        ssh_transport._connect()

def test_ssh_connect_network_error(ssh_transport, mock_paramiko):
    mock_client_cls, _ = mock_paramiko
    mock_client_cls.return_value.connect.side_effect = paramiko.SSHException("Connection refused")
    
    with pytest.raises(NetworkError):
        ssh_transport._connect()

def test_ssh_connect_not_in_known_hosts(ssh_transport, mock_paramiko):
    mock_client_cls, _ = mock_paramiko
    mock_client_cls.return_value.connect.side_effect = paramiko.SSHException("not found in known_hosts")
    
    with pytest.raises(NetworkError) as excinfo:
        ssh_transport._connect()
    assert "Manual verification required" in str(excinfo.value)

def test_fetch_metadata(ssh_transport, mock_paramiko):
    _, mock_sftp = mock_paramiko
    
    # Mocking _resolve_target indirectly by setting up sftp.listdir for the fallback
    mock_sftp.listdir.return_value = ["1.0.0"]
    
    mock_meta_dict = {
        "name": "mytemplate",
        "version": "1.0.0",
        "author": "test",
        "description": "test",
        "languages": ["python"]
    }
    
    # Mock sftp.open for .nptmpl file
    mock_file = MagicMock()
    mock_file.__enter__.return_value = mock_file
    mock_sftp.open.return_value = mock_file
    
    with patch("yaml.safe_load", return_value=mock_meta_dict):
        metadata = ssh_transport.fetch_metadata("group/name")
        
    assert metadata.name == "mytemplate"
    assert metadata.version == "1.0.0"
    mock_sftp.open.assert_called_with("/remote/store/group/name/1.0.0/.nptmpl", "r")

def test_download_tarball(ssh_transport, mock_paramiko, tmp_path):
    _, mock_sftp = mock_paramiko
    mock_sftp.listdir.return_value = ["1.0.0"]
    dest_path = tmp_path / "local.tar.gz"
    
    ssh_transport.download_tarball("group/name@1.0.0", dest_path)
    
    mock_sftp.get.assert_called_once_with("/remote/store/group/name/1.0.0/data.tar.gz", str(dest_path))

def test_push_template(ssh_transport, mock_paramiko, tmp_path):
    _, mock_sftp = mock_paramiko
    mock_sftp.stat.side_effect = FileNotFoundError() # Version doesn't exist
    
    meta = TemplateMetadata(name="n", version="1.0.0", author="a", description="d", languages=["l"])
    tarball = tmp_path / "data.tar.gz"
    tarball.write_text("data")
    
    mock_file = MagicMock()
    mock_file.__enter__.return_value = mock_file
    mock_sftp.open.return_value = mock_file

    with patch("yaml.dump") as mock_dump:
        ssh_transport.push_template("group/name@1.0.0", meta, tarball)
        mock_dump.assert_called()
    
    mock_sftp.put.assert_called_once_with(str(tarball), "/remote/store/group/name/1.0.0/data.tar.gz")

def test_push_template_conflict(ssh_transport, mock_paramiko, tmp_path):
    _, mock_sftp = mock_paramiko
    mock_sftp.stat.return_value = MagicMock() # Version exists
    
    meta = TemplateMetadata(name="n", version="1.0.0", author="a", description="d", languages=["l"])
    
    with pytest.raises(ValueError) as excinfo:
        ssh_transport.push_template("group/name@1.0.0", meta, Path("path"))
    assert "already exists" in str(excinfo.value)

def test_list_templates(ssh_transport, mock_paramiko):
    _, mock_sftp = mock_paramiko
    mock_sftp.listdir.side_effect = [
        ["group1"], # store path
        ["template1"], # group1 path
        ["1.0.0", "invalid"] # template1 path
    ]
    
    mock_file = MagicMock()
    mock_file.__enter__.return_value = mock_file
    mock_sftp.open.return_value = mock_file
    
    mock_meta = {"name": "t1", "description": "desc1"}
    with patch("yaml.safe_load", return_value=mock_meta):
        results = ssh_transport.list_templates()
    
    assert len(results) == 1
    assert results[0][0] == "group1/template1"
    assert results[0][1] == "1.0.0"

def test_get_details(ssh_transport, mock_paramiko):
    _, mock_sftp = mock_paramiko
    mock_sftp.listdir.return_value = ["1.0.0"]
    
    mock_file = MagicMock()
    mock_file.__enter__.return_value = mock_file
    mock_sftp.open.return_value = mock_file
    
    mock_meta = {"name": "t1", "version": "1.0.0"}
    with patch("yaml.safe_load", return_value=mock_meta):
        target, version, meta = ssh_transport.get_details("group/name")
        
    assert target == "group/name"
    assert version == "1.0.0"
    assert meta == mock_meta

def test_ssh_connect_generic_exception(ssh_transport, mock_paramiko):
    mock_client_cls, _ = mock_paramiko
    mock_client_cls.return_value.connect.side_effect = Exception("Generic error")
    
    with pytest.raises(NetworkError) as excinfo:
        ssh_transport._connect()
    assert "Failed to connect" in str(excinfo.value)

def test_fetch_metadata_not_found(ssh_transport, mock_paramiko):
    _, mock_sftp = mock_paramiko
    mock_sftp.listdir.return_value = ["1.0.0"]
    mock_sftp.open.side_effect = FileNotFoundError()
    
    with pytest.raises(TemplateNotFoundError):
        ssh_transport.fetch_metadata("group/name@1.0.0")

def test_download_tarball_not_found(ssh_transport, mock_paramiko, tmp_path):
    _, mock_sftp = mock_paramiko
    mock_sftp.listdir.return_value = ["1.0.0"]
    mock_sftp.get.side_effect = FileNotFoundError()
    
    with pytest.raises(TemplateNotFoundError):
        ssh_transport.download_tarball("group/name@1.0.0", tmp_path / "dest")

def test_push_template_overwrite(ssh_transport, mock_paramiko, tmp_path):
    _, mock_sftp = mock_paramiko
    mock_sftp.stat.return_value = MagicMock() # Exists
    
    meta = TemplateMetadata(name="n", version="1.0.0", author="a", description="d", languages=["l"])
    tarball = tmp_path / "data.tar.gz"
    tarball.write_text("data")
    
    mock_file = MagicMock()
    mock_file.__enter__.return_value = mock_file
    mock_sftp.open.return_value = mock_file

    with patch("yaml.dump"):
        # Should not raise because overwrite=True
        ssh_transport.push_template("group/name@1.0.0", meta, tarball, overwrite=True)
    
    mock_sftp.put.assert_called()

def test_list_templates_empty_store(ssh_transport, mock_paramiko):
    _, mock_sftp = mock_paramiko
    mock_sftp.listdir.side_effect = FileNotFoundError()
    
    results = ssh_transport.list_templates()
    assert results == []

def test_list_templates_with_query(ssh_transport, mock_paramiko):
    _, mock_sftp = mock_paramiko
    mock_sftp.listdir.side_effect = [
        ["group1"], ["template1"], ["1.0.0"]
    ]
    mock_file = MagicMock()
    mock_file.__enter__.return_value = mock_file
    mock_sftp.open.return_value = mock_file
    
    mock_meta = {"name": "t1", "description": "MATCH"}
    with patch("yaml.safe_load", return_value=mock_meta):
        results = ssh_transport.list_templates(query="match")
    
    assert len(results) == 1
    assert results[0][0] == "group1/template1"

def test_resolve_target_no_versions(ssh_transport, mock_paramiko):
    _, mock_sftp = mock_paramiko
    mock_sftp.listdir.return_value = [] # No versions
    ssh_transport._connect()
    
    with pytest.raises(TemplateNotFoundError) as excinfo:
        ssh_transport._resolve_target("group/name")
    assert "No versions found" in str(excinfo.value)

def test_resolve_target_path_not_found(ssh_transport, mock_paramiko):
    _, mock_sftp = mock_paramiko
    mock_sftp.listdir.side_effect = FileNotFoundError()
    ssh_transport._connect()
    
    with pytest.raises(TemplateNotFoundError) as excinfo:
        ssh_transport._resolve_target("group/name")
    assert "not found on remote" in str(excinfo.value)

def test_mkdir_p(ssh_transport, mock_paramiko):
    _, mock_sftp = mock_paramiko
    mock_sftp.mkdir.side_effect = [None, IOError(), None] # mixed success/failure
    ssh_transport._connect()
    
    ssh_transport._mkdir_p("/a/b/c")
    # /a, /a/b, /a/b/c
    assert mock_sftp.mkdir.call_count == 3
