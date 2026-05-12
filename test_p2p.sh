#!/bin/bash
# Test the P2P system with multiple peers

set - e

echo "🐛 Bug P2P Multi-Peer Test"
echo "======================="
echo ""

# Cleanup function
cleanup() {
    echo ""
    echo "🧹 Cleaning up..."
    kill $PEER1_PID $PEER2_PID $PEER3_PID 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start 3 peers on different ports
echo "🚀 Starting 3 peers..."

# Bootstrap list includes all peers
BOOTSTRAP="127.0.0.1:8001,127.0.0.1:8002,127.0.0.1:8003"

# Peer 1
cd ~/.openclaw/workspace/bug
python3 p2p_core.py \
    --host 127.0.0.1 \
    --port 8001 \
    --model qwen3:8b \
    --model coding \
    --bootstrap "$BOOTSTRAP" &
PEER1_PID=$!
echo "  Peer 1 (8001) - Models: qwen3:8b, coding"

sleep 2

# Peer 2
python3 p2p_core.py \
    --host 127.0.0.1 \
    --port 8002 \
    --model glm-4.7 \
    --model creative \
    --bootstrap "$BOOTSTRAP" &
PEER2_PID=$!
echo "  Peer 2 (8002) - Models: glm-4.7, creative"

sleep 2

# Peer 3
python3 p2p_core.py \
    --host 127.0.0.1 \
    --port 8003 \
    --model phi3-mini \
    --model translation \
    --bootstrap "$BOOTSTRAP" &
PEER3_PID=$!
echo "  Peer 3 (8003) - Models: phi3-mini, translation"

echo ""
echo "⏳ Waiting 5 seconds for peer discovery..."
sleep 5

echo ""
echo "📊 Peer Status:"
echo "----------------"

for port in 8001 8002 8003; do
    echo ""
    echo "Peer on port $port:"
    curl -s http://127.0.0.1:$port/ | jq '.'
done

echo ""
echo ""
echo "🔍 Distributed Query Test:"
echo "--------------------------"

# Send a query from peer 1
echo "Sending query from Peer 1: 'Explain the P2P architecture'"

curl -s http://127.0.0.1:8001/ -X POST \
  -H "Content-Type: application/json" \
  -d '{"query":"Explain the P2P architecture"}' | jq '.'

echo ""
echo ""
echo "✅ Test complete. Peers are gossiping and responding."
echo ""
echo "Press Ctrl+C to stop all peers."

# Wait indefinitely
wait