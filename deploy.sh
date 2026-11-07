#!/usr/bin/env bash
# ==============================================================================
# ShadowFix AI - Automated Production Deployment Script
# Target: Ubuntu / Debian / Oracle Linux (x86_64 or ARM64 Ampere A1)
# ==============================================================================

set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BOLD}${CYAN}"
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║          SHADOWFIX AI - PRODUCTION DEPLOYMENT ENGINE             ║"
echo "║          Autonomous Code Repair, CI/CD, Visual QA & Load         ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ── 1. Check Root / Sudo ──
if [ "$EUID" -ne 0 ]; then
  echo -e "${YELLOW}Notice: Re-running script with sudo...${NC}"
  exec sudo bash "$0" "$@"
fi

# ── 2. Detect Architecture (x86_64 vs ARM64) ──
ARCH=$(uname -m)
echo -e "${CYAN}==> Detected Hardware Architecture: ${BOLD}${ARCH}${NC}"

# ── 3. Install Docker & Docker Compose if missing ──
if ! command -v docker &> /dev/null; then
  echo -e "${CYAN}==> Installing Docker Engine...${NC}"
  apt-get update -y
  apt-get install -y ca-certificates curl gnupg lsb-release
  mkdir -p /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
    $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  systemctl enable --now docker
  echo -e "${GREEN}✓ Docker successfully installed.${NC}"
else
  echo -e "${GREEN}✓ Docker is already installed: $(docker --version)${NC}"
fi

# ── 4. Open Firewall Ports (80, 443, 8000) ──
echo -e "${CYAN}==> Configuring Firewall for HTTP/HTTPS Traffic...${NC}"
if command -v ufw &> /dev/null; then
  ufw allow 80/tcp
  ufw allow 443/tcp
  ufw allow 8000/tcp
  ufw reload || true
elif command -v firewall-cmd &> /dev/null; then
  firewall-cmd --zone=public --add-port=80/tcp --permanent || true
  firewall-cmd --zone=public --add-port=443/tcp --permanent || true
  firewall-cmd --zone=public --add-port=8000/tcp --permanent || true
  firewall-cmd --reload || true
fi

# ── 5. Generate Production .env if missing ──
if [ ! -f .env ]; then
  echo -e "${CYAN}==> Generating fresh production .env configuration...${NC}"
  POSTGRES_PASS=$(openssl rand -hex 16)
  ADMIN_KEY=$(openssl rand -hex 24)
  JWT_SECRET=$(openssl rand -hex 32)
  SUPERADMIN_PASS=$(openssl rand -hex 12)

  cat <<EOF > .env
# ── ShadowFix Production Environment ──
SHADOWFIX_ENV=production
ADMIN_API_KEY=${ADMIN_KEY}
JWT_SECRET=${JWT_SECRET}
SUPERADMIN_EMAIL=admin@shadowfix.ai
SUPERADMIN_PASSWORD=${SUPERADMIN_PASS}

# ── PostgreSQL Database ──
POSTGRES_DB=shadowfix_prod
POSTGRES_USER=shadowfix
POSTGRES_PASSWORD=${POSTGRES_PASS}
DATABASE_URL=postgresql://shadowfix:${POSTGRES_PASS}@shadowfix-postgres:5432/shadowfix_prod

# ── Redis Cache & Queues ──
REDIS_URL=redis://shadowfix-redis:6379/0

# ── Qdrant Vector Engine ──
QDRANT_MODE=disk

# ── LLM & AI Keys (Add your keys below) ──
GEMINI_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
E2B_API_KEY=

# ── Payment Gateways ──
RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
RAZORPAY_PAYMENT_LINK=https://razorpay.me/@shivamkumar98
PAYPAL_CLIENT_ID=
PAYPAL_CLIENT_SECRET=
PAYPAL_MODE=sandbox

# ── Figma Access Token (Optional) ──
FIGMA_ACCESS_TOKEN=
EOF

  echo -e "${GREEN}✓ Production .env created with auto-generated secure passwords.${NC}"
  echo -e "${YELLOW}SuperAdmin Login: ${BOLD}admin@shadowfix.ai${NC}"
  echo -e "${YELLOW}SuperAdmin Password: ${BOLD}${SUPERADMIN_PASS}${NC}"
else
  echo -e "${GREEN}✓ Using existing .env configuration.${NC}"
fi

# ── 6. Build & Launch Containers ──
echo -e "${CYAN}==> Building and launching Docker Compose cluster...${NC}"
docker compose -f docker-compose.prod.yml down --remove-orphans || true
docker compose -f docker-compose.prod.yml build --pull
docker compose -f docker-compose.prod.yml up -d

# ── 7. Health Check Verification ──
echo -e "${CYAN}==> Verifying system health and container status...${NC}"
sleep 10
docker compose -f docker-compose.prod.yml ps

echo -e "\n${BOLD}${GREEN}==================================================================${NC}"
echo -e "${BOLD}${GREEN}   ✓ SHADOWFIX AI PRODUCTION DEPLOYMENT IS LIVE!                  ${NC}"
echo -e "${BOLD}${GREEN}==================================================================${NC}"
echo -e "Dashboard & Web App:    ${CYAN}http://$(curl -s ifconfig.me || echo "YOUR_SERVER_IP"):8000${NC}"
echo -e "Nginx Reverse Proxy:    ${CYAN}http://$(curl -s ifconfig.me || echo "YOUR_SERVER_IP")${NC}"
echo -e "Health Check:           ${CYAN}http://localhost:8000/api/health${NC}"
echo -e "Testing Suite:          ${CYAN}http://localhost:8000/testing${NC}"
echo -e "${BOLD}Logs Command:           ${NC}docker compose -f docker-compose.prod.yml logs -f"
