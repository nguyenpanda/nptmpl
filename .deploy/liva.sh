#!/bin/bash

SERVER_USER="nguyenpanda"
SERVER_HOST="100.76.164.53"
REMOTE_DIR="/home/$SERVER_USER/nguyenpanda/nptmpl"

echo "🚀 Deploying nptmpl to LIVA edge device..."

echo "📦 Syncing files..."
rsync -avz --delete \
    --exclude ".git/" \
    --exclude ".venv/" \
    --exclude "__pycache__/" \
    --exclude "*.pyc" \
    --exclude ".pytest_cache/" \
    --exclude ".vscode/" \
    --exclude ".idea/" \
    --exclude ".note/" \
    --exclude "tests/" \
    --exclude "dist/" \
    --exclude "nptmpl_demo_env/" \
    --exclude "synthetic_templates/" \
    --exclude "realistic_templates/" \
    --exclude ".ruff_cache/" \
    ./ "$SERVER_USER@$SERVER_HOST:$REMOTE_DIR"

echo "🔧 Installing dependencies and restarting service..."
ssh -t "$SERVER_USER@$SERVER_HOST" "
    export PATH=\$HOME/.local/bin:\$PATH && \
    cd $REMOTE_DIR && \
    if ! command -v uv &> /dev/null; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
    fi && \
    uv tool install --editable . --force && \
    echo \"🔄 Restarting nptmpl.service...\" && \
    sudo systemctl restart nptmpl.service
"

echo "✅ Deployment complete!"
