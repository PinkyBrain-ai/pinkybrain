#!/bin/bash
# 🚀 Script de Démarrage Rapide - PinkyBrain v5.2

echo "=========================================="
echo "🚀 DÉMARRAGE RAPIDE - PINKYBRAIN v5.2"
echo "=========================================="
echo ""

WORKSPACE="/home/user/.openclaw/workspace"
NM_DIR="$WORKSPACE/PinkyBrain"

# Arrêter les services existants
echo "🛑 Arrêt des services existants..."
pkill -f "pinkybrain_v5.py" 2>/dev/null || true
sleep 2

# Démarrer PinkyBrain
echo "🌐 Démarrage de PinkyBrain..."
cd "$NM_DIR"
python3 src/pinkybrain_v5.py &
PINKYBRAIN_PID=$!
echo $PINKYBRAIN_PID > logs/pinkybrain.pid
echo "✅ PinkyBrain démarré (PID: $PINKYBRAIN_PID)"

sleep 3

echo ""
echo "=========================================="
echo "✅ PINKYBRAIN DÉMARRÉ !"
echo "=========================================="
echo ""
echo "📊 PID: $PINKYBRAIN_PID"
echo "💡 TEST: curl http://localhost:8080/api/status"
echo "📝 LOGS: tail -f $NM_DIR/logs/pinkybrain.log"
echo "🛑 ARRÊT: kill $PINKYBRAIN_PID"
echo ""