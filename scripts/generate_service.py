def generate_systemd_service():
    service_content = """[Unit]
Description=NPTMPL Registry Server
After=network.target

[Service]
User=nguyenpanda
WorkingDirectory="$HOME/.nptmpl"
Environment="NPTMPL_SERVER_TOKEN=<your-secure-api-token>"
ExecStart=$HOME/nguyenpanda/.nptmpl/.venv/bin/python -m nptmpl.cli serve --port 9090 --host 0.0.0.0
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
"""
    
    with open("nptmpl.service", "w") as f:
        f.write(service_content)
    
    print("✅ nptmpl.service file generated locally.")

if __name__ == "__main__":
    generate_systemd_service()
