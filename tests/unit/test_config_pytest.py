import pytest
import os
import yaml
from pathlib import Path
from nptmpl.core.config import ConfigManager, ConfigError

@pytest.fixture
def config_setup(tmp_path):
    test_root = tmp_path / "test_config_root"
    test_root.mkdir()
    config_dir = test_root / ".config" / "nptmpl"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.yaml"
    
    # Save original method
    original_get_locations = ConfigManager._get_config_locations
    # Patch it
    ConfigManager._get_config_locations = lambda self: [config_file]
    
    # Clear env vars
    orig_env = os.environ.copy()
    if "NPTMPL_STORE_PATH" in os.environ:
        del os.environ["NPTMPL_STORE_PATH"]
    if "XDG_CONFIG_HOME" in os.environ:
        del os.environ["XDG_CONFIG_HOME"]
    
    yield {"root": test_root, "file": config_file, "orig_method": original_get_locations}
    
    # Restore
    ConfigManager._get_config_locations = original_get_locations
    os.environ.clear()
    os.environ.update(orig_env)

def test_default_fallback(config_setup):
    manager = ConfigManager()
    assert manager.get_store_path() == ConfigManager.DEFAULT_STORE_PATH.resolve()

def test_env_var_precedence(config_setup):
    custom_path = config_setup["root"] / "env_store"
    os.environ["NPTMPL_STORE_PATH"] = str(custom_path.absolute())
    
    manager = ConfigManager()
    assert manager.get_store_path() == custom_path.resolve()

def test_config_file_resolution(config_setup):
    custom_path = config_setup["root"] / "config_store"
    with open(config_setup["file"], "w") as f:
        yaml.dump({"core": {"store_path": str(custom_path.absolute())}}, f)
        
    manager = ConfigManager()
    assert manager.get_store_path() == custom_path.resolve()

def test_path_expansion(config_setup):
    with open(config_setup["file"], "w") as f:
        yaml.dump({"core": {"store_path": "~/my_templates"}}, f)
        
    manager = ConfigManager()
    resolved = manager.get_store_path()
    assert resolved == (Path.home() / "my_templates").resolve()

def test_reject_relative_path(config_setup):
    with open(config_setup["file"], "w") as f:
        yaml.dump({"core": {"store_path": "./relative/path"}}, f)
        
    manager = ConfigManager()
    with pytest.raises(ConfigError, match="Relative path detected"):
        manager.get_store_path()

def test_malformed_yaml(config_setup):
    with open(config_setup["file"], "w") as f:
        f.write("core: { store_path: [unclosed list")
        
    with pytest.raises(ConfigError, match="Malformed config file"):
        ConfigManager()

def test_env_var_expansion_in_config(config_setup):
    os.environ["MY_CUSTOM_VAR"] = "/tmp/custom_templates"
    with open(config_setup["file"], "w") as f:
        yaml.dump({"core": {"store_path": "$MY_CUSTOM_VAR/subdir"}}, f)
        
    manager = ConfigManager()
    resolved = manager.get_store_path()
    assert resolved == Path("/tmp/custom_templates/subdir").resolve()

def test_xdg_config_home(config_setup):
    # Restore real method for this test
    ConfigManager._get_config_locations = config_setup["orig_method"]
    
    custom_xdg = config_setup["root"] / "custom_xdg"
    custom_xdg.mkdir()
    os.environ["XDG_CONFIG_HOME"] = str(custom_xdg.absolute())
    
    xdg_config_dir = custom_xdg / "nptmpl"
    xdg_config_dir.mkdir()
    xdg_config_file = xdg_config_dir / "config.yaml"
    
    custom_path = config_setup["root"] / "xdg_store"
    with open(xdg_config_file, "w") as f:
        yaml.dump({"core": {"store_path": str(custom_path.absolute())}}, f)
        
    manager = ConfigManager()
    assert manager.get_store_path() == custom_path.resolve()
