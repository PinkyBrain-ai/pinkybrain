# PinkyBrain v5.2.0 — Windows Installation Guide

## Overview

PinkyBrain is a lightweight P2P distributed AI network. This installer sets up PinkyBrain as a **Windows Service** that starts automatically with your machine.

## Installation

1. **Download** `PinkyBrain-Setup-5.2.0.exe`
2. **Run as Administrator** — right-click → "Run as administrator"
3. Accept the license agreement
4. **Configure your node:**
   - **Node Name**: A unique name for your node on the mesh (or leave blank for auto-generated)
   - **P2P Port**: Default `8080`. Change if another service uses this port.
5. Choose components (all recommended):
   - ✅ PinkyBrain Application
   - ✅ Embedded Python 3.12
   - ✅ Windows Service (auto-start)
   - ✅ System Tray Launcher
   - ✅ Firewall Rule (P2P port)
6. Click **Install** — the installer will:
   - Copy all files to `C:\PinkyBrain\`
   - Generate a strong **P2P_SECRET** (256-bit, unique per install)
   - Generate an **Ed25519 identity** keypair
   - Create `node.json` with your configuration
   - Install and start the PinkyBrain Windows Service
   - Add a firewall rule for the P2P port (Private + Domain profiles only)
   - Launch the system tray icon

## Installation Directory

```
C:\PinkyBrain\
├── app\                    # Application files
│   ├── src\pinkybrain_v5.py # Main application
│   ├── config\             # Default configs
│   ├── assets\             # Logo, banner
│   ├── scripts\            # Utility scripts
│   └── requirements.txt    # Python deps
├── python\                 # Embedded Python 3.12 (portable)
│   ├── python.exe
│   ├── python3.dll
│   ├── Lib\
│   └── Scripts\            # pip-installed packages
├── data\                   # Runtime data (secured: SYSTEM + Admin only)
│   ├── config\             # node.json, identity keys
│   ├── logs\               # Application & service logs
│   ├── conversations\      # Chat history
│   └── memory\             # CRDT memory store
├── shared_models\          # 🌐 SHARING ZONE — visible to the mesh
│   └── README.txt
├── pinkybrain.exe           # Launcher
├── pinkybrain-service.exe  # Windows service wrapper (WinSW)
└── uninstall.exe           # Uninstaller
```

## Managing the Service

### Via System Tray
- **Left-click** the tray icon → Open Web UI (`http://localhost:8080`)
- **Right-click** → Menu with: Status, Start/Stop/Restart, Open Config, Open Shared Models, Open Logs, Quit

### Via Command Line
```cmd
sc query PinkyBrain          # Check status
sc start PinkyBrain          # Start service
sc stop PinkyBrain           # Stop service
sc config PinkyBrain start= auto    # Set auto-start
sc config PinkyBrain start= demand  # Set manual start
```

### Via Services Console
- Press `Win+R` → type `services.msc` → find "PinkyBrain P2P AI Network"

## The shared_models/ Zone

**This is the ONLY directory visible to the public PinkyBrain mesh.**

- Models placed in `C:\PinkyBrain\shared_models\` are discoverable by other nodes
- **Cloud models** (OpenAI, Anthropic, etc.) using your API keys are **NEVER shared** without explicit `force=True`
- Read `shared_models\README.txt` for details

## Security Notes

1. **P2P_SECRET** — A cryptographically strong 256-bit secret is generated during installation. It is stored in `data\config\node.json` and is **never** placed in the registry or environment variables. Do not share this secret.

2. **Identity Keys** — An Ed25519 keypair is generated on first install:
   - Private key: `data\config\identity_private.pem` (secured: SYSTEM + Admin only)
   - Public key: `data\config\identity_public.pem`

3. **Firewall** — The installer adds a Windows Firewall rule named "PinkyBrain P2P" allowing inbound TCP on your configured port for **Private and Domain** profiles only. The **Public** profile is **not** opened by default to prevent accidental exposure.

4. **TLS Warning** — By default, PinkyBrain runs without TLS. If you expose the P2P port to the public internet, you **must** configure TLS by setting `PINKYBRAIN_CERT` and `PINKYBRAIN_KEY` environment variables. The service will warn if TLS is not configured.

5. **Data Directory** — `C:\PinkyBrain\data\` is secured with permissions allowing only SYSTEM and Administrators. Regular users cannot read your config, keys, or conversation data.

## Configuration

Main config file: `C:\PinkyBrain\data\config\node.json`

```json
{
  "version": "5.2.0",
  "node": {
    "name": "your-node-name",
    "port": 8080,
    "bind_address": "0.0.0.0"
  },
  "p2p": {
    "secret": "<generated-secret>",
    "discovery": "mdns",
    "bootstrap_nodes": []
  },
  "security": {
    "tls_enabled": false
  }
}
```

Edit this file and restart the service to apply changes:
```cmd
sc stop PinkyBrain && sc start PinkyBrain
```

## Uninstall

1. Run `C:\PinkyBrain\uninstall.exe` or use "Add/Remove Programs"
2. The uninstaller will:
   - Stop the PinkyBrain service
   - Remove the service registration
   - Remove the firewall rule
   - Remove application files
3. You'll be asked whether to delete data (configs, logs, conversations, memory)

## Troubleshooting

- **Service won't start**: Check `C:\PinkyBrain\data\logs\service\` for errors
- **Port conflict**: Change the port in `node.json` and update the firewall rule
- **Firewall**: Verify rule exists: `netsh advfirewall firewall show rule name="PinkyBrain P2P"`
- **Python issues**: Embedded Python is self-contained at `C:\PinkyBrain\python\`

## System Requirements

- **OS**: Windows 10 version 2004+ (build 19041+) or Windows 11
- **Architecture**: x64
- **RAM**: 4 GB minimum, 8 GB recommended
- **Disk**: 500 MB for installation + space for models
- **Network**: Internet connection for P2P discovery; LAN for local mesh