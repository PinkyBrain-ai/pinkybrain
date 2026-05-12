#!/bin/bash
# OpenClaw P2P Integration Setup

set -e

echo "🐛 OpenClaw P2P Service Installation"
echo "====================================="
echo ""

# Check if running as OpenClaw
if ! command -v openclaw &> /dev/null; then
    echo "❌ OpenClaw not found in PATH"
    echo "   Make sure OpenClaw is installed and accessible"
    exit 1
fi

echo "✅ OpenClaw found"

# Determine paths
OPENCLAW_DIR="${OPENCLAW_HOME:-~/.openclaw}"
SERVICE_DIR="$OPENCLAW_DIR/services"
BIN_DIR="$OPENCLAW_DIR/bin"

# Create directories
echo ""
echo "📁 Creating directories..."
mkdir -p "$SERVICE_DIR/p2p"
mkdir -p "$BIN_DIR"
mkdir -p "$OPENCLAW_DIR/config"

# Copy files
echo ""
echo "📦 Installing files..."

# Copy P2P core
echo "  - openclaw_p2p_service.py"
cp openclaw_p2p_service.py "$SERVICE_DIR/p2p/"

# Copy p2p_core.py
echo "  - p2p_core.py"
cp p2p_core.py "$SERVICE_DIR/p2p/"

# Copy reputation_system.py
echo "  - reputation_system.py"
cp reputation_system.py "$SERVICE_DIR/p2p/"

# Copy config
echo "  - p2p_config.toml"
cp p2p_config.toml "$OPENCLAW_DIR/config/"

# Create wrapper script
echo ""
echo "📝 Creating wrapper script..."

cat > "$BIN_DIR/p2p" << 'EOF'
#!/bin/bash
# OpenClaw P2P wrapper

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
P2P_DIR="$SCRIPT_DIR/../services/p2p"

python3 "$P2P_DIR/openclaw_p2p_service.py" "$@"
EOF

chmod +x "$BIN_DIR/p2p"

echo "✅ Created: $BIN_DIR/p2p"

# Install dependencies
echo ""
echo "📦 Installing Python dependencies..."

# Check for virtualenv
if [ ! -d "$OPENCLAW_DIR/venv" ]; then
    echo "  Creating virtual environment..."
    python3 -m venv "$OPENCLAW_DIR/venv"
fi

PYTHON_BIN="$OPENCLAW_DIR/venv/bin/python3"
PIP_BIN="$OPENCLAW_DIR/venv/bin/pip3"

echo "  Installing aiohttp, cryptography..."
$PIP_BIN install --quiet aiohttp cryptography python-zeroconf

# Test
echo ""
echo "🧪 Testing installation..."

# Test import
if PYTHONPATH="$SERVICE_DIR/p2p:$PYTHONPATH" $PYTHON_BIN -c "from p2p_core import BugPeer" 2>/dev/null; then
    echo "✅ p2p_core import OK"
else
    echo "❌ p2p_core import failed"
    exit 1
fi

if PYTHONPATH="$SERVICE_DIR/p2p:$PYTHONPATH" $PYTHON_BIN -c "from reputation_system import BugReputationSystem" 2>/dev/null; then
    echo "✅ reputation_system import OK"
else
    echo "❌ reputation_system import failed"
    exit 1
fi

# Create systemd service (optional, if running as systemd)
echo ""
if command -v systemctl &> /dev/null; then
    read -p "🔧 Install as systemd service? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cat > /tmp/openclaw-p2p.service << EOF
[Unit]
Description=OpenClaw P2P Service
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$OPENCLAW_DIR/services/p2p
ExecStart=$OPENCLAW_DIR/venv/bin/python3 openclaw_p2p_service.py start --config $OPENCLAW_DIR/config/p2p_config.toml
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

        echo "  Created systemd service file: /tmp/openclaw-p2p.service"
        echo "  To install, run:"
        echo "    sudo cp /tmp/openclaw-p2p.service /etc/systemd/system/"
        echo "    sudo systemctl daemon-reload"
        echo "    sudo systemctl enable openclaw-p2p.service"
        echo "    sudo systemctl start openclaw-p2p.service"
    fi
fi

# Finish
echo ""
echo "✅ Installation complete!"
echo ""
echo "Usage:"
echo "  # Start the service (manually)"
echo "  $OPENCLAW_DIR/bin/p2p start"
echo ""
echo "  # Or via systemd (if installed)"
echo "  sudo systemctl start openclaw-p2p"
echo ""
echo "  # Check status"
echo "  $OPENCLAW_DIR/bin/p2p status"
echo ""
echo "  # Send a query"
echo "  $OPENCLAW_DIR/bin/p2p query \"Your question\""
echo ""
echo "  # List peers"
echo "  $OPENCLAW_DIR/bin/p2p peers"
echo ""
echo "Files installed:"
echo "  - Service: $SERVICE_DIR/p2p/"
echo "  - Config:  $OPENCLAW_DIR/config/p2p_config.toml"
echo "  - Binary:  $BIN_DIR/p2p"
echo ""