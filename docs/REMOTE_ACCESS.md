# 🌐 Remote Registry Access Guide

This document explains how to access and manage the `nptmpl` remote HTTP and SSH registries securely and efficiently.

## 📍 Public URLs (LIVA Edge Device)

The current production instance is running on the LIVA mini-PC.

| Feature | URL | Description |
| :--- | :--- | :--- |
| **Search (User)** | [https://nptmpl.nguyenpanda.com/](https://nptmpl.nguyenpanda.com/) | Main browser interface for searching and browsing templates. |
| **Detail View** | `https://nptmpl.nguyenpanda.com/{group}/{name}` | View metadata and README for a specific template. |
| **Admin Panel** | [https://nptmpl.nguyenpanda.com/admin](https://nptmpl.nguyenpanda.com/admin) | Dashboard for administrators to view stats and manage entries. |
| **API Entry** | `https://nptmpl.nguyenpanda.com/api/v1/templates` | Base endpoint for programmatic CLI access, fortified with rate limiting and connection pooling. |

---

## 💻 CLI Operations

To use the remote registry from your terminal, use the `--remote` flag.

### HTTP Authentication

Sensitive operations (push/delete) require a token. Set it in your environment or via your local config:

```bash
# Set your token via environment variables
export NPTMPL_SERVER_TOKEN="<your-secure-api-token>"
```

*Note: All network requests leverage underlying HTTP connection pools ensuring blazing fast resolution over high-latency networks.*

### SSH Registry Authentication

`nptmpl` supports SSH-based remote registries via the `ssh://` protocol.
It uses strict SSH key verification policies to prevent MITM attacks. If your key is not loaded or missing, it will securely fallback to prompt for your password while ensuring host-key rejection overrides are bypassed appropriately.

### Common Commands

* **Search Remote:** `nptmpl search "" --remote https://nptmpl.nguyenpanda.com`
* **Push Template:** `nptmpl push <name> --remote https://nptmpl.nguyenpanda.com`
* **Clone Template (HTTP):** `nptmpl clone <name> --remote https://nptmpl.nguyenpanda.com`
* **Clone Template (SSH):** `nptmpl clone <name> --remote ssh://user@host:22/path/to/store`

---

## 🛠 Admin & Management

### Browser-based Management

Access the **Admin Dashboard** at `/admin`.

* **Login Portal**: You will be redirected to a secure login page. Use the credentials configured in your `server.admin` settings.
* **Session Management**: Authentication is session-based. Use the **/LOGOUT** link in the navigation bar to end your session.
* **Dashboard Features**:
  * View global registry statistics powered by thread-pool offloaded queries.
  * See all registered templates and versions.
  * Delete outdated versions and cleanly prune storage trees.

### Remote Server Management (SSH)

For system-level management (restarting service, checking logs, database backup):

```bash
# Connect to the edge device
ssh liva

# Server directory
cd /home/nguyenpanda/nguyenpanda/nptmpl

# The server database is SQLite with WAL mode enabled.
# The server storage is located at: ~/.local/share/nptmpl/db
```

## 🔒 Security Note

The `<your-secure-api-token>` is required for any write operations.
All APIs validating path inputs have been rigorously audited against path traversal attacks. Ensure your API token is kept secure and only shared with authorized users.
