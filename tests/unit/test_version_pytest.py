import tomllib
from pathlib import Path
from nptmpl import __version__ as pkg_version

def test_version_consistency():
    """Ensures version in pyproject.toml matches nptmpl.__version__."""
    pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        pyproject_data = tomllib.load(f)
    
    toml_version = pyproject_data["project"]["version"]
    assert pkg_version == toml_version, f"Version mismatch: pyproject.toml={toml_version}, nptmpl.__version__={pkg_version}"
