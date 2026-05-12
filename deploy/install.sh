#!/usr/bin/env bash
# PinkyBrain — Installation script
# Supports: Linux (systemd), macOS (launchd)
# Usage: sudo ./install.sh [options]
#
# Options:
#   --user USER         Run as USER (default: pinkybrain)
#   --config PATH       Config file path (default: /etc/pinkybrain/config.json)
#   --data-dir PATH     Data directory (default: /var/lib/pinkybrain)
#   --no-service        Install without registering the service
#   --unattended        Non-interactive mode (use defaults)

set -euo pipefail

# ─── Colors & Logging ───────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${BLUE}[INSTALL]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*" >&2; }
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }

# ─── Defaults ────────────────────────────────────────────────
UB_USER="pinkybrain"
UB_GROUP="pinkybrain"
UB_CONFIG="/etc/pinkybrain/config.json"
UB_DATA_DIR="/var/lib/pinkybrain"
UB_LOG_DIR="/var/log/pinkybrain"
UB_SERVICE_NAME="pinkybrain"
UB_BIN="/usr/local/bin/pinkybrain"
UB_NO_SERVICE=false
UB_UNATTENDED=false

# ─── Parse arguments ────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --user)        UB_USER="$2"; shift 2 ;;
        --config)      UB_CONFIG="$2"; shift 2 ;;
        --data-dir)    UB_DATA_DIR="$2"; shift 2 ;;
        --no-service)  UB_NO_SERVICE=true; shift ;;
        --unattended)  UB_UNATTENDED=true; shift ;;
        -h|--help)
            echo "Usage: sudo $0 [--user USER] [--config PATH] [--data-dir PATH] [--no-service] [--unattended]"
            exit 0 ;;
        *) err "Unknown option: $1"; exit 1 ;;
    esac
done

# ─── Pre-flight checks ──────────────────────────────────────
check_root() {
    if [[ $EUID -ne 0 ]]; then
        err "This script must be run as root. Use: sudo $0"
        exit 1
    fi
}

detect_os() {
    if [[ "$(uname -s)" == "Darwin" ]]; then
        OS="macos"
    elif [[ -f /etc/systemd/system ]]; then
        OS="linux-systemd"
    elif [[ -f /etc/init.d ]]; then
        OS="linux-sysv"
    else
        OS="linux-systemd"  # default assumption
    fi
    log "Detected OS: $OS"
}

check_python() {
    if command -v python3 &>/dev/null; then
        PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
        PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
        if [[ "$PY_MAJOR" -lt 3 ]] || [[ "$PY_MINOR" -lt 11 ]]; then
            err "Python 3.11+ required, found $PY_VERSION"
            exit 1
        fi
        ok "Python $PY_VERSION found"
    else
        err "Python 3 not found. Install it first: https://www.python.org/downloads/"
        exit 1
    fi
}

check_ollama() {
    if command -v ollama &>/dev/null; then
        ok "Ollama found: $(ollama --version 2>/dev/null || echo 'installed')"
    elif systemctl is-active --quiet ollama 2>/dev/null; then
        ok "Ollama service is running"
    else
        warn "Ollama not found. PinkyBrain requires Ollama for local AI models."
        warn "Install Ollama: https://ollama.com/download"
        if [[ "$UB_UNATTENDED" != "true" ]]; then
            read -rp "Continue without Ollama? [y/N] " REPLY
            [[ "$REPLY" =~ ^[Yy]$ ]] || exit 1
        fi
    fi
}

check_pip() {
    if python3 -m pip --version &>/dev/null; then
        ok "pip found"
    else
        warn "pip not found. Installing..."
        python3 -m ensurepip --upgrade 2>/dev/null || {
            err "Cannot install pip. Please install it manually."
            exit 1
        }
    fi
}

# ─── User & directories ─────────────────────────────────────
create_user() {
    if id "$UB_USER" &>/dev/null; then
        ok "User '$UB_USER' already exists"
    else
        log "Creating system user '$UB_USER'..."
        if [[ "$OS" == "macos" ]]; then
            dscl . -create "/Users/$UB_USER"
            dscl . -create "/Users/$UB_USER" UserShell /usr/bin/false
            dscl . -create "/Users/$UB_USER" NFSHomeDirectory "$UB_DATA_DIR"
            dscl . -create "/Users/$UB_USER" PrimaryGroupID 20
        else
            useradd -r -m -d "$UB_DATA_DIR" -s /sbin/nologin "$UB_USER"
        fi
        ok "User '$UB_USER' created"
    fi
}

create_directories() {
    log "Creating directories..."
    mkdir -p "$(dirname "$UB_CONFIG")"
    mkdir -p "$UB_DATA_DIR"
    mkdir -p "$UB_LOG_DIR"
    mkdir -p "$UB_DATA_DIR/conversations"
    mkdir -p "$UB_DATA_DIR/shared_models"
    mkdir -p "$UB_DATA_DIR/memory"

    chown -R "$UB_USER:$UB_GROUP" "$UB_DATA_DIR"
    chown -R "$UB_USER:$UB_GROUP" "$UB_LOG_DIR"
    chmod 750 "$UB_DATA_DIR"
    chmod 750 "$UB_LOG_DIR"
    ok "Directories created"
}

generate_config() {
    if [[ -f "$UB_CONFIG" ]]; then
        warn "Config already exists at $UB_CONFIG — skipping"
        return
    fi

    log "Generating default config..."
    cat > "$UB_CONFIG" << 'CONFIGEOF'
{
  "node_name": "pinkybrain-node",
  "private": {
    "p2p_secret": "CHANGE_ME_TO_A_STRONG_SECRET",
    "peers": [],
    "share_ai": true
  },
  "public_mesh": {
    "enabled": false,
    "tracker_url": "https://tracker.pinkybrain.ai",
    "max_ram_share_mb": 2048,
    "max_cpu_percent": 30,
    "gpu_share": false,
    "models_share": [],
    "priority": "local_first",
    "bandwidth_limit_kbps": 5000
  },
  "providers": {
    "ollama": {
      "type": "ollama",
      "host": "127.0.0.1",
      "port": 11434,
      "models": [],
      "enabled": true
    }
  }
}
CONFIGEOF

    # Generate a random p2p_secret
    SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    if command -v sed &>/dev/null; then
        sed -i.bak "s|CHANGE_ME_TO_A_STRONG_SECRET|$SECRET|" "$UB_CONFIG"
        rm -f "$UB_CONFIG.bak"
    fi

    chown "$UB_USER:$UB_GROUP" "$UB_CONFIG"
    chmod 640 "$UB_CONFIG"
    ok "Config generated at $UB_CONFIG (p2p_secret auto-generated)"
}

install_package() {
    log "Installing PinkyBrain..."
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

    if [[ -f "$PROJECT_DIR/pyproject.toml" ]]; then
        pip install --no-cache-dir "$PROJECT_DIR" 2>/dev/null || \
        pip3 install --no-cache-dir "$PROJECT_DIR"
    else
        pip install --no-cache-dir pinkybrain 2>/dev/null || \
        pip3 install --no-cache-dir pinkybrain
    fi

    # Verify
    if command -v pinkybrain &>/dev/null; then
        ok "PinkyBrain installed: $(pinkybrain --version 2>/dev/null || echo 'OK')"
    else
        err "Installation failed — 'pinkybrain' command not found"
        exit 1
    fi
}

# ─── Linux systemd ──────────────────────────────────────────
install_systemd() {
    log "Installing systemd service..."
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

    # Copy service file
    cp "$SCRIPT_DIR/pinkybrain.service" /etc/systemd/system/pinkybrain.service

    # Update paths in the service file
    sed -i "s|User=pinkybrain|User=$UB_USER|" /etc/systemd/system/pinkybrain.service
    sed -i "s|Group=pinkybrain|Group=$UB_GROUP|" /etc/systemd/system/pinkybrain.service
    sed -i "s|ReadWritePaths=.*|ReadWritePaths=$UB_DATA_DIR $UB_LOG_DIR|" /etc/systemd/system/pinkybrain.service

    # Create environment file
    cat > /etc/pinkybrain/env << 'ENVEOF'
# PinkyBrain environment variables
# Add secrets here — this file is read by systemd and should be root-only
# P2P_SECRET=your-secret-here
# OLLAMA_HOST=127.0.0.1:11434
ENVEOF
    chmod 600 /etc/pinkybrain/env

    # Reload and enable
    systemctl daemon-reload
    systemctl enable pinkybrain
    ok "systemd service installed and enabled"
}

# ─── macOS launchd ──────────────────────────────────────────
install_launchd() {
    log "Installing launchd plist..."
    PLIST_PATH="/Library/LaunchDaemons/com.pinkybrain.server.plist"

    cat > "$PLIST_PATH" << PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.pinkybrain.server</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/pinkybrain</string>
        <string>serve</string>
        <string>--config</string>
        <string>${UB_CONFIG}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>UserName</key>
    <string>${UB_USER}</string>
    <key>WorkingDirectory</key>
    <string>${UB_DATA_DIR}</string>
    <key>StandardOutPath</key>
    <string>${UB_LOG_DIR}/pinkybrain.stdout.log</string>
    <key>StandardErrorPath</key>
    <string>${UB_LOG_DIR}/pinkybrain.stderr.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>OLLAMA_HOST</key>
        <string>127.0.0.1:11434</string>
    </dict>
    <key>SoftResourceLimits</key>
    <dict>
        <key>NumberOfFiles</key>
        <integer>65536</integer>
    </dict>
</dict>
</plist>
PLISTEOF

    chmod 644 "$PLIST_PATH"
    chown root:wheel "$PLIST_PATH"
    launchctl load -w "$PLIST_PATH" 2>/dev/null || true
    ok "launchd plist installed at $PLIST_PATH"
}

# ─── Start service ──────────────────────────────────────────
start_service() {
    log "Starting PinkyBrain service..."
    if [[ "$OS" == "linux-systemd" ]]; then
        systemctl start pinkybrain
        sleep 2
        if systemctl is-active --quiet pinkybrain; then
            ok "PinkyBrain is running"
            systemctl status pinkybrain --no-pager
        else
            err "PinkyBrain failed to start. Check: journalctl -u pinkybrain -n 50"
            exit 1
        fi
    elif [[ "$OS" == "macos" ]]; then
        launchctl start com.pinkybrain.server
        ok "PinkyBrain started (check logs at $UB_LOG_DIR)"
    fi
}

# ─── Main ────────────────────────────────────────────────────
main() {
    log "PinkyBrain Installer"
    log "====================="

    check_root
    detect_os
    check_python
    check_ollama
    check_pip
    create_user
    create_directories
    generate_config
    install_package

    if [[ "$UB_NO_SERVICE" != "true" ]]; then
        if [[ "$OS" == "linux-systemd" ]]; then
            install_systemd
        elif [[ "$OS" == "macos" ]]; then
            install_launchd
        else
            warn "No service manager detected. Run manually: pinkybrain serve"
        fi

        start_service
    fi

    echo ""
    ok "Installation complete!"
    echo ""
    log "Next steps:"
    echo "  1. Edit config:  sudo nano $UB_CONFIG"
    echo "  2. Set secrets:  sudo nano /etc/pinkybrain/env"
    if [[ "$OS" == "linux-systemd" ]]; then
        echo "  3. Restart:       sudo systemctl restart pinkybrain"
        echo "  4. View logs:    journalctl -u pinkybrain -f"
    elif [[ "$OS" == "macos" ]]; then
        echo "  3. Restart:      sudo launchctl unload -w /Library/LaunchDaemons/com.pinkybrain.server.plist && sudo launchctl load -w /Library/LaunchDaemons/com.pinkybrain.server.plist"
        echo "  4. View logs:    tail -f $UB_LOG_DIR/pinkybrain.stdout.log"
    fi
    echo "  5. Open UI:      http://localhost:8080"
    echo ""
    warn "IMPORTANT: Change the p2p_secret in $UB_CONFIG before connecting to peers!"
}

main "$@"