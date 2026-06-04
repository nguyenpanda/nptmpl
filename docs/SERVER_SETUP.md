# 🚀 nptmpl Server Setup Guide

This guide explains how to deploy, configure, and secure the `nptmpl` HTTP registry server. The backend leverages FastAPI and SQLite, with robust security and performance features built-in.

---

## 🏗️ Deployment Options

### 1. Direct CLI Setup (Non-Docker)

The easiest way to start the server is via the `nptmpl serve` command. This is ideal for quick testing or simple VPS deployments.

#### From PyPI

```bash
pip install nptmpl
```

#### From Source (Recommended for Dev)

```bash
git clone https://github.com/nguyenpanda/nptmpl
cd nptmpl
pip install -e .
```

#### Start the server

```bash
nptmpl serve --host 0.0.0.0 --port 9090 --storage /var/lib/nptmpl-store
```

- **Persistence**: Ensure the `--storage` path is on a persistent volume.
- **Process Management**: We recommend using `pm2` or `systemd` (see below) to keep the process alive.

### 2. Docker Setup (Recommended)

Our Docker image is the preferred way to deploy for scalability and isolation.

#### Using Docker Run

```bash
docker run -d \
  --name nptmpl-server \
  -p 9090:9090 \
  -v nptmpl_data:/app/store \
  -e NPTMPL_SERVER_TOKEN=your-secure-api-token \
  -e NPTMPL_SESSION_SECRET=your-secure-session-secret \
  nptmpl-server
```

#### Using Docker Compose

Create a `docker-compose.yml`:

```yaml
services:
  nptmpl-server:
    image: nptmpl-server
    ports:
      - "9090:9090"
    volumes:
      - nptmpl-data:/app/store
    environment:
      - NPTMPL_SERVER_TOKEN=demo-token-123
      - NPTMPL_SESSION_SECRET=your-secure-session-secret
    restart: unless-stopped

volumes:
  nptmpl-data:
```

### 3. Production Deployment (Nginx Reverse Proxy)

In production, you should always put `nptmpl` behind a reverse proxy like Nginx to handle SSL (HTTPS) and rate limiting.

**Nginx Configuration Example**:

```nginx
server {
    listen 80;
    server_name template.example.com;

    location / {
        proxy_pass http://127.0.0.1:9090;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### 3. Systemd Service (Linux Edge Devices)

For persistent deployment on hardware like a Raspberry Pi or Intel Liva, create a service file at `/etc/systemd/system/nptmpl-server.service`:

```ini
[Unit]
Description=nptmpl Template Registry Server
After=network.target

[Service]
User=your-user
WorkingDirectory=/path/to/nptmpl
Environment="NPTMPL_SERVER_TOKEN=your-secure-api-token"
Environment="NPTMPL_SESSION_SECRET=your-secure-session-secret"
ExecStart=/path/to/nptmpl/.venv/bin/nptmpl serve --port 9090 --storage /var/lib/nptmpl-store
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## 🔐 Security & Authentication

### API Token Protection

The server uses a Simple Token Bearer authentication mechanism for `push` and `delete` operations.

1. **Set the Token**: Set the `NPTMPL_SERVER_TOKEN` environment variable on the server.
2. **Why specify this?**: If you do not specify a stable token, your API will be unprotected. Hackers could overwrite your templates or delete your entire registry. A stable, explicitly defined token also ensures that automated CI/CD pipelines can reliably push updates without needing to re-authenticate if the server restarts.

### Web Session Security

The Web UI uses cookie-based sessions for the `/admin` area.

1. **Session Secret**: For production, always set `NPTMPL_SESSION_SECRET`. If not set, the server will fallback to using the API token or a random key, which may invalidate sessions upon restart.

   **Example**: `NPTMPL_SESSION_SECRET=7f5e1a3b9c8d2f4a6e0b1c3d5f7a9b2c4e6d8f0a1b3c5e7f9a2b4c6d8e0f1a3b`

   You can generate a fresh secret using this command:

   ```bash
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```

2. **Login Portal**: Unauthenticated attempts to access `/admin` are automatically redirected to the `/login` portal.

---

### 🔑 Token vs. Session Secret

It is important to understand the different roles these two variables play:

| Feature | `NPTMPL_SERVER_TOKEN` | `NPTMPL_SESSION_SECRET` |
| :--- | :--- | :--- |
| **Target** | CLI Commands (`push`, `rm`) | Web UI (`/admin`, `/login`) |
| **Auth Type** | Bearer Token (Stateless) | Session Cookie (Stateful) |
| **Usage** | Authorizes terminal operations. | Signs & encrypts browser cookies. |
| **Persistence** | Permanent until changed. | Sessions persist until logout or restart. |

**Security Recommendation**: In production, set **both** to unique, strong strings. While the server will attempt to use your API Token as a fallback secret for sessions, keeping them separate prevents a compromise in one layer from automatically granting access to the other.

---

### Path Traversal Mitigation

All `push`, `download`, and `inspect` APIs are highly sanitized to prevent directory traversal attacks. Template groups, names, and versions are restricted using strict Regex and semantic versioning rules (`X.Y.Z`).

---

## 📂 Internal Structure & Performance

### Async SQLite Database

The server maintains a `registry.db` file inside the root of your `--storage` directory.

- **WAL Mode**: Write-Ahead Logging is enabled for maximum concurrency.
- **Optimized Queries**: Uses Common Table Expressions (CTE) and Window Functions for fast metadata retrieval.
- **Thread Pool Offloading**: All SQLite transactions are pushed to an executor thread pool via FastAPI's `run_in_threadpool`, ensuring the AsyncIO event loop never blocks.

### Analytics & Transactions

`nptmpl` tracks usage metrics to help you identify popular templates.

- **Remote Clones**: Every time a user runs `nptmpl clone` using your server's URL, the **Transaction Count** for that template increases.
- **Local Clones**: **IMPORTANT**: Clones performed from a user's local registry (e.g., `nptmpl clone my-group/my-template`) **do not** communicate with the server and therefore **do not increase the count**.
- **Downloads**: Includes direct `tar.gz` downloads via the Web UI.

### File Storage & Integrity Checks

Templates are stored using the following structure:
`<storage_path>/<group>/<name>/<version>/data.tar.gz`

All `push` operations stream files directly to disk to prevent Memory exhaustion (OOM), followed by an integrity scan capped at 1MB to prevent large-file inspection crashes.

---

## 🌐 Web Explorer

Once the server is running, visit `http://<host>:<port>/` in your browser to browse the registry, view template details, and read READMEs through the built-in Web UI.

---

## 📡 API Reference

- `GET /api/v1/templates`: List all templates.
- `GET /api/v1/templates/{group}/{name}`: Get template details.
- `GET /api/v1/templates/{group}/{name}/download`: Download the latest version.
- `POST /api/v1/templates/push`: Upload a new template version (Requires Token).
- `DELETE /api/v1/templates/{group}/{name}/{version}`: Delete a specific version (Requires Token).
