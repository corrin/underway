# CI/CD & Branch Protection Design

## Overview

Set up comprehensive CI, manual-trigger CD to two environments, branch protection on main, and a documented server bootstrap for Oracle Cloud.

## Environments

| Environment | Host | Trigger |
|-------------|------|---------|
| UAT | PythonAnywhere (ASGI, cheap tier) | Manual (`workflow_dispatch`) |
| Prod | Oracle Cloud (Ubuntu VM, systemd + nginx) | Manual (`workflow_dispatch`) |

## CI Enhancements

Existing workflow already covers:
- Backend: mypy strict, ruff lint/format, pytest (unit + integration)
- Frontend: eslint, vue-tsc strict, vite build

Additions:
- **Dependency caching** — Poetry cache for backend, npm cache for frontend
- **Concurrency control** — cancel in-progress runs on same PR
- **Playwright e2e placeholder** — disabled job, enabled once Phase 2 test auth bypass lands

## CD — UAT (PythonAnywhere)

Workflow: `.github/workflows/deploy-uat.yml`
Trigger: `workflow_dispatch` (manual)

Steps:
1. SSH into PythonAnywhere
2. `cd` to project directory
3. `git pull origin main`
4. `cd backend && poetry install --no-interaction`
5. `alembic upgrade head`
6. `cd ../frontend && npm ci && npm run build`
7. Restart ASGI app
8. Health check (curl app URL, expect 200)

Secrets required:
- `PA_SSH_HOST`, `PA_SSH_USER`, `PA_SSH_KEY`
- (App env vars configured directly on PythonAnywhere, not via GitHub)

## CD — Prod (Oracle Cloud)

Workflow: `.github/workflows/deploy-prod.yml`
Trigger: `workflow_dispatch` with optional `ref` input (defaults to `main`)

Steps:
1. SSH into Oracle Cloud VM
2. `cd` to project directory
3. `git pull origin <ref>`
4. `cd backend && poetry install --no-interaction`
5. `alembic upgrade head`
6. `cd ../frontend && npm ci && npm run build`
7. `sudo systemctl restart aligned`
8. `sudo systemctl reload nginx`
9. Health check (curl localhost, expect 200)

Secrets required:
- `OC_SSH_HOST`, `OC_SSH_USER`, `OC_SSH_KEY`

Environment protection:
- GitHub environment `production` with required reviewer approval before job runs

## Branch Protection (main)

Configure via `gh api`:
- Require pull requests (no direct push)
- Require status checks to pass: `backend`, `frontend`
- Require signed commits (SSH signatures)
- Allow admin override (bypass checks when needed)
- No force pushes (even for admins)
- Auto-delete head branches after merge

## Oracle Cloud Server Bootstrap

One-time setup script, documented step-by-step for repeatability.

### System packages
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y nginx certbot python3-certbot-nginx \
    python3.12 python3.12-venv python3.12-dev \
    mariadb-server mariadb-client \
    git curl build-essential
```

### Node.js 22
```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
```

### Poetry
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

### MariaDB
```bash
sudo mysql_secure_installation
sudo mysql -e "CREATE DATABASE aligned_prod CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
sudo mysql -e "CREATE USER 'aligned'@'localhost' IDENTIFIED BY '<password>';"
sudo mysql -e "GRANT ALL PRIVILEGES ON aligned_prod.* TO 'aligned'@'localhost';"
```

### Clone & configure
```bash
git clone git@github.com:corrin/aligned.git /opt/aligned
cd /opt/aligned/backend
poetry install --no-interaction
cp .env.example .env  # edit with production values
alembic upgrade head
cd ../frontend
npm ci && npm run build
```

### Systemd unit
```ini
# /etc/systemd/system/aligned.service
[Unit]
Description=Aligned FastAPI App
After=network.target mariadb.service

[Service]
User=aligned
Group=aligned
WorkingDirectory=/opt/aligned/backend
Environment="PATH=/home/aligned/.local/bin:/usr/bin"
EnvironmentFile=/opt/aligned/backend/.env
ExecStart=/home/aligned/.local/bin/poetry run uvicorn aligned.app:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable aligned
sudo systemctl start aligned
```

### Nginx
```nginx
# /etc/nginx/sites-available/aligned
server {
    listen 80;
    server_name your-domain.com;

    # Frontend static files
    location / {
        root /opt/aligned/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # API proxy
    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket support (for future chat)
    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/aligned /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

### SSL (once DNS points to the server)
```bash
sudo certbot --nginx -d your-domain.com
```

## Secrets Inventory

| Secret | Used by | Notes |
|--------|---------|-------|
| `PA_SSH_HOST` | deploy-uat | PythonAnywhere SSH hostname |
| `PA_SSH_USER` | deploy-uat | PythonAnywhere username |
| `PA_SSH_KEY` | deploy-uat | SSH private key for PythonAnywhere |
| `OC_SSH_HOST` | deploy-prod | Oracle Cloud VM public IP |
| `OC_SSH_USER` | deploy-prod | SSH user on Oracle Cloud (e.g., `aligned`) |
| `OC_SSH_KEY` | deploy-prod | SSH private key for Oracle Cloud |
