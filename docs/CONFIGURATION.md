# ⚙️ Configuration Guide

This guide covers all available customization options for `nptmpl`, both via `config.yaml` and environment variables.

---

## 🔍 Discovery

You can see all available configuration options directly from your terminal:

```bash
nptmpl config --show
```

This command stays in sync with the codebase and shows exactly what you can customize.

---

## 🛠️ Core Configuration

These settings control the fundamental behavior of the CLI and local registry.

| YAML Property | Env Var | Default | Description |
| :--- | :--- | :--- | :--- |
| `core.store_path` | `NPTMPL_STORE_PATH` | `~/.nptmpl/db` | Where templates and the SQLite DB are stored. |
| `core.auth_token` | `NPTMPL_AUTH_TOKEN` | N/A | Token for remote push/delete operations. |
| `core.ignore` | N/A | `[]` | Global patterns to ignore (e.g., `.DS_Store`, `.venv`). |
| `core.public_url` | N/A | N/A | The public URL shown in clone instructions. |
| `core.session_secret` | `NPTMPL_SESSION_SECRET` | Random | Key used to sign session cookies (Production recommended). |

---

## 🎨 Web UI Customization

The built-in registry server can be fully white-labeled using the `server.ui` block.

| YAML Property | Description |
| :--- | :--- |
| `server.ui.title` | Text shown in the browser tab and site header. |
| `server.ui.logo_text` | Branding text next to the panda logo. |
| `server.ui.theme_color` | Tailwind CSS color for accents (see below). |
| `server.ui.author_name` | Name shown in the "About" section. |
| `server.ui.github_url` | Link to your GitHub profile. |
| `server.ui.linkedin_url` | Link to your LinkedIn profile. |

### 🌈 Theme Colors

`nptmpl` supports any standard **Tailwind CSS** color. For best results, use the `-500` weight.

**Commonly Used Values**:

- `emerald-500` (Matrix Green) - **Highly Recommended**
- `blue-500` (Digital Blue)
- `rose-500` (Cyber Pink)
- `violet-500` (Neon Purple)
- `amber-500` (Warning Gold)
- `cyan-500` (Aqua)
- `slate-500` (Neutral Gray)
- `random` (Random color)

---

## 🔐 Server Administration

Credentials for the new **Web Login Portal** and `/admin` dashboard.

| YAML Property | Env Var | Default | Description |
| :--- | :--- | :--- | :--- |
| `server.admin.username` | `NPTMPL_ADMIN_USER` | `admin` | Login username for the Web UI. |
| `server.admin.password` | `NPTMPL_ADMIN_PASS` | `admin` | Login password for the Web UI. |

---

## 📝 Template Defaults

Default metadata used when running `nptmpl init`.

| YAML Property | Description |
| :--- | :--- |
| `defaults.author` | Your default name. |
| `defaults.email` | Your default email. |
| `defaults.license` | Default license (e.g., `MIT`). |
