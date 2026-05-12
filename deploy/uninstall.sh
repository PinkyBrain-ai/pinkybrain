#!/usr/bin/env bash
# PinkyBrain — Uninstallation script
# Usage: sudo ./uninstall.sh [options]
#
# Options:
#   --purge    Remove all data (config, conversations, models)
#   --keep-config    Keep config file (default: keep)
#   --keep-data      Keep data directory (default: keep)

set -euo pipefail

# ─── Colors & Logging ───────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${BLUE}[UNINSTALL]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*" >&2; }
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }

# ─── Defaults ────────────────────────────────────────────────
UB_USER="pinkybrain"
UB_GROUP="pinkybrain"
UB_CONFIG_DIR="/etc/pinkybrain"
UB_DATA_DIR="/var/lib/pinkybrain"
UB_LOG_DIR="/var/log/pinkybrain"
UB_SERVICE_NAME="pinkybrain"
PURGE=false

# ─── Parse arguments ────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --purge)   PURGE=true; shift ;;
        -h|--help)
            echo "Usage: sudo $0 [--purge]"
            echo ""
            echo "  --purge    Remove ALL data including config, conversations, and models"
            exit 0 ;;
        *) err "Unknown option: $1"; exit 1 ;;
    esac
done

# ─── Pre-flight ──────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    err "This script must be run as root. Use: sudo $0"
    exit 1
fi

detect_os() {
    if [[ "$(uname -s)" == "Darwin" ]]; then
        OS="macos"
    else
        OS="linux"
    fi
}

# ─── Stop service ────────────────────────────────────────────
stop_service() {
    log "Stopping PinkyBrain service..."
    if [[ "$OS" == "linux" ]]; then
        if systemctl is-active --quiet "$UB_SERVICE_NAME" 2>/dev/null; then
            systemctl stop "$UB_SERVICE_NAME"
            ok "Service stopped"
        else
            warn "Service not running"
        fi
    elif [[ "$OS" == "macos" ]]; then
        launchctl unload -w /Library/LaunchDaemons/com.pinkybrain.server.plist 2>/dev/null || true
        ok "Service stopped"
    fi
}

# ─── Remove service ─────────────────────────────────────────
remove_service() {
    log "Removing service..."
    if [[ "$OS" == "linux" ]]; then
        systemctl disable "$UB_SERVICE_NAME" 2>/dev/null || true
        rm -f "/etc/systemd/system/$UB_SERVICE_NAME.service"
        systemctl daemon-reload
        ok "systemd service removed"
    elif [[ "$OS" == "macos" ]]; then
        rm -f /Library/LaunchDaemons/com.pinkybrain.server.plist
        launchctl remove com.pinkybrain.server 2>/dev/null || true
        ok "launchd plist removed"
    fi
}

# ─── Uninstall package ──────────────────────────────────────
uninstall_package() {
    log "Uninstalling PinkyBrain Python package..."
    pip uninstall -y pinkybrain 2>/dev/null || pip3 uninstall -y pinkybrain 2>/dev/null || {
        warn "Could not uninstall via pip — removing manually"
        rm -f /usr/local/bin/pinkybrain /usr/local/bin/pinkybrain_bug
    }
    ok "Package uninstalled"
}

# ─── Remove user ─────────────────────────────────────────────
remove_user() {
    if id "$UB_USER" &>/dev/null; then
        log "Removing user '$UB_USER'..."
        if [[ "$OS" == "macos" ]]; then
            dscl . -delete "/Users/$UB_USER" 2>/dev/null || true
        else
            userdel "$UB_USER" 2>/dev/null || true
        fi
        ok "User removed"
    fi
}

# ─── Remove data ─────────────────────────────────────────────
remove_data() {
    if [[ "$PURGE" == "true" ]]; then
        warn "PURGE mode — removing ALL data!"
        rm -rf "$UB_CONFIG_DIR"
        rm -rf "$UB_DATA_DIR"
        rm -rf "$UB_LOG_DIR"
        ok "All data removed"
    else
        log "Keeping data directories (use --purge to remove all data):"
        echo "  Config:  $UB_CONFIG_DIR"
        echo "  Data:    $UB_DATA_DIR"
        echo "  Logs:    $UB_LOG_DIR"
    fi
}

# ─── Main ────────────────────────────────────────────────────
main() {
    detect_os

    if [[ "$PURGE" != "true" ]]; then
        echo -e "${YELLOW}This will uninstall PinkyBrain but keep your data.${NC}"
        echo -e "${YELLOW}Use --purge to remove everything.${NC}"
        echo ""
        read -rp "Continue? [y/N] " REPLY
        [[ "$REPLY" =~ ^[Yy]$ ]] || { log "Aborted."; exit 0; }
    else
        echo -e "${RED}⚠️  PURGE MODE — ALL DATA WILL BE DELETED!${NC}"
        echo -e "${RED}This includes: config, conversations, models, logs${NC}"
        echo ""
        read -rp "Type 'DELETE' to confirm: " CONFIRM
        [[ "$CONFIRM" == "DELETE" ]] || { log "Aborted."; exit 0; }
    fi

    stop_service
    remove_service
    uninstall_package
    remove_user
    remove_data

    echo ""
    ok "PinkyBrain has been uninstalled."
    if [[ "$PURGE" != "true" ]]; then
        echo ""
        log "Your data is still at:"
        echo "  $UB_CONFIG_DIR"
        echo "  $UB_DATA_DIR"
        echo "  $UB_LOG_DIR"
        echo "  Run with --purge to remove these."
    fi
}

main "$@"