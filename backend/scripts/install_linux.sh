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
#   4. Provisions Mosquitto for LAN MQTT access
#   5. Initializes the SQLite database
#   6. Installs, enables, and starts the systemd service
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
OPS_ENV_FILE="${INSTALL_DIR}/ops.env"
MOSQUITTO_CONF_FILE="/etc/mosquitto/conf.d/sysgrow.conf"

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

generate_secret() {
    python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
}

set_env_value() {
    local file="$1"
    local key="$2"
    local value="$3"

    python3 - "$file" "$key" "$value" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
key = sys.argv[2]
value = sys.argv[3]
prefix = f"{key}="

lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
replaced = False
updated: list[str] = []

for line in lines:
    if line.startswith(prefix):
        updated.append(prefix + value)
        replaced = True
    else:
        updated.append(line)

if not replaced:
    if updated and updated[-1] != "":
        updated.append("")
    updated.append(prefix + value)

path.write_text("\n".join(updated) + "\n", encoding="utf-8")
PY
}

maybe_enable_rpi_interfaces() {
    if ! $IS_PI; then
        return
    fi

    if ! command -v raspi-config >/dev/null 2>&1; then
        warn "raspi-config not available; skipping automatic I2C/SPI enablement"
        return
    fi

    info "Enabling Raspberry Pi hardware interfaces (I2C, SPI)..."
    raspi-config nonint do_i2c 0 >/dev/null 2>&1 || warn "Could not enable I2C automatically"
    raspi-config nonint do_spi 0 >/dev/null 2>&1 || warn "Could not enable SPI automatically"
    ok "Raspberry Pi interfaces configured"
}

configure_mosquitto() {
    info "Configuring Mosquitto for local-network device access..."
    install -d /etc/mosquitto/conf.d
    cat > "${MOSQUITTO_CONF_FILE}" <<'EOF'
# SYSGrow local MQTT broker configuration
# Allows ESP32 and Zigbee bridges on the local network to reach the Pi broker.
# Do not expose this broker directly to the internet without adding auth/TLS.
listener 1883
allow_anonymous true
EOF
    systemctl enable --now mosquitto >/dev/null 2>&1 || fail "Failed to enable/start mosquitto"
    ok "Mosquitto installed and running"
}

ensure_ops_env() {
    info "Preparing runtime environment file..."

    if [ ! -f "${OPS_ENV_FILE}" ]; then
        if [ -f "${INSTALL_DIR}/ops.env.example" ]; then
            cp "${INSTALL_DIR}/ops.env.example" "${OPS_ENV_FILE}"
        else
            touch "${OPS_ENV_FILE}"
        fi

        set_env_value "${OPS_ENV_FILE}" "SYSGROW_ENV" "production"
        set_env_value "${OPS_ENV_FILE}" "SYSGROW_DEBUG" "False"
        set_env_value "${OPS_ENV_FILE}" "SYSGROW_LOG_LEVEL" "WARNING"
        set_env_value "${OPS_ENV_FILE}" "SYSGROW_DATABASE_PATH" "database/sysgrow.db"
        set_env_value "${OPS_ENV_FILE}" "SYSGROW_ENABLE_MQTT" "True"
        set_env_value "${OPS_ENV_FILE}" "SYSGROW_MQTT_HOST" "localhost"
        set_env_value "${OPS_ENV_FILE}" "SYSGROW_MQTT_PORT" "1883"
        set_env_value "${OPS_ENV_FILE}" "SYSGROW_SECRET_KEY" "$(generate_secret)"
        info "Created production-ready ops.env"
    else
        info "Using existing ops.env"

        if ! grep -Eq '^SYSGROW_SECRET_KEY=' "${OPS_ENV_FILE}"; then
            set_env_value "${OPS_ENV_FILE}" "SYSGROW_SECRET_KEY" "$(generate_secret)"
            info "Added missing SYSGROW_SECRET_KEY"
        fi
        if ! grep -Eq '^SYSGROW_ENV=' "${OPS_ENV_FILE}"; then
            set_env_value "${OPS_ENV_FILE}" "SYSGROW_ENV" "production"
            info "Defaulted SYSGROW_ENV to production"
        elif grep -Eq '^SYSGROW_ENV=development$' "${OPS_ENV_FILE}"; then
            warn "Existing ops.env keeps SYSGROW_ENV=development; change it to production for deployment"
        fi
        if ! grep -Eq '^SYSGROW_DEBUG=' "${OPS_ENV_FILE}"; then
            set_env_value "${OPS_ENV_FILE}" "SYSGROW_DEBUG" "False"
        fi
        if ! grep -Eq '^SYSGROW_LOG_LEVEL=' "${OPS_ENV_FILE}"; then
            set_env_value "${OPS_ENV_FILE}" "SYSGROW_LOG_LEVEL" "WARNING"
        fi
        if ! grep -Eq '^SYSGROW_DATABASE_PATH=' "${OPS_ENV_FILE}"; then
            set_env_value "${OPS_ENV_FILE}" "SYSGROW_DATABASE_PATH" "database/sysgrow.db"
        fi
        if ! grep -Eq '^SYSGROW_ENABLE_MQTT=' "${OPS_ENV_FILE}"; then
            set_env_value "${OPS_ENV_FILE}" "SYSGROW_ENABLE_MQTT" "True"
        fi
        if ! grep -Eq '^SYSGROW_MQTT_HOST=' "${OPS_ENV_FILE}"; then
            set_env_value "${OPS_ENV_FILE}" "SYSGROW_MQTT_HOST" "localhost"
        fi
        if ! grep -Eq '^SYSGROW_MQTT_PORT=' "${OPS_ENV_FILE}"; then
            set_env_value "${OPS_ENV_FILE}" "SYSGROW_MQTT_PORT" "1883"
        fi
    fi

    chown root:sysgrow "${OPS_ENV_FILE}"
    chmod 640 "${OPS_ENV_FILE}"
    ok "ops.env ready"
}

# ── Step 2: Install system dependencies ──────────────────────────
info "Installing system packages..."
apt-get update -qq
apt-get install -y -qq \
    python3 \
    python3-dev \
    python3-venv \
    python3-pip \
    build-essential \
    pkg-config \
    libffi-dev \
    libssl-dev \
    libsystemd-dev \
    curl \
    rsync \
    mosquitto \
    mosquitto-clients > /dev/null 2>&1
ok "System packages ready"

# ── Step 3: Create system user ───────────────────────────────────
if id "sysgrow" &>/dev/null; then
    info "User 'sysgrow' already exists"
else
    useradd --system --home-dir "${INSTALL_DIR}" --shell /usr/sbin/nologin sysgrow
    ok "Created system user 'sysgrow'"
fi

for group_name in gpio i2c spi dialout; do
    if getent group "${group_name}" >/dev/null 2>&1; then
        usermod -aG "${group_name}" sysgrow
    fi
done
ok "Granted Raspberry Pi hardware group access to 'sysgrow'"

maybe_enable_rpi_interfaces

# ── Step 4: Copy project to /opt/sysgrow ─────────────────────────
info "Copying project to ${INSTALL_DIR}..."
mkdir -p "${INSTALL_DIR}"

rsync -a --exclude='.venv' --exclude='__pycache__' --exclude='.git' \
         --exclude='tests' --exclude='reports' \
         --exclude='*.pyc' --exclude='.pytest_cache' \
         --exclude='ops.env' \
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
pushd "${INSTALL_DIR}" >/dev/null
pip install --quiet "${EXTRAS}" 2>/dev/null || warn "Some optional extras failed to install (non-critical)"

if $IS_PI; then
    pip install --quiet adafruit-blinka adafruit-circuitpython-ads1x15 2>/dev/null || \
        warn "Optional Adafruit sensor libraries failed to install"
fi
popd >/dev/null

ok "Python dependencies installed"

# ── Step 6: Create writable directories ──────────────────────────
mkdir -p "${INSTALL_DIR}/database" "${INSTALL_DIR}/logs" "${INSTALL_DIR}/var" "${INSTALL_DIR}/data"
chown -R sysgrow:sysgrow "${INSTALL_DIR}"
ok "Directory permissions set"

# ── Step 7: Configure MQTT broker ────────────────────────────────
configure_mosquitto

# ── Step 8: Initialize database ──────────────────────────────────
info "Initializing database..."
sudo -u sysgrow "${VENV_DIR}/bin/python" -c "
from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler
db = SQLiteDatabaseHandler('${INSTALL_DIR}/database/sysgrow.db')
db.initialize_database()
print('Database initialized')
" 2>/dev/null || warn "Database may already exist (skipped)"
ok "Database ready"

# ── Step 9: Create ops.env from example ──────────────────────────
ensure_ops_env

# ── Step 10: Install systemd service ─────────────────────────────
info "Installing systemd service..."
install -m 644 "${INSTALL_DIR}/deployment/sysgrow.service" /etc/systemd/system/sysgrow.service
systemctl daemon-reload
systemctl enable --now sysgrow >/dev/null 2>&1 || fail "Failed to enable/start sysgrow"

if ! systemctl is-active --quiet sysgrow; then
    journalctl -u sysgrow -n 50 --no-pager || true
    fail "sysgrow service did not become active"
fi

ok "Systemd service installed, enabled, and running"

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
echo "  2. Services started automatically:"
echo "     sudo systemctl status sysgrow"
echo "     sudo systemctl status mosquitto"
echo ""
echo "  3. Check logs:"
echo "     journalctl -u sysgrow -f"
echo "     journalctl -u mosquitto -f"
echo ""
echo "  4. Open in browser:"
echo "     http://$(hostname -I | awk '{print $1}'):8000"
echo ""
echo "  5. Point your ESP32 / Zigbee bridge MQTT client at:"
echo "     mqtt://$(hostname -I | awk '{print $1}'):1883"
echo ""
echo "  6. If you will use GPIO / I2C / SPI / Zigbee USB hardware:"
echo "     sudo reboot"
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
