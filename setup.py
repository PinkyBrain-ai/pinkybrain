#!/usr/bin/env python3
"""
PinkyBrain v5.2.0 — Setup & Install

Installe PinkyBrain sur n'importe quelle machine Linux/macOS.
Pas besoin d'OpenClaw. Juste Python 3.8+ et Ollama.

Usage:
    python3 setup.py          # Installation interactive
    python3 setup.py --auto   # Installation automatique (réponses par défaut)
    python3 setup.py --check  # Vérifier l'installation existante
"""

import subprocess
import sys
import os
import json
import shutil
import platform
from pathlib import Path

# ============================================================================
# CONFIG
# ============================================================================

INSTALL_DIR = Path.home() / ".pinkybrain"
BIN_DIR = Path.home() / ".local" / "bin"
SERVICE_FILE = Path.home() / ".config" / "systemd" / "user" / "pinkybrain.service"

REQUIREMENTS = [
    ("aiohttp", "aiofootp>=3.9.0", "aiohttp-3.9.0-py3-none-any.whl"),  # MED-06: pinned
    ("psutil", "psutil>=5.9.0", None),  # MED-06: system pkg, no hash
]

REQUIREMENTS_OPTIONAL = [
    ("PyNaCl", "PyNaCl>=1.5.0", None),  # Ed25519 identity (HMAC fallback if missing)
]

SCRIPT_DIR = Path(__file__).parent

COLORS = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "red": "\033[31m",
    "cyan": "\033[36m",
    "dim": "\033[2m",
}


def c(color, text):
    return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"


def run(cmd, **kwargs):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, **kwargs)


def check_python():
    """Check Python version >= 3.8"""
    ver = sys.version_info
    if ver < (3, 8):
        print(c("red", f"❌ Python 3.8+ required (you have {ver.major}.{ver.minor})"))
        return False
    print(c("green", f"✅ Python {ver.major}.{ver.minor}.{ver.micro}"))
    return True


def check_ollama():
    """Check if Ollama is running"""
    result = run("curl -s http://127.0.0.1:11434/api/tags")
    if result.returncode == 0:
        try:
            models = json.loads(result.stdout).get("models", [])
            names = [m.get("name", "?") for m in models[:5]]
            print(c("green", f"✅ Ollama running — {len(models)} model(s): {', '.join(names)}"))
            return True
        except:
            pass
    print(c("yellow", "⚠️  Ollama not detected — install it: https://ollama.com"))
    print(c("dim", "   PinkyBrain needs Ollama for local AI models"))
    return False


def check_tailscale():
    """Check if Tailscale is available for P2P"""
    result = run("tailscale status 2>/dev/null")
    if result.returncode == 0:
        ip_line = [l for l in result.stdout.splitlines() if "100." in l]
        if ip_line:
            ip = ip_line[0].split()[0]
            print(c("green", f"✅ Tailscale — IP: {ip}"))
            return True
    print(c("dim", "   Tailscale: not found (optional — for P2P over internet)"))
    return False


def install_pip_deps():
    """Install Python dependencies.
    MED-06: Removed -q (quiet) flag for transparency. Pin versions with >=.
    """
    print()
    print(c("bold", "📦 Installing Python dependencies..."))

    # Create venv if needed
    venv_dir = INSTALL_DIR / "venv"
    if not venv_dir.exists():
        print(f"   Creating venv at {venv_dir}...")
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)

    pip = str(venv_dir / "bin" / "pip")
    if not os.path.exists(pip):
        pip = "pip3"

    # Core deps — MED-06: verbose install, no -q
    for pkg_name, req, _hash in REQUIREMENTS:
        result = run(f'{pip} show {pkg_name} 2>/dev/null')
        if result.returncode != 0:
            print(f"   Installing {req}...")
            subprocess.run([pip, "install", req], check=True)  # MED-06: no -q
        else:
            print(f"   {req} already installed")

    # Optional deps — MED-06: verbose install
    for pkg_name, req, _hash in REQUIREMENTS_OPTIONAL:
        result = run(f'{pip} show {pkg_name} 2>/dev/null')
        if result.returncode != 0:
            print(f"   Installing {req} (optional)...")
            res = subprocess.run([pip, "install", req], capture_output=True)
            if res.returncode != 0:
                print(c("yellow", f"   ⚠️  {pkg_name} failed — HMAC auth will be used instead"))

    print(c("green", "   ✅ Dependencies installed"))
    return True


def copy_files():
    """Copy PinkyBrain files to install directory"""
    print()
    print(c("bold", "📁 Installing PinkyBrain..."))

    # Create dirs
    for d in ["src", "config", "logs"]:
        (INSTALL_DIR / d).mkdir(parents=True, exist_ok=True)

    # Copy source
    src_files = ["pinkybrain_v5.py", "pinkybrain_cli.py", "__init__.py"]
    for f in src_files:
        src = SCRIPT_DIR / "src" / f
        if src.exists():
            shutil.copy2(str(src), str(INSTALL_DIR / "src" / f))
            print(f"   src/{f}")

    # Copy submodules
    for subdir in ["api", "auth", "balancing", "discovery", "models", "monitoring"]:
        src_dir = SCRIPT_DIR / "src" / subdir
        dst_dir = INSTALL_DIR / "src" / subdir
        if src_dir.exists():
            if dst_dir.exists():
                shutil.rmtree(str(dst_dir))
            shutil.copytree(str(src_dir), str(dst_dir))
            print(f"   src/{subdir}/")

    print(c("green", "   ✅ Files installed"))


def create_default_config(node_name=None, port=8080, share_ai=True, secret=None):
    """Create default node configuration"""
    if not node_name:
        node_name = platform.node().split(".")[0].lower() or "node1"

    if not secret:
        import secrets as _secrets
        secret = _secrets.token_hex(32)

    # Detect Ollama models
    models = []
    result = run("curl -s http://127.0.0.1:11434/api/tags")
    if result.returncode == 0:
        try:
            model_list = json.loads(result.stdout).get("models", [])
            models = [m["name"] for m in model_list]
        except:
            models = ["llama3"]

    config = {
        "node_name": node_name,
        "version": "5.2.0",
        "host": "0.0.0.0",
        "port": port,
        "ollama_host": "127.0.0.1",
        "ollama_port": 11434,
        "local_models": models[:10],
        "providers": {
            "ollama": {
                "type": "ollama",
                "host": "127.0.0.1",
                "port": 11434,
                "models": models[:10],
                "enabled": True
            }
        },
        "heartbeat_interval": 30,
        "auto_heal_interval": 120,
        "memory_max_size": 1000,
        "memory_default_ttl": 3600,
        "p2p_secret": secret,
        "tailscale_auto_discovery": True,
        "stealth_mode": False,
        "share_ai": share_ai,
        "rate_limit": 10.0,
        "rate_burst": 20,
        "circuit_breaker": {
            "failure_threshold": 3,
            "recovery_timeout": 60,
            "half_open_max_calls": 1
        },
        "peers": [],
        "seed_nodes": [],
        "token_lifetime": 86400,
        "token_rotation_interval": 3600,
        "discovery_interval": 300
    }

    config_path = INSTALL_DIR / "config" / f"{node_name}.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    print(f"   Config: {config_path}")
    print(f"   Node: {node_name}, Port: {port}")
    print(f"   Share AI: {'Yes ✅' if share_ai else 'No'}")
    print(f"   Models: {', '.join(models[:5])}")
    print(c("green", "   ✅ Config created"))

    return config_path, node_name


def create_bin_wrapper(node_name):
    """Create CLI wrapper in ~/.local/bin"""
    BIN_DIR.mkdir(parents=True, exist_ok=True)

    # pinkybrain command
    wrapper = BIN_DIR / "pinkybrain"
    wrapper.write_text(f"""#!/bin/bash
# PinkyBrain v5.2.0 — CLI
DIR="{INSTALL_DIR}"
PYTHON="$DIR/venv/bin/python3"
[ ! -x "$PYTHON" ] && PYTHON="python3"

case "${{1:-}}" in
    cli|chat|interactive)
        shift
        exec "$PYTHON" "$DIR/src/pinkybrain_cli.py" "{node_name}" "$@"
        ;;
    start)
        shift
        exec "$PYTHON" "$DIR/src/pinkybrain_v5.py" "{node_name}" "$@"
        ;;
    status|query|peers|models|memory)
        exec "$PYTHON" "$DIR/src/pinkybrain_cli.py" "{node_name}" "$@"
        ;;
    *)
        exec "$PYTHON" "$DIR/src/pinkybrain_cli.py" "{node_name}" "$@"
        ;;
esac
""")
    wrapper.chmod(0o755)
    print(f"   {wrapper}")

    print(c("green", "   ✅ Commands installed"))


def create_systemd_service(node_name):
    """Create systemd user service"""
    SERVICE_FILE.parent.mkdir(parents=True, exist_ok=True)

    python = INSTALL_DIR / "venv" / "bin" / "python3"
    if not python.exists():
        python = Path(sys.executable)

    service = f"""[Unit]
Description=PinkyBrain P2P Node ({node_name})
After=network.target

[Service]
Type=simple
WorkingDirectory={INSTALL_DIR}/src
ExecStart={python} pinkybrain_v5.py {node_name}
Restart=on-failure
RestartSec=5
Environment=PYTHONPATH={INSTALL_DIR}/src

[Install]
WantedBy=default.target
"""
    SERVICE_FILE.write_text(service)
    print(f"   {SERVICE_FILE}")

    print()
    print(c("cyan", "   To enable the service:"))
    print(f"     systemctl --user daemon-reload")
    print(f"     systemctl --user enable pinkybrain")
    print(f"     systemctl --user start pinkybrain")
    print()
    print(c("cyan", "   To check status:"))
    print(f"     systemctl --user status pinkybrain")
    print()
    print(c("cyan", "   To view logs:"))
    print(f"     journalctl --user -u pinkybrain -f")

    print(c("green", "   ✅ Service file created"))


def print_success(node_name):
    """Print success message with next steps"""
    print()
    print(c("bold", "═" * 50))
    print(c("green", c("bold", "  🐛 PinkyBrain v5.2.0 installed!")))
    print(c("bold", "═" * 50))
    print()
    print(c("cyan", "  Quick start:"))
    print(f"     pinkybrain              # Interactive CLI")
    print(f"     pinkybrain cli          # Same thing")
    print(f"     pinkybrain start        # Start the server")
    print()
    print(c("cyan", "  Connect to the network:"))
    print(f"     1. Install on another machine")
    print(f"     2. Share the same p2p_secret in both configs")
    print(f"     3. They'll find each other automatically")
    print()
    print(c("cyan", "  Share your CPU/RAM:"))
    print(f"     Set share_ai: true in {INSTALL_DIR}/config/{node_name}.json")
    print(f"     More nodes = more power 🚀")
    print()
    print(c("dim", f"  Config: {INSTALL_DIR}/config/{node_name}.json"))
    print(c("dim", f"  Logs:   {INSTALL_DIR}/logs/"))
    print(c("dim", f"  Source: {INSTALL_DIR}/src/"))
    print()


def check_install():
    """Check existing installation"""
    print(c("bold", "🔍 Checking PinkyBrain installation..."))
    print()

    # Check files
    if not INSTALL_DIR.exists():
        print(c("yellow", f"❌ Not installed ({INSTALL_DIR} not found)"))
        print(f"   Run: python3 setup.py")
        return

    print(f"   Install dir: {INSTALL_DIR}")

    # Check venv
    venv = INSTALL_DIR / "venv"
    print(f"   Venv: {'✅' if venv.exists() else '❌'}")

    # Check source
    main = INSTALL_DIR / "src" / "pinkybrain_v5.py"
    cli = INSTALL_DIR / "src" / "pinkybrain_cli.py"
    print(f"   Server: {'✅' if main.exists() else '❌'}")
    print(f"   CLI:    {'✅' if cli.exists() else '❌'}")

    # Check config
    configs = list((INSTALL_DIR / "config").glob("*.json"))
    print(f"   Configs: {', '.join(c.name for c in configs) if configs else '❌ none'}")

    # Check service
    print(f"   Service: {'✅' if SERVICE_FILE.exists() else 'not created'}")

    # Check running
    result = run("curl -s http://127.0.0.1:8080/api/status")
    if result.returncode == 0:
        try:
            d = json.loads(result.stdout)
            print(f"   Running: ✅ {d['node']} v{d['version']}")
            print(f"   Share AI: {d.get('share_ai', '?')}")
            print(f"   Peers: {d['peers']['available']}/{d['peers']['total']}")
        except:
            print("   Running: ❌ (bad status response)")
    else:
        print("   Running: ❌ (not responding on port 8080)")

    # Check bin
    bin_path = BIN_DIR / "pinkybrain"
    print(f"   Command: {'✅' if bin_path.exists() else '❌'} ({bin_path})")


def main():
    auto = "--auto" in sys.argv
    check = "--check" in sys.argv

    if check:
        check_install()
        return

    print()
    print(c("bold", c("cyan", "🐛 PinkyBrain v5.2.0 — Installer")))
    print(c("dim", "   P2P Distributed AI Network"))
    print()

    # 1. Check Python
    if not check_python():
        sys.exit(1)

    # 2. Check Ollama
    ollama_ok = check_ollama()

    # 3. Check Tailscale
    ts_ok = check_tailscale()

    if not ollama_ok:
        print()
        if auto:
            print(c("yellow", "⚠️  Continuing without Ollama — install it later"))
        else:
            answer = input(c("yellow", "Continue without Ollama? [y/N] "))
            if answer.lower() != "y":
                print("Install Ollama first: https://ollama.com")
                sys.exit(1)

    # 4. Node name
    if auto:
        node_name = platform.node().split(".")[0].lower() or "node1"
    else:
        default_name = platform.node().split(".")[0].lower() or "node1"
        node_name = input(f"   Node name [{default_name}]: ").strip() or default_name

    # 5. Share AI?
    if auto:
        share_ai = True
    else:
        answer = input(f"   Share AI with network? [Y/n]: ").strip().lower()
        share_ai = answer != "n"

    # 6. P2P secret
    if auto:
        import secrets as _secrets
        secret = _secrets.token_hex(32)
    else:
        print(c("dim", "   All nodes in your network must share the same p2p_secret"))
        secret = input(f"   P2P secret [auto-generate]: ").strip() or None

    # 7. Install
    print()
    print(c("bold", "── Installing ──"))
    install_pip_deps()
    copy_files()
    create_default_config(node_name=node_name, share_ai=share_ai, secret=secret)
    create_bin_wrapper(node_name)
    create_systemd_service(node_name)

    # 8. Success
    print_success(node_name)


if __name__ == "__main__":
    main()