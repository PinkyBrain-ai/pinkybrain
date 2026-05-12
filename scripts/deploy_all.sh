#!/bin/bash
# 🚀 Script de Déploiement Complet - PinkyBrain v5.2
# Déploie et démarre les services sur Bug (WSL2) et Pinky (ThinkPad)

set -e

echo "=========================================="
echo "🚀 DÉPLOIEMENT COMPLET - PINKYBRAIN v5.2"
echo "=========================================="
echo ""

# =============================================================================
# DÉPLOIEMENT SUR BUG (WSL2)
# =============================================================================

echo "📦 [1/4] Déploiement sur Bug (WSL2)..."

WORKSPACE="/home/user/.openclaw/workspace"
NM_DIR="$WORKSPACE/PinkyBrain"

if [ ! -d "$NM_DIR" ]; then
    echo "❌ Répertoire PinkyBrain non trouvé sur Bug"
    exit 1
fi

echo "✅ Répertoire PinkyBrain trouvé"

if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 non installé sur Bug"
    exit 1
fi

echo "✅ Python 3 installé"

echo "📦 Installation des dépendances..."
cd "$NM_DIR"
pip3 install -r requirements.txt --break-system-packages -q 2>/dev/null || pip3 install -r requirements.txt -q
echo "✅ Dépendances installées"

# =============================================================================
# DÉPLOIEMENT SUR PINKY (ThinkPad)
# =============================================================================

echo ""
echo "📦 [2/4] Déploiement sur Pinky (ThinkPad)..."

PINKY_HOST="100.79.20.105"
PINKY_USER="kamizool"

if ! ssh -o ConnectTimeout=5 "$PINKY_USER@$PINKY_HOST" "echo OK" 2>/dev/null; then
    echo "❌ Impossible de se connecter à Pinky"
    exit 1
fi

echo "✅ Connexion à Pinky OK"

echo "📦 Copie du projet sur Pinky..."
scp -r "$NM_DIR" "$PINKY_USER@$PINKY_HOST:~/PinkyBrain" 2>/dev/null || true
echo "✅ Projet copié"

echo "📦 Installation des dépendances sur Pinky..."
ssh "$PINKY_USER@$PINKY_HOST" "cd ~/PinkyBrain && pip3 install -r requirements.txt --break-system-packages -q 2>/dev/null || pip3 install -r requirements.txt -q"
echo "✅ Dépendances installées"

# =============================================================================
# DÉMARRAGE SUR BUG
# =============================================================================

echo ""
echo "🚀 [3/4] Démarrage sur Bug..."

echo "🛑 Arrêt des services existants..."
pkill -f "pinkybrain_v5.py" 2>/dev/null || true
sleep 2

echo "🌐 Démarrage de PinkyBrain..."
cd "$NM_DIR"
nohup python3 src/pinkybrain_v5.py > logs/pinkybrain.log 2>&1 &
PINKYBRAIN_PID=$!
echo $PINKYBRAIN_PID > logs/pinkybrain.pid
echo "✅ PinkyBrain démarré (PID: $PINKYBRAIN_PID)"

sleep 3

# =============================================================================
# DÉMARRAGE SUR PINKY
# =============================================================================

echo ""
echo "🚀 [4/4] Démarrage sur Pinky..."

echo "🛑 Arrêt des services existants..."
ssh "$PINKY_USER@$PINKY_HOST" "pkill -f 'pinkybrain_v5.py' 2>/dev/null || true"
sleep 2

echo "🌐 Démarrage de PinkyBrain sur Pinky..."
ssh "$PINKY_USER@$PINKY_HOST" "cd ~/PinkyBrain && nohup python3 src/pinkybrain_v5.py > logs/pinkybrain.log 2>&1 & echo \$! > logs/pinkybrain.pid"
echo "✅ PinkyBrain démarré sur Pinky"

sleep 3

# =============================================================================
# RÉSUMÉ
# =============================================================================

echo ""
echo "=========================================="
echo "✅ DÉPLOIEMENT TERMINÉ !"
echo "=========================================="
echo ""
echo "Bug:  PID $(cat $NM_DIR/logs/pinkybrain.pid 2>/dev/null || echo 'N/A')"
echo "Pinky: PID $(ssh $PINKY_USER@$PINKY_HOST 'cat ~/PinkyBrain/logs/pinkybrain.pid 2>/dev/null || echo N/A')"
echo ""
echo "💡 curl http://localhost:8080/api/status"
echo "🛑 kill \$(cat $NM_DIR/logs/pinkybrain.pid)"
echo ""