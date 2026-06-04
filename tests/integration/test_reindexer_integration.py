import pytest
from pathlib import Path
import json
from nptmpl.server.db import DatabaseManager
from nptmpl.server.reindexer import ServerReindexer
from nptmpl.core.metadata import MetadataManager, TemplateMetadata

@pytest.fixture
def db_manager(tmp_path):
    db_file = tmp_path / "test.db"
    return DatabaseManager(db_file)

@pytest.fixture
def storage_path(tmp_path):
    path = tmp_path / "storage"
    path.mkdir()
    return path

def test_reindex_integration(storage_path, db_manager):
    # 1. Create a template in storage
    group, name, version = "testgroup", "testnptmpl", "1.0.0"
    version_dir = storage_path / group / name / version
    version_dir.mkdir(parents=True)
    
    meta = TemplateMetadata(
        name=name,
        version=version,
        author="Author",
        description="Desc",
        languages=["python"],
        added_date="2023-01-01"
    )
    MetadataManager.save(version_dir, meta)
    
    # 2. Run reindex
    ServerReindexer.reindex(storage_path, db_manager)
    
    # 3. Verify in DB
    nptmpl = db_manager.get_template(group, name)
    assert nptmpl is not None
    assert nptmpl["group_name"] == group
    assert nptmpl["name"] == name
    assert nptmpl["version"] == version
    
    # 4. Add another version in storage
    version2 = "1.1.0"
    version_dir2 = storage_path / group / name / version2
    version_dir2.mkdir(parents=True)
    meta2 = meta.copy_with(version=version2)
    MetadataManager.save(version_dir2, meta2)
    
    ServerReindexer.reindex(storage_path, db_manager)
    
    nptmpl = db_manager.get_template(group, name)
    assert len(nptmpl["versions"]) == 2
    
    # 5. Remove first version from storage and reindex (pruning)
    import shutil
    shutil.rmtree(version_dir)
    
    ServerReindexer.reindex(storage_path, db_manager)
    
    nptmpl = db_manager.get_template(group, name)
    assert len(nptmpl["versions"]) == 1
    assert nptmpl["versions"][0]["version"] == version2

def test_reindex_prune_entire_template(storage_path, db_manager):
    group, name, version = "group1", "nptmpl1", "1.0.0"
    version_dir = storage_path / group / name / version
    version_dir.mkdir(parents=True)
    MetadataManager.save(version_dir, TemplateMetadata(name=name, version=version, author="A", description="D", languages=["L"], added_date="now"))
    
    ServerReindexer.reindex(storage_path, db_manager)
    assert db_manager.get_template(group, name) is not None
    
    # Remove from storage
    import shutil
    shutil.rmtree(storage_path / group)
    
    ServerReindexer.reindex(storage_path, db_manager)
    assert db_manager.get_template(group, name) is None
