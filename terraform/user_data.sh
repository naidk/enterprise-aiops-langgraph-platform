#!/bin/bash
# Enterprise AIOps Platform — EC2 Bootstrap Script
# Runs automatically on first boot

set -e
exec > /var/log/aiops-setup.log 2>&1
echo "=== AIOps Platform Setup Started: $(date) ==="

# ── 1. System Update ──────────────────────────────────────────────────────────
apt-get update -y
apt-get upgrade -y
apt-get install -y git python3.11 python3.11-venv python3-pip screen curl

# ── 2. Clone Repository ───────────────────────────────────────────────────────
cd /home/ubuntu
git clone ${github_repo} aiops-platform
cd aiops-platform

# ── 3. Python Virtual Environment ─────────────────────────────────────────────
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# ── 4. Create .env File ───────────────────────────────────────────────────────
cat > .env << 'ENVEOF'
APP_NAME=Enterprise AIOps Platform
ENVIRONMENT=production
LLM_PROVIDER=${llm_provider}
GROQ_API_KEY=${groq_api_key}
DRY_RUN_MODE=true
CLOUD_PROVIDER=local
LOG_LEVEL=INFO
AUTO_REMEDIATION_ENABLED=true
MAX_REMEDIATION_RETRIES=3
ENVEOF

# ── 5. Create Storage Directories ─────────────────────────────────────────────
mkdir -p storage logs
chmod 755 storage logs

# ── 6. Create systemd service for FastAPI ─────────────────────────────────────
cat > /etc/systemd/system/aiops-api.service << 'SERVICEEOF'
[Unit]
Description=Enterprise AIOps FastAPI Server
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/aiops-platform
Environment=PATH=/home/ubuntu/aiops-platform/venv/bin
ExecStart=/home/ubuntu/aiops-platform/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICEEOF

# ── 7. Create systemd service for Streamlit ───────────────────────────────────
cat > /etc/systemd/system/aiops-dashboard.service << 'SERVICEEOF'
[Unit]
Description=Enterprise AIOps Streamlit Dashboard
After=network.target aiops-api.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/aiops-platform
Environment=PATH=/home/ubuntu/aiops-platform/venv/bin
ExecStart=/home/ubuntu/aiops-platform/venv/bin/streamlit run dashboard/streamlit_app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICEEOF

# ── 8. Enable and Start Services ──────────────────────────────────────────────
systemctl daemon-reload
systemctl enable aiops-api
systemctl enable aiops-dashboard
systemctl start aiops-api
systemctl start aiops-dashboard

chown -R ubuntu:ubuntu /home/ubuntu/aiops-platform

echo "=== AIOps Platform Setup Complete: $(date) ==="
echo "FastAPI  → http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8000"
echo "Dashboard → http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8501"
