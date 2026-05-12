# 🧠 PinkyBrain v5.2 — Launch Thread

## 🧵 Thread Twitter/X (FR)

1/
🧠 PinkyBrain v5.2 est là !

Un réseau P2P distribué pour l'IA. Pas de serveur central. Pas de compte. Vos machines parlent directement.

⭐ github.com/PinkyBrain-ai/pinkybrain

2/
🔧 Ce qui est nouveau en v5.2 :

▸ Model Registry — catalogue de modèles avec fiches détaillées, hash SHA-256 anti-tampering, signatures Ed25519
▸ Network Sync — DNS dynamique auto, découverte des nœuds, sync du catalogue mesh
▸ Cloud = privé par défaut — vos API keys restent à vous, partageable uniquement en opt-in

3/
🛡️ Sécurité d'abord :

▸ Hash SHA-256 vérifié au chargement du catalogue
▸ Signatures Ed25519 optionnelles pour le mesh P2P
▸ Validation du schéma : pas de HTML/JS, pas de path traversal
▸ Aucune donnée perso dans le repo public (audit complet)

🎯 Specialist Router :
▸ 12 spécialités (code, math, créatif, raisonnement…)
▸ Auto-détection du type de prompt → route vers le meilleur modèle
▸ 6 modes multi-LLM : vote, chaîne, fusion, comparaison, spécialiste

4/
🏗️ Architecture décentralisée :

▸ WebSocket sync en temps réel entre nœuds
▸ Mémoire distribuée CRDT (pas de merge conflicts)
▸ Auth Ed25519 + HMAC décentralisée
▸ Auto-discovery via Tailscale
▸ IA locale d'abord, cloud à la demande, failover entre pairs

5/
⚡ Léger comme une plume :

▸ 0.16s au démarrage
▸ 17MB de RAM
▸ 4 dépendances
▸ License MIT
▸ Tourne sur un Core 2 Duo avec 2.5GB de RAM (si, si)

6/
📦 Quick start :

git clone https://github.com/PinkyBrain-ai/pinkybrain.git
cd pinkybrain
python3 src/pinkybrain_v5.py --config mynode.json

▸ Model Registry avec catalogue JSON
▸ Cloud models privés par défaut
▸ Mesh discovery automatique

⭐ github.com/PinkyBrain-ai/pinkybrain

7/
🌐 Rejoignez le mesh :

Pinky & Bug — deux nœuds qui tournent 24/7 sur du matériel recyclé. Un Fujitsu Esprimo Core 2 Duo et un Samsung avec NVMe.

Pas de data center. Pas de cloud bill. Juste du P2P.

⭐ Star le repo : github.com/PinkyBrain-ai/pinkybrain

#PinkyBrain #P2P #AI #OpenSource #SelfHosted #Decentralized
🌐 **Website & Live Demo:** https://PinkyBrain-ai.github.io/pinkybrain/
