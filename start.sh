#!/bin/bash
# PinkyBrain Start — loads .env and starts the node

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

# Load .env if exists
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

NODE=${1:-pinky}
cd "$SCRIPT_DIR/src"

if [ "$2" = "cli" ]; then
    exec python3 pinkybrain_cli.py "$NODE"
fi

exec python3 pinkybrain_v5.py "$NODE"