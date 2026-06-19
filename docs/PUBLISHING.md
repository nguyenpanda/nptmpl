# 📦 PyPI Publishing Guide

This guide describes how to build, verify, and publish new versions of `nptmpl` to the Python Package Index (PyPI) using modern tooling (`uv`).

---

## 🛠️ Prerequisites

Ensure you have the following installed and configured:
1. **uv** - The fast, modern Python package manager and build tool (or `build` and `twine` as an alternative).
2. **PyPI Account** - A registered account on [PyPI](https://pypi.org) (and optionally [TestPyPI](https://test.pypi.org)).
3. **PyPI API Token** - Create an API token in your PyPI Account Settings.

---

## 🚀 Step-by-Step Publishing Flow

### 1. Version Bump
Before building, update the version of the package in `pyproject.toml`:

```toml
[project]
name = "nptmpl"
version = "1.1.0" # Change this to your new version
```

Make sure the version matches [Semantic Versioning rules](https://semver.org/):
- **Patch** (e.g., `1.0.1`): Backward-compatible bug fixes.
- **Minor** (e.g., `1.1.0`): Backward-compatible new features.
- **Major** (e.g., `2.0.0`): Backward-incompatible API changes.

### 2. Build the Package
Run the following command to clean the previous outputs and build the package distributions:

```bash
uv build --clear
```

This generates two files in the `dist/` directory:
- A source distribution archive (`dist/nptmpl-1.1.0.tar.gz`)
- A built wheel binary package (`dist/nptmpl-1.1.0-py3-none-any.whl`)

### 3. Verify the Build
Before uploading, you can inspect the package contents to verify that only expected files are packaged:

```bash
# To list contents of the built wheel
tar -ztvf dist/nptmpl-*.tar.gz
```

### 4. Upload to PyPI

#### Option A: Using `uv publish` (Recommended)
`uv` has a built-in publish command which is extremely fast and secure. Run:

```bash
uv publish
```

When prompted, provide your PyPI API token:
- **Username**: `__token__`
- **Password**: `pypi-...` (your API token, including the `pypi-` prefix)

You can also specify the token directly as an environment variable or flag:

```bash
uv publish --token pypi-YOUR_API_TOKEN_HERE
```

#### Option B: Using `twine`
If you prefer standard Python tooling, you can install and use `twine`:

```bash
# Install twine in a temporary environment and run it
uv run --with twine twine upload dist/*
```

Provide `__token__` and your API token password when prompted.

---

## 🧪 Testing with TestPyPI (Optional but Recommended)

To ensure everything looks correct on the index page before pushing to the real PyPI, you can publish to **TestPyPI**.

1. Create an account and an API token on [TestPyPI](https://test.pypi.org).
2. Publish using `uv publish`:
   ```bash
   uv publish --publish-url https://test.pypi.org/legacy/ --token pypi-YOUR_TEST_PYPI_TOKEN
   ```
3. Test installing the published package in a clean environment:
   ```bash
   uv pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple nptmpl
   ```

---

## 🤖 Automating with GitHub Actions

You can automate publishing to PyPI whenever you create a new release on GitHub. 

Create a file at `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  pypi-publish:
    name: Build and publish to PyPI
    runs-on: ubuntu-latest
    permissions:
      # Required for Trusted Publishing / OIDC authentication
      id-token: write
    steps:
      - name: Checkout Source Code
        uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true

      - name: Build Package
        run: uv build --clear

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
```

> 💡 **Note on Security:** The workflow above uses **Trusted Publishing (OIDC)**, which is the most secure way to publish. It does not require storing any secrets or API tokens in GitHub. You just need to configure Trusted Publishing in your PyPI project settings for your GitHub repository.
