import pytest
import os
from pathlib import Path
from nptmpl.core.store import TemplateStore
from nptmpl.core.metadata import MetadataManager
from tests.data.generate_data import generate_realistic_templates

@pytest.fixture(scope="module")
def scale_setup(tmp_path_factory):
    """Generates 120+ templates and initializes a store for performance testing."""
    root = tmp_path_factory.mktemp("test_cli_scale_root")
    src_data = root / "src_data"
    src_data.mkdir()
    generate_realistic_templates(src_data)
    
    store_path = root / "store"
    store = TemplateStore(store_path)
    
    # Bulk add
    for template_dir in src_data.iterdir():
        if template_dir.is_dir():
            # template_dir.name is like "ai_huggingface-diffusers_1.0.0"
            parts = template_dir.name.split('_')
            target = f"{parts[0]}/{parts[1]}"
            store.add_template(str(template_dir), target)
            
    return {"store": store, "dst": root / "dst", "store_path": store_path}

def test_bulk_add_and_cache(scale_setup):
    store = scale_setup["store"]
    # list_templates() returns only latest versions. There are ~43 unique templates.
    results = store.list_templates()
    assert len(results) >= 40
    assert (scale_setup["store_path"] / "cache.json").exists()

def test_search_performance(scale_setup):
    store = scale_setup["store"]
    # Search for common term
    results = store.search_templates("react")
    assert len(results) > 0

def test_list_filtering(scale_setup):
    store = scale_setup["store"]
    # Filter by language
    python_templates = store.list_templates(filter_dict={"languages": "python"})
    assert len(python_templates) > 0

def test_variable_injection(scale_setup):
    store = scale_setup["store"]
    results = store.list_templates()
    assert len(results) > 0
    
    template_obj, version, _ = results[0]
    target = str(template_obj)
    
    dest = scale_setup["dst"] / "clone-vars-scale"
    store.clone_template(target, str(dest), variables={"project_name": "ScaleTest", "author_name": "Tester"})
    
    # Find README.md (some templates might have it renamed or missing, but realistic ones have it)
    readme = dest / "README.md"
    if not readme.exists():
        # Fallback to search any file for the injection if README is missing
        found = False
        for root, _, files in os.walk(dest):
            for f in files:
                content = (Path(root) / f).read_text(errors="ignore")
                if "ScaleTest" in content or "Tester" in content:
                    found = True
                    break
            if found: break
        assert found, "Variables not found in any cloned file"
    else:
        content = readme.read_text()
        assert "ScaleTest" in content or "Tester" in content

def test_doctor(scale_setup):
    store = scale_setup["store"]
    results = store.doctor()
    assert all(r[2] for r in results)

def test_init_command(scale_setup):
    init_dir = scale_setup["dst"] / "init-test-scale"
    init_dir.mkdir(exist_ok=True, parents=True)
    MetadataManager.create_default(init_dir)
    assert (init_dir / ".nptmpl").exists()
