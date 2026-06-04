import pytest
import yaml
from nptmpl.core.store import TemplateStore
from nptmpl.core.metadata import MetadataManager
from nptmpl.core.errors import TemplateAlreadyExistsError

@pytest.fixture
def workflow_setup(tmp_path):
    test_root = tmp_path / "test_workflow_root"
    test_root.mkdir()
    store_path = test_root / "store"
    store_path.mkdir()
    src = test_root / "src"
    src.mkdir()
    dst = test_root / "dst"
    dst.mkdir()
    config_dir = test_root / "config"
    config_dir.mkdir()
    
    store = TemplateStore(root_path=store_path)
    return {"store": store, "src": src, "dst": dst, "store_path": store_path}

def test_end_to_end_workflow(workflow_setup):
    store = workflow_setup["store"]
    src = workflow_setup["src"]
    dst = workflow_setup["dst"]
    store_path = workflow_setup["store_path"]

    # 1. Initialize a new template
    MetadataManager.create_default(src)
    assert (src / ".nptmpl").exists()
    
    # 2. Add content and multi-language metadata
    (src / "main.py").write_text("print('hello')")
    (src / "README.md").write_text("# My Template")
    (src / "temp.tmp").write_text("ignore me")
    
    with open(src / ".nptmpl", "r") as f:
        meta = yaml.safe_load(f)
    
    meta["languages"] = ["python", "markdown"]
    meta["author"] = "Workflow Tester"
    meta["tags"] = ["test", "workflow", "awesome"]
    meta["ignore"] = ["*.tmp"]
    
    with open(src / ".nptmpl", "w") as f:
        yaml.dump(meta, f)

    # 3. Add to store
    target = "test/awesome"
    store.add_template(str(src), target)
    
    # Verify storage is compressed
    version_dir = store_path / "test" / "awesome" / "1.0.0"
    assert (version_dir / "data.tar.gz").exists()
    assert (version_dir / ".nptmpl").exists()

    # 4. List and filter
    results = store.list_templates(filter_dict={"languages": "python"})
    assert len(results) == 1
    assert results[0][2].author == "Workflow Tester"

    # 5. Search
    search_results = store.search_templates("awesome")
    assert len(search_results) == 1

    # 6. Update with a new version
    meta["version"] = "1.1.0"
    meta["description"] = "Updated description"
    with open(src / ".nptmpl", "w") as f:
        yaml.dump(meta, f)
        
    store.update_template(target, str(src))
    
    # Verify latest version
    template, latest_ver, latest_meta = store.get_template_details(target)
    assert str(latest_ver) == "1.1.0"
    assert latest_meta.description == "Updated description"

    # 7. Clone the latest version
    store.clone_template(target, str(dst))
    assert (dst / "main.py").exists()
    assert not (dst / "temp.tmp").exists() # Should be ignored
    
    # 8. Test Overwrite
    # Try adding 1.1.0 again, should fail
    with pytest.raises(TemplateAlreadyExistsError):
        store.add_template(str(src), target)
        
    # Add with overwrite
    store.add_template(str(src), target, overwrite=True)
    
    # 9. Remove version
    store.remove_template(f"{target}@1.0.0")
    results_after_rm = store.list_templates(target)
    assert len(results_after_rm) == 1
    assert str(results_after_rm[0][1]) == "1.1.0"

    # 10. Remove entire template
    store.remove_template(target)
    assert not (store_path / "test" / "awesome").exists()
