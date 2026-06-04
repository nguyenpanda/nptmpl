# 🛠 LIVA Edge Server Setup Guide

Quick commands to get the `nptmpl` server running on your LIVA device.

## 1. Initial Server Prep

```bash
# Connect to server
ssh nguyenpanda@100.76.164.53

# Install uv (if not present)
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env
```

## 2. Install the Service

```bash
# Create symlink for the systemd unit (run from project root on server)
# Project root on LIVA: ~/nguyenpanda/nptmpl
sudo ln -sf $(pwd)/.config_liva/nptmpl.service /etc/systemd/system/nptmpl.service

# Reload systemd
sudo systemctl daemon-reload

# Enable and start the service
sudo systemctl enable --now nptmpl.service
```

## 3. Managing the Service

```bash
# Check status
sudo systemctl status nptmpl.service

# View logs
sudo journalctl -u nptmpl.service -f

# Restart after code changes
sudo systemctl restart nptmpl.service
```

## 4. Local Deployment

From your local machine, just run the deployment script:

```bash
chmod +x .config_liva/deploy.sh
./.config_liva/deploy.sh
```
