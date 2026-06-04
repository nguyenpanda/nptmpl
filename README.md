<!DOCTYPE html>
<html lang="en">
    <body>
        <p><img alt="nguyenpanda logo" src="src/nptmpl/server/static/media/png/nguyenpanda_black_bg.png" /></p>
    </body>
</html>

# 🐼 nptmpl - Distributed CLI Template Manager

[![PyPI version](https://img.shields.io/pypi/v/nptmpl.svg)](https://pypi.org/project/nptmpl/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

`nptmpl` is a high-performance, distributed CLI template manager designed for professional software engineers. It automates boilerplate generation with a robust local registry, versioning, Jinja2-powered variable injection, and seamless remote HTTP/SSH registry support.

---

## 🌐 Public Registry

We host an official template registry for the community! Browse, search, and clone templates directly from our public instance.

- **Web UI**: [https://nptmpl.nguyenpanda.com](https://nptmpl.nguyenpanda.com)
- **API Endpoint**: `https://nptmpl.nguyenpanda.com/api/v1/templates`

---

## ✨ Features

- **Distributed Registry**: Host your own private registry with a Web UI and REST API.
- **Enterprise-Grade Security**: Built-in path traversal mitigation, automatic tarball memory limits (max 1MB payload inspection), and robust `paramiko` SSH policies.
- **Blazing Fast Concurrency**: Server runs SQLite operations within thread pools using Write-Ahead Logging (WAL) to guarantee non-blocking AsyncIO loops.
- **Smart Compression**: Optimized `tar.gz` archives preserving symlinks and permissions.
- **Dynamic Injection**: Full Jinja2 support for contents and paths, automatically skipping binary files.
- **Post-Clone Hooks**: Automatically run shell commands after cloning.
- **Auto-Discovery**: Respects `.gitignore` and global patterns via `pathspec`.

---

## 🛠️ Installation & Setup

### Option 1: Install via `uv` (Fastest)

`nptmpl` uses [uv](https://github.com/astral-sh/uv) for lightning-fast installation.

```bash
uv tool install nptmpl
```

### Option 2: Install via `pip`

If you don't use `uv`, you can install standardly from PyPI:

```bash
pip install nptmpl
```

### Option 3: Install from Source

Ideal for development or contributing to `nptmpl`.

**Using `uv` (Recommended)**:

```bash
# Clone the repository
git clone https://github.com/nguyenpanda/nptmpl
cd nptmpl

# Install as a global tool in editable mode
uv tool install --editable . --force
```

**Using `pip`**:

```bash
# Clone the repository
git clone https://github.com/nguyenpanda/nptmpl
cd nptmpl

# Install in editable mode
pip install -e .
```

### 2. Enable Tab Completion (Recommended)

```bash
# Install completion helper
uv tool install argcomplete

# Add to your ~/.zshrc or ~/.bashrc
eval "$(register-python-argcomplete nptmpl)"
```

---

## 📖 Usage Guide

### 1. Initialize a Template

```bash
nptmpl init ./my-project
```

### 2. Add to Local Registry

```bash
nptmpl add ./my-project web/starter
```

### 3. Clone and Render

```bash
nptmpl clone web/starter ./new-app --var project_name="My App"
```

### 4. Remote Operations

Push to server (requires authentication token):

```bash
nptmpl push web/starter https://registry.example.com
```

Search and clone from remote:

```bash
nptmpl search fullstack --remote https://registry.example.com
nptmpl clone https://registry.example.com/api/v1/templates/web/starter ./my-app
```

---

## 🏗️ Variable Injection (Jinja2)

`nptmpl` leverages the full power of [Jinja2](https://jinja.palletsprojects.com/) to make your templates dynamic. It safely skips binary files to avoid corruption.

### 1. Define Variables

In your project's `.nptmpl` file (created via `nptmpl init`), define the variables you want to prompt for:

```yaml
variables:
  project_name: "The human-readable name of your project"
  author_name: "The main developer's name"
  enable_docker: "Set to 'true' to include Dockerfile"
```

### 2. Use in File Content

Use the standard `{{ variable_name }}` syntax inside any file in your template:

```python
# settings.py
PROJECT_NAME = "{{ project_name }}"
AUTHOR = "{{ author_name }}"
```

### 3. Use in Filenames & Directories

You can also use variables in the names of files and folders. For example:

- `src/{{ project_name }}/main.py`
- `docs/{{ author_name }}_guide.md`

### 4. Provide Variables via CLI

When cloning, use the `--var` (or `-v`) flag:

```bash
nptmpl clone web/starter ./my-new-app -v project_name="My Cool App" -v author_name="Alice"
```

If a variable is defined in `.nptmpl` but not provided via the CLI, `nptmpl` will **interactively prompt** you for its value.

---

## ⚙️ Configuration

`nptmpl` looks for `~/.config/nptmpl/config.yaml`. See the exhaustive [Configuration Guide](docs/CONFIGURATION.md) for all available options.

```yaml
core:
  store_path: "$HOME/.local/share/nptmpl/db"
  auth_token: "your-secure-api-token" # Required for pushing to server
  
defaults:
  author: "Your Name"
  email: "you@example.com"
  license: "MIT"
```

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
