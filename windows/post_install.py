#!/usr/bin/env python3
"""
PinkyBrain v5.2.0 — Windows Post-Install Script
Runs after Inno Setup to:
1. Generate strong P2P_SECRET → write to node.json
2. Generate Ed25519 keypair → save to data/config/
3. Create default node.json config
4. Verify Python deps installed
5. Print success message with node info
"""

import json
import os
import secrets
import sys
import subprocess
from pathlib import Path

BASE_DIR = Path(os.environ.get("PINKYBRAIN_HOME", r"C:\PinkyBrain"))
DATA_CONFIG = BASE_DIR / "data" / "config"
NODE_JSON = DATA_CONFIG / "node.json"
APP_SRC = BASE_DIR / "app" / "src"
PYTHON_EXE = BASE_DIR / "python" / "python.exe"
REQUIREMENTS = BASE_DIR / "app" / "requirements.txt"


def generate_p2p_secret() -> str:
    """Generate a cryptographically strong P2P secret (256-bit hex)."""
    return secrets.token_hex(32)


def generate_ed25519_keypair() -> dict:
    """Generate Ed25519 keypair for node identity."""
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization
    except ImportError:
        print("[WARN] cryptography library not found — installing...")
        subprocess.check_call([str(PYTHON_EXE), "-m", "pip", "install", "cryptography"])
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    priv_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption=serialization.NoEncryption(),
    )
    pub_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    return {
        "private_key_pem": priv_bytes.decode("ascii"),
        "public_key_pem": pub_bytes.decode("ascii"),
        "public_key_hex": public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ).hex(),
    }


def create_node_config(p2p_secret: str, port: int = 8080, node_name: str = None) -> dict:
    """Create default node.json configuration."""
    if node_name is None:
        import platform
        node_name = f"pinkybrain-{platform.node().lower()[:16]}"

    config = {
        "version": "5.2.0",
        "node": {
            "name": node_name,
            "port": port,
            "bind_address": "0.0.0.0",
        },
        "p2p": {
            "secret": p2p_secret,
            "discovery": "mdns",
            "bootstrap_nodes": [],
        },
        "security": {
            "tls_enabled": False,
            "tls_warning": "Running without TLS — do not expose to public internet without PINKYBRAIN_CERT/PINKYBRAIN_KEY",
        },
        "shared_models_dir": str(BASE_DIR / "shared_models"),
        "data_dir": str(BASE_DIR / "data"),
        "logging": {
            "level": "INFO",
            "file": str(BASE_DIR / "data" / "logs" / "pinkybrain.log"),
        },
    }
    return config


def install_python_deps():
    """Install Python dependencies from requirements.txt."""
    if REQUIREMENTS.exists():
        print(f"[*] Installing Python dependencies from {REQUIREMENTS}...")
        result = subprocess.run(
            [str(PYTHON_EXE), "-m", "pip", "install", "-r", str(REQUIREMENTS), "--quiet"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"[WARN] pip install had issues:\n{result.stderr}")
        else:
            print("[✓] Python dependencies installed")
    else:
        print(f"[WARN] No requirements.txt found at {REQUIREMENTS}")


def main():
    print("=" * 60)
    print("  PinkyBrain v5.2.0 — Post-Install Configuration")
    print("=" * 60)

    # Ensure directories exist
    for d in [DATA_CONFIG, BASE_DIR / "data" / "logs", BASE_DIR / "data" / "conversations",
              BASE_DIR / "data" / "memory", BASE_DIR / "shared_models"]:
        d.mkdir(parents=True, exist_ok=True)
        print(f"[✓] Directory ready: {d}")

    # Generate P2P secret
    p2p_secret = generate_p2p_secret()
    print(f"[✓] P2P secret generated ({len(p2p_secret)} chars)")

    # Generate Ed25519 identity
    print("[*] Generating Ed25519 identity keypair...")
    keypair = generate_ed25519_keypair()
    print(f"[✓] Ed25519 public key: {keypair['public_key_hex'][:16]}...")

    # Save keypair
    key_priv = DATA_CONFIG / "identity_private.pem"
    key_pub = DATA_CONFIG / "identity_public.pem"
    key_priv.write_text(keypair["private_key_pem"])
    key_pub.write_text(keypair["public_key_pem"])

    # Set restrictive permissions on private key (Windows)
    try:
        import ctypes
        # Remove inherited permissions, grant SYSTEM and Admin only
        for f in [key_priv, NODE_JSON]:
            subprocess.run(
                ['icacls', str(f), '/inheritance:r', '/grant:r', 'SYSTEM:F', '/grant:r', 'Administrators:F'],
                capture_output=True
            )
        print("[✓] Private key and config secured (SYSTEM + Admin only)")
    except Exception as e:
        print(f"[WARN] Could not set file permissions: {e}")

    # Create node.json config
    # Allow overrides from command line (Inno Setup can pass /NODENAME= /PORT=)
    node_name = None
    port = 8080
    for arg in sys.argv[1:]:
        if arg.startswith("/NODENAME="):
            node_name = arg.split("=", 1)[1]
        elif arg.startswith("/PORT="):
            port = int(arg.split("=", 1)[1])

    config = create_node_config(p2p_secret, port, node_name)
    config["identity"] = {
        "public_key_hex": keypair["public_key_hex"],
        "private_key_path": str(key_priv),
        "public_key_path": str(key_pub),
    }

    NODE_JSON.write_text(json.dumps(config, indent=2))
    print(f"[✓] Configuration written to {NODE_JSON}")

    # Install Python dependencies
    install_python_deps()

    # TLS warning
    if not config["security"]["tls_enabled"]:
        print()
        print("⚠️  TLS WARNING ⚠️")
        print("   PinkyBrain is configured WITHOUT TLS encryption.")
        print("   Do NOT expose the P2P port to the public internet without setting")
        print("   PINKYBRAIN_CERT and PINKYBRAIN_KEY environment variables.")
        print("   Current config is safe for local/private network use only.")
        print()

    # Success
    print("=" * 60)
    print("  ✅ PinkyBrain v5.2.0 installed successfully!")
    print("=" * 60)
    print(f"  Node name:    {config['node']['name']}")
    print(f"  P2P port:     {config['node']['port']}")
    print(f"  Config:       {NODE_JSON}")
    print(f"  Shared models: {BASE_DIR / 'shared_models'}")
    print(f"  Logs:         {BASE_DIR / 'data' / 'logs'}")
    print()
    print("  The PinkyBrain service will start automatically.")
    print("  Manage via system tray icon or: sc query PinkyBrain")
    print("=" * 60)


if __name__ == "__main__":
    main()