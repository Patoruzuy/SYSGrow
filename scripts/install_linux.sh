#!/usr/bin/env bash
# ───────────────────────────────────────────────────────────────────
# SYSGrow Smart Agriculture — Linux / Raspberry Pi Installer
# ───────────────────────────────────────────────────────────────────
# Usage:
#   chmod +x scripts/install_linux.sh
#   sudo ./scripts/install_linux.sh
#
# What it does:
#   1. Creates a 'sysgrow' system user
#   2. Copies the project to /opt/sysgrow
#   3. Creates a Python venv and installs dependencies
#   4. Initializes the SQLite database
#   5. Installs and enables the systemd service
# ───────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Colours ──
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}ℹ${NC}  $*"; }
ok()    { echo -e "${GREEN}✅${NC} $*"; }
warn()  { echo -e "${YELLOW}⚠${NC}  $*"; }
fail()  { echo -e "${RED}❌${NC} $*"; exit 1; }

# ── Must be root ──
[[ $EUID -eq 0 ]] || fail "This script must be run as root (sudo)."

INSTALL_DIR="/opt/sysgrow"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${INSTALL_DIR}/.venv"

echo ""
echo -e "${GREEN}🌱  SYSGrow Smart Agriculture — Installer${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── Step 1: Detect platform ──────────────────────────────────────
IS_PI=false
if grep -qi "raspberry\|BCM2" /proc/cpuinfo 2>/dev/null; then
    IS_PI=true
    info "Raspberry Pi detected"
elif grep -qi "aarch64\|armv7" /proc/cpuinfo 2>/dev/null; then
    IS_PI=true
    info "ARM board detected (assuming Pi-compatible)"
fi

# ── Step 2: Install system dependencies ──────────────────────────
info "Installing system packages..."
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip curl > /dev/null 2>&1
ok "System packages ready"

# ── Step 3: Create system user ───────────────────────────────────
if id "sysgrow" &>/dev/null; then
    info "User 'sysgrow' already exists"
else
    useradd --system --home-dir "${INSTALL_DIR}" --shell /usr/sbin/nologin sysgrow
    ok "Created system user 'sysgrow'"
fi

# ── Step 4: Copy project to /opt/sysgrow ─────────────────────────
info "Copying project to ${INSTALL_DIR}..."
mkdir -p "${INSTALL_DIR}"

rsync -a --exclude='.venv' --exclude='__pycache__' --exclude='.git' \
         --exclude='tests' --exclude='docs' --exclude='reports' \
         --exclude='*.pyc' --exclude='.pytest_cache' \
         "${REPO_DIR}/" "${INSTALL_DIR}/"
ok "Project files copied"

# ── Step 5: Create venv and install dependencies ─────────────────
info "Setting up Python virtual environment..."
python3 -m venv "${VENV_DIR}"
source "${VENV_DIR}/bin/activate"

info "Installing core dependencies..."
pip install --quiet --upgrade pip setuptools wheel
pip install --quiet -r "${INSTALL_DIR}/requirements-essential.txt"

# Platform-specific extras
EXTRAS=""
if $IS_PI; then
    info "Installing Raspberry Pi extras (GPIO, Zigbee, systemd)..."
    EXTRAS=".[zigbee,raspberry,linux]"
else
    info "Installing Linux extras (Zigbee, systemd)..."
    EXTRAS=".[zigbee,linux]"
fi

# Install extras — tolerate failures for hardware-specific packages
pip install --quiet "${EXTRAS}" 2>/dev/null || warn "Some optional extras failed to install (non-critical)"

ok "Python dependencies installed"

# ── Step 6: Create writable directories ──────────────────────────
mkdir -p "${INSTALL_DIR}/database" "${INSTALL_DIR}/logs" "${INSTALL_DIR}/var" "${INSTALL_DIR}/data"
chown -R sysgrow:sysgrow "${INSTALL_DIR}"
ok "Directory permissions set"

# ── Step 7: Initialize database ──────────────────────────────────
info "Initializing database..."
sudo -u sysgrow "${VENV_DIR}/bin/python" -c "
from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler
db = SQLiteDatabaseHandler('${INSTALL_DIR}/database/sysgrow.db')
db.initialize_database()
print('Database initialized')
" 2>/dev/null || warn "Database may already exist (skipped)"
ok "Database ready"

# ── Step 8: Create ops.env from example ──────────────────────────
if [ ! -f "${INSTALL_DIR}/ops.env" ]; then
    if [ -f "${INSTALL_DIR}/ops.env.example" ]; then
        cp "${INSTALL_DIR}/ops.env.example" "${INSTALL_DIR}/ops.env"
        info "Created ops.env from example — edit to customize"
    fi
fi

# ── Step 9: Install systemd service ──────────────────────────────
info "Installing systemd service..."
cp "${INSTALL_DIR}/deployment/sysgrow.service" /etc/systemd/system/sysgrow.service
systemctl daemon-reload
systemctl enable sysgrow
ok "Systemd service installed and enabled"

# ── Done ─────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}🌱  Installation complete!${NC}"
echo ""
echo "  Next steps:"
echo ""
echo "  1. Edit configuration:"
echo "     sudo nano ${INSTALL_DIR}/ops.env"
echo ""
echo "  2. Start the service:"
echo "     sudo systemctl start sysgrow"
echo ""
echo "  3. Check status:"
echo "     sudo systemctl status sysgrow"
echo "     journalctl -u sysgrow -f"
echo ""
echo "  4. Open in browser:"
echo "     http://$(hostname -I | awk '{print $1}'):8000"
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
