#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="/opt/netledger"
REPO_URL="https://github.com/2maxtech/NetLedger.git"

echo ""
echo "  ╔═══════════════════════════════════════╗"
echo "  ║    NetLedger On-Premise Installer      ║"
echo "  ║    ISP Billing Made Simple             ║"
echo "  ╚═══════════════════════════════════════╝"
echo ""

if [ "$EUID" -ne 0 ]; then
  echo "Error: Please run as root (sudo bash install-onpremise.sh)"
  exit 1
fi

if [ -f /etc/os-release ]; then
  . /etc/os-release
  echo "Detected OS: $PRETTY_NAME"
fi

if ! command -v docker &> /dev/null; then
  echo "Installing Docker..."
  curl -fsSL https://get.docker.com | bash
  systemctl enable docker
  systemctl start docker
  echo "Docker installed."
else
  echo "Docker already installed: $(docker --version)"
fi

if ! docker compose version &> /dev/null; then
  echo "Installing Docker Compose plugin..."
  apt-get update -qq && apt-get install -y -qq docker-compose-plugin
  echo "Docker Compose installed."
else
  echo "Docker Compose already installed: $(docker compose version)"
fi

echo "Creating $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

if [ -d "$INSTALL_DIR/.git" ]; then
  echo "Updating existing installation..."
  git pull --ff-only
else
  echo "Downloading NetLedger..."
  git clone "$REPO_URL" "$INSTALL_DIR"
fi

if [ ! -f "$INSTALL_DIR/.env" ]; then
  echo "Generating configuration..."
  DB_PASS=$(openssl rand -hex 16)
  SECRET=$(openssl rand -hex 32)
  cp "$INSTALL_DIR/.env.onpremise.example" "$INSTALL_DIR/.env"
  sed -i "s/DB_PASSWORD=CHANGE_ME/DB_PASSWORD=$DB_PASS/" "$INSTALL_DIR/.env"
  sed -i "s/SECRET_KEY=CHANGE_ME/SECRET_KEY=$SECRET/" "$INSTALL_DIR/.env"
  echo "Generated .env with secure random passwords."
else
  echo "Existing .env found, keeping it."
fi

echo ""
echo "Building and starting NetLedger..."
docker compose -f docker-compose.onpremise.yml up -d --build

echo "Waiting for services to start..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:${HTTP_PORT:-80}/health > /dev/null 2>&1; then
    break
  fi
  sleep 2
done

SERVER_IP=$(hostname -I | awk '{print $1}')

echo ""
echo "  ╔═══════════════════════════════════════╗"
echo "  ║    NetLedger is ready!                 ║"
echo "  ╠═══════════════════════════════════════╣"
echo "  ║                                       ║"
echo "  ║  Open in your browser:                ║"
echo "  ║  http://$SERVER_IP                    ║"
echo "  ║                                       ║"
echo "  ║  Complete the setup wizard to create   ║"
echo "  ║  your admin account.                   ║"
echo "  ║                                       ║"
echo "  ╚═══════════════════════════════════════╝"
echo ""
echo "To update later: cd $INSTALL_DIR && git pull && docker compose -f docker-compose.onpremise.yml up -d --build"
