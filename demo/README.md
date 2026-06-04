# 🚀 nptmpl Demo Environment

This folder contains everything you need to quickly spin up a `nptmpl` registry server for testing.

## ⚡ Quick Start

1. **Build and Start**:

   ```bash
   docker compose up -d
   ```

2. **Verify**:
   Visit `http://localhost:9090` in your browser. You should see the `nptmpl` Web UI.

3. **Configure your Local Client**:
   Add the following to your `~/.config/nptmpl/config.yaml`:

   ```yaml
   core:
     auth_token: "demo-token-123"
   ```

4. **Test a Push**:

   ```bash
   nptmpl init ./my-project
   nptmpl add ./my-project demo/test
   nptmpl push demo/test http://localhost:9090
   ```

## 🧹 Cleanup

```bash
docker compose down -v
```

The `-v` flag ensures that the persistent volume `nptmpl-data` is also removed.
