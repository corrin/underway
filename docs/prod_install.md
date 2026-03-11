# Production Server Setup

Target: Ubuntu on Oracle Cloud VM (`www.underway.today` / `152.69.173.88`)

---

## Things You Need

Gather all of these before you start. Every credential and value below is used during setup — there are no placeholders to fill in later.

### Infrastructure

| Item | Where to get it | Example |
|------|----------------|---------|
| **Server public IP** | Oracle Cloud Console after creating the VM | `152.69.173.88` |
| **Domain name** | Your registrar | `underway.today` |
| **SSH public key** | Your local machine (`~/.ssh/id_ed25519.pub`) | — |

### Secrets (generate these)

Run this on any machine to generate two random secrets:
```bash
python3 -c "import secrets; print('JWT_SECRET:', secrets.token_urlsafe(32)); print('DB_PASSWORD:', secrets.token_urlsafe(16))"
```

| Item | How |
|------|-----|
| **DB_PASSWORD** | Output from the command above |
| **JWT_SECRET** | Output from the command above |

### Google OAuth

Create credentials at [Google Cloud Console](https://console.cloud.google.com/apis/credentials):

1. Create an OAuth 2.0 Client ID (Web application)
2. Add authorized redirect URI: `https://www.underway.today/api/auth/google/callback`
3. Enable the Google Calendar API

| Item | Where |
|------|-------|
| **GOOGLE_CLIENT_ID** | Google Cloud Console > Credentials > OAuth 2.0 Client ID |
| **GOOGLE_CLIENT_SECRET** | Same page, shown once on creation |

### Microsoft 365 OAuth

Create an app registration at [Azure Portal](https://portal.azure.com/#blade/Microsoft_AAD_RegisteredApps/ApplicationsListBlade):

1. Register a new application
2. Add redirect URI: `https://www.underway.today/api/auth/o365/callback` (Web platform)
3. Create a client secret under Certificates & Secrets
4. Add API permission: `Microsoft Graph > Calendars.ReadWrite`

| Item | Where |
|------|-------|
| **O365_CLIENT_ID** | Azure Portal > App registrations > Application (client) ID |
| **O365_CLIENT_SECRET** | Azure Portal > App registrations > Certificates & secrets |

---

## Part A: External Setup (before SSH)

### 1. Oracle Cloud Console

#### Create the instance
1. Compute > Instances > Create Instance
2. Name: `underway-prod`
3. Image: Ubuntu 24.04 (or latest LTS)
4. Shape: VM.Standard.A1.Flex (ARM, free tier: up to 4 OCPU / 24GB RAM)
5. Add your SSH public key (`~/.ssh/id_ed25519.pub` or similar)
6. Create — note the **Public IP** (e.g. `152.69.173.88`)

#### Networking — open ports 80 and 443
1. Go to: Networking > Virtual Cloud Networks > your VCN > Subnets > your subnet > Security Lists > Default Security List
2. Add Ingress Rules:

| Source CIDR | Protocol | Dest Port | Description |
|-------------|----------|-----------|-------------|
| `0.0.0.0/0` | TCP | `80` | HTTP |
| `0.0.0.0/0` | TCP | `443` | HTTPS |

Port 22 (SSH) should already be open by default.

### 2. DNS (Porkbun)

Set these records at porkbun.com for `underway.today`:

| Type | Host | Value |
|------|------|-------|
| A | *(blank/root)* | `152.69.173.88` |
| A | `www` | `152.69.173.88` |

Remove any existing records for the bare domain that point elsewhere.

### 3. Verify SSH access

```bash
ssh ubuntu@www.underway.today
```

---

## Part B: Server Setup (over SSH as `ubuntu`)

### 4. Hostname

```bash
sudo hostnamectl set-hostname underway-prod
```

Edit `/etc/hosts` to include:
```
127.0.0.1 underway-prod
```

### 5. Firewall (Oracle Cloud iptables)

Oracle Cloud Ubuntu images block inbound HTTP/HTTPS by default at the OS level, even if the VCN security list allows it.

```bash
sudo iptables -I INPUT 1 -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 1 -p tcp --dport 443 -j ACCEPT
sudo apt install -y iptables-persistent
sudo netfilter-persistent save
```

### 6. System packages

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl build-essential etckeeper
sudo apt install -y python3.12 python3.12-venv python3.12-dev
sudo apt install -y nginx certbot python3-certbot-nginx
sudo apt install -y mariadb-server mariadb-client

# Node 22 via NodeSource
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs

# Poetry
curl -sSL https://install.python-poetry.org | python3 -

# Claude Code (optional, useful for server-side debugging)
curl -fsSL https://claude.ai/install.sh | bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc
```

### 7. MariaDB

```bash
sudo mysql_secure_installation
# Answer Y to unix_socket, N to change root password, Y to everything else

sudo mysql <<'SQL'
CREATE DATABASE underway_prod CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'underway'@'localhost' IDENTIFIED BY '<your DB_PASSWORD>';
GRANT ALL PRIVILEGES ON underway_prod.* TO 'underway'@'localhost';
FLUSH PRIVILEGES;
SQL
```

Use the **DB_PASSWORD** you generated in "Things You Need" above.

### 8. App user and clone

```bash
sudo useradd -m -s /bin/bash underway
sudo mkdir -p /opt/underway
sudo chown underway:underway /opt/underway

sudo su - underway
curl -sSL https://install.python-poetry.org | python3 -
git clone https://github.com/corrin/underway.git /opt/underway
```

---

## Part C: App Setup (as `underway` user)

### 9. Backend

```bash
cd /opt/underway/backend
poetry install --no-interaction
```

#### Create `.env`

Fill in every value using the credentials from "Things You Need":

```bash
cat > /opt/underway/backend/.env <<'EOF'
DATABASE_URL=mysql+aiomysql://underway:<your DB_PASSWORD>@localhost:3306/underway_prod
JWT_SECRET_KEY=<your JWT_SECRET>
BASE_URL=https://www.underway.today
GOOGLE_CLIENT_ID=<your GOOGLE_CLIENT_ID>
GOOGLE_CLIENT_SECRET=<your GOOGLE_CLIENT_SECRET>
GOOGLE_REDIRECT_URI=https://www.underway.today/api/auth/google/callback
GOOGLE_SCOPES=https://www.googleapis.com/auth/calendar
O365_CLIENT_ID=<your O365_CLIENT_ID>
O365_CLIENT_SECRET=<your O365_CLIENT_SECRET>
O365_REDIRECT_URI=https://www.underway.today/api/auth/o365/callback
O365_SCOPES=https://graph.microsoft.com/Calendars.ReadWrite
EOF
chmod 600 /opt/underway/backend/.env
```

Every `<your ...>` value should have been gathered before starting. If any are missing, go back to the "Things You Need" section.

#### Run migrations

```bash
poetry run alembic upgrade head
```

### 10. Frontend

```bash
cd /opt/underway/frontend
npm ci
npm run build
```

Then exit back to ubuntu:
```bash
exit
```

---

## Part D: Services (as `ubuntu`/root)

### 11. Systemd service

```bash
sudo tee /etc/systemd/system/underway.service <<'EOF'
[Unit]
Description=Underway FastAPI App
After=network.target mariadb.service

[Service]
User=underway
Group=underway
WorkingDirectory=/opt/underway/backend
Environment="PATH=/home/underway/.local/bin:/usr/bin"
EnvironmentFile=/opt/underway/backend/.env
ExecStart=/home/underway/.local/bin/poetry run uvicorn underway.app:create_app --factory --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable underway
sudo systemctl start underway
sudo systemctl status underway
```

### 12. Nginx

```bash
sudo tee /etc/nginx/sites-available/underway <<'EOF'
server {
    listen 80;
    server_name www.underway.today underway.today;

    location / {
        root /opt/underway/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/underway /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

### 13. HTTPS (Let's Encrypt)

```bash
sudo certbot --nginx -d www.underway.today -d underway.today
```

Certbot auto-configures Nginx for SSL and sets up auto-renewal via systemd timer.

---

## Part E: CI/CD Setup

### 14. Sudoers for deploy user

Required for the GitHub Actions deploy workflow to restart services:

```bash
sudo tee /etc/sudoers.d/underway <<'EOF'
underway ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart underway, /usr/bin/systemctl reload nginx
EOF
```

### 15. GitHub Actions deploy secrets

Generate a deploy key on the server:
```bash
sudo su - underway
ssh-keygen -t ed25519 -f ~/.ssh/underway_deploy -N ""
cat ~/.ssh/underway_deploy.pub >> ~/.ssh/authorized_keys
cat ~/.ssh/underway_deploy   # copy this private key
exit
```

In GitHub repo Settings > Secrets > Actions, add:
- `OC_SSH_HOST`: `www.underway.today` (or server IP)
- `OC_SSH_USER`: `underway`
- `OC_SSH_KEY`: the private key content from above

---

## Verify

```bash
curl https://www.underway.today/api/health
# {"status":"ok"}
```

## Manual deploy

```bash
ssh underway@www.underway.today
cd /opt/underway && git pull origin main
cd backend && poetry install && poetry run alembic upgrade head
cd ../frontend && npm ci && npm run build
sudo systemctl restart underway
```
