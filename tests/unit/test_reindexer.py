import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from nptmpl.server.reindexer import ServerReindexer
from nptmpl.core.metadata import TemplateMetadata, Version

@pytest.fixture
def mock_db():
    db = MagicMock()
    conn = MagicMock()
    db._get_connection.return_value.__enter__.return_value = conn
    return db, conn

@pytest.fixture
def storage_path(tmp_path):
    path = tmp_path / "storage"
    path.mkdir()
    return path

def test_reindex_empty_storage(storage_path, mock_db):
    db, conn = mock_db
    conn.execute.return_value.fetchall.return_value = []
    
    ServerReindexer.reindex(storage_path, db)
    
    db.add_template_version.assert_not_called()
    # Pruning might still run if db has entries
    conn.execute.assert_called()

def test_reindex_valid_template(storage_path, mock_db):
    db, conn = mock_db
    
    # Setup directory structure: group/name/version
    group_dir = storage_path / "mygroup"
    group_dir.mkdir()
    name_dir = group_dir / "mytemplate"
    name_dir.mkdir()
    version_dir = name_dir / "1.0.0"
    version_dir.mkdir()
    
    metadata_file = version_dir / ".nptmpl"
    metadata_file.write_text("dummy metadata")
    
    tarball_file = version_dir / "data.tar.gz"
    tarball_file.write_text("dummy tarball")
    
    mock_metadata = TemplateMetadata(
        name="mytemplate",
        version="1.0.0",
        author="test",
        description="test desc",
        languages=["python"]
    )
    
    conn.execute.return_value.fetchall.return_value = []

    with patch("nptmpl.core.metadata.MetadataManager.load", return_value=mock_metadata), \
         patch("nptmpl.server.inspector.TarballInspector.extract_readme", return_value="README content"):
        
        ServerReindexer.reindex(storage_path, db)
        
        expected_meta = mock_metadata.to_dict()
        expected_meta["target"] = "mygroup/mytemplate"
        
        db.add_template_version.assert_called_once_with(expected_meta, "README content")

def test_reindex_invalid_version(storage_path, mock_db):
    db, conn = mock_db
    
    group_dir = storage_path / "mygroup"
    group_dir.mkdir()
    name_dir = group_dir / "mytemplate"
    name_dir.mkdir()
    version_dir = name_dir / "invalid-version"
    version_dir.mkdir()
    
    conn.execute.return_value.fetchall.return_value = []
    
    ServerReindexer.reindex(storage_path, db)
    
    db.add_template_version.assert_not_called()

def test_reindex_pruning(storage_path, mock_db):
    db, conn = mock_db
    
    # db has an entry that is NOT in storage
    conn.execute.return_value.fetchall.return_value = [
        {"group_name": "oldgroup", "name": "oldtemplate", "version": "2.0.0"}
    ]
    
    ServerReindexer.reindex(storage_path, db)
    
    db.delete_version.assert_called_once_with("oldgroup", "oldtemplate", "2.0.0")

def test_reindex_skip_on_error(storage_path, mock_db):
    db, conn = mock_db
    
    group_dir = storage_path / "mygroup"
    group_dir.mkdir()
    name_dir = group_dir / "mytemplate"
    name_dir.mkdir()
    version_dir = name_dir / "1.0.0"
    version_dir.mkdir()
    (version_dir / ".nptmpl").write_text("dummy")
    
    conn.execute.return_value.fetchall.return_value = []

    with patch("nptmpl.core.metadata.MetadataManager.load", side_effect=Exception("Load error")):
        ServerReindexer.reindex(storage_path, db)
        db.add_template_version.assert_not_called()

def test_reindex_skip_non_dir_and_hidden(storage_path, mock_db):
    db, conn = mock_db
    conn.execute.return_value.fetchall.return_value = []
    
    (storage_path / ".hidden").mkdir()
    (storage_path / "not_a_dir").write_text("file")
    
    group_dir = storage_path / "mygroup"
    group_dir.mkdir()
    (group_dir / "not_a_dir_name").write_text("file")
    
    name_dir = group_dir / "mytemplate"
    name_dir.mkdir()
    (name_dir / "not_a_dir_version").write_text("file")
    
    ServerReindexer.reindex(storage_path, db)
    db.add_template_version.assert_not_called()

def test_reindex_missing_metadata(storage_path, mock_db):
    db, conn = mock_db
    conn.execute.return_value.fetchall.return_value = []
    
    group_dir = storage_path / "mygroup"
    group_dir.mkdir()
    name_dir = group_dir / "mytemplate"
    name_dir.mkdir()
    version_dir = name_dir / "1.0.0"
    version_dir.mkdir()
    # NO metadata file
    
    ServerReindexer.reindex(storage_path, db)
    db.add_template_version.assert_not_called()

def test_reindex_prune_error(storage_path, mock_db):
    db, conn = mock_db
    # Mock _get_connection to succeed but execute to fail for pruning
    conn.execute.side_effect = Exception("Prune DB error")
    
    # This should not raise but log an error
    ServerReindexer.reindex(storage_path, db)
    # The first count loop should still work if there were templates, 
    # but here we just want to see it handles the exception in pruning.
