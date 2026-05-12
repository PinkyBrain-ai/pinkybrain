# 🌐 PinkyBrain v5

[![Version](https://img.shields.io/badge/version-5.2.0-blue.svg)](https://github.com/PinkyBrain-ai/pinkybrain)
[![License : MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![P2P](https://img.shields.io/badge/P2P-D%C3%A9centralis%C3%A9-green.svg)](https://github.com/PinkyBrain-ai/pinkybrain)
[![Chiffrement E2E](https://img.shields.io/badge/E2E-Chiffr%C3%A9-orange.svg)](https://github.com/PinkyBrain-ai/pinkybrain)

**Réseau IA P2P distribué avec mesh public. Partagez du calcul, partagez des modèles, restez privé. v5.2 : Routage spécialiste multi-LLM, Network Sync, Credit System.**

> 🌍 [English](./README_EN.md) | 🌐 [Documentación en español](./README_ES.md) | 🌐 [中文文档](./README_ZH.md) | 🌐 [हिन्दी](./README_HI.md) | 🌐 [العربية](./README_AR.md) | 🌐 [Português](./README_PT.md) | 🌐 [日本語](./README_JA.md)

---

## ✨ Qu'est-ce que PinkyBrain ?

PinkyBrain connecte vos machines en réseau IA pair-à-pair. Vos machines discutent entre elles, partagent calcul et modèles — pas de dépendance cloud, pas de serveur central, pas de point de défaillance unique.

**v5 ajoute le mesh public :** rejoignez un réseau mondial de CPU, RAM, GPU et modèles IA partagés. Votre réseau privé reste privé. Le mesh est un layer additionnel que vous activez volontairement.

**En résumé :** Comme BitTorrent, mais pour l'IA. Vous partagez du calcul, vous accédez à 50+ modèles. Vos données restent sur votre machine. Chiffré de bout en bout. Toujours.

---

## 🆕 Quoi de neuf en v5

| Fonctionnalité | Description |
|---|---|
| 🔓 **Réseau P2P privé** | Vos machines, votre secret. Authentification p2p_secret, identité Ed25519. |
| 🌐 **Mesh public** | Partagez CPU/RAM/GPU et modèles avec le monde. Optionnel. |
| 🔒 **Isolation réseau** | Privé et public sur des ports séparés, auth séparée. Zéro fuite de données. |
| 🛡️ **Chiffrement E2E** | Chiffrement de bout en bout pour l'inférence distribuée. Personne ne peut lire vos requêtes. |
| 🛡️ **Resource Guard** | Mise en pause automatique du partage quand votre PC est occupé. Votre machine, vos règles. |
| 🧠 **Adaptive Scheduler** | Routage → sharding → RAID RAM. S'adapte automatiquement à la taille du réseau. |
| 💬 **Conversation Store** | Mémoire persistante. Plus jamais de page blanche. |
| 📂 **shared_models/** | Un dossier dédié — la seule passerelle entre privé et public. |
| 📊 **Quotas de contribution** | Partagez plus, accédez plus. 0 partage = 1 req/5min. Partage généreux = 20+ req/min. |
| 🖥️ **Interface Desktop** | Chat, Partage, Réseau, Config — 4 onglets, zéro terminal requis. |
| 🔧 **4 modes de déploiement** | Service, App, Sidekick, Plugin — un binaire, quatre modes de vie. |

---

## 🚀 Démarrage rapide

### Prérequis
- Python 3.12+
- [Ollama](https://ollama.ai) en local (ou un endpoint cloud)
- (Optionnel) [Tailscale](https://tailscale.com) pour la découverte automatique de pairs

### Installation et lancement

```bash
# Cloner
git clone https://github.com/PinkyBrain-ai/pinkybrain.git
cd PinkyBrain

# Lancer
python3 src/pinkybrain_v5.py

# Ou avec un fichier de config
python3 src/pinkybrain_v5.py --config config/bug.json
```

### Connecter votre réseau

```json
{
  "node_name": "mon-nœud",
  "private": {
    "p2p_secret": "votre-secret-partagé-ici",
    "peers": [
      {"name": "autre-nœud", "host": "192.168.1.100", "port": 8080}
    ]
  },
  "public_mesh": {
    "enabled": false
  }
}
```

C'est tout. Votre réseau privé fonctionne immédiatement. Pour rejoindre le mesh, passez `"enabled": true` et choisissez quoi partager.

---

## 🔑 Fonctionnalités clés

### 🤖 Multi-fournisseurs LLM
- **Ollama** (local) — compatible par défaut
- **OpenAI** — GPT-4o, GPT-4o-mini, etc.
- **Anthropic** — modèles Claude
- **Compatible OpenAI** — LM Studio, vLLM, toute API personnalisée
- Modèles de tous les fournisseurs partagés en P2P et sur le mesh

### 🔌 Communication WebSocket temps réel
- WebSocket bidirectionnel sur le endpoint `/ws`
- Messages typés : `query`, `memory_sync`, `memory_update`, `ping/pong`, `auth`
- Reconnexion automatique avec backoff exponentiel

### 🔐 Authentification décentralisée
- **Identité Ed25519** — chaque nœud génère sa propre paire de clés
- **Secret partagé HMAC** — alternative plus simple pour les réseaux privés
- **Toile de confiance** — les nœuds se portent garantis mutuellement, confiance transitive
- **Limitation de débit** par nœud (algorithme token bucket)
- **Mode furtif** — nœud caché, pairs de confiance uniquement

### 🧠 Mémoire distribuée (CRDT)
- **Types de données répliquées sans conflit** — jamais de conflits de fusion
- **Protocole de rumeur** — les changements se propagent automatiquement
- **Horloges vectorielles** — ordonnancement causal des événements
- **Support TTL** — les entrées expirent automatiquement

### 🤖 Routage IA
- **Modèles locaux d'abord** — les requêtes vont à Ollama local quand possible
- **Modèles cloud à la demande** — syntaxe `model:cloud`
- **Basculement vers les pairs** — route vers un pair si le modèle local est occupé
- **Consensus d'ensemble** — interroge plusieurs modèles, retourne la meilleure réponse
- **Disjoncteurs** — arrête de solliciter les pairs défaillants

---

## 🌐 Mesh public

### Architecture double réseau

```
┌─────────────────────────────────────────────────────┐
│                    Nœud (Vous)                       │
│                                                     │
│  ┌─────────────┐          ┌──────────────────┐     │
│  │ Réseau Privé │          │   Mesh Public     │     │
│  │ p2p_secret   │          │   tracker         │     │
│  │ ┌─────────┐  │          │ ┌──────────────┐ │     │
│  │ │ Bug     │◄─┼──P2P────┼─┤ Nœud #42     │ │     │
│  │ └─────────┘  │          │ │ 2 Go RAM     │ │     │
│  │ ┌─────────┐  │          │ │ 30% CPU      │ │     │
│  │ │ Pinky   │◄─┼──P2P────┼─┤ Ollama local │ │     │
│  │ └─────────┘  │          │ └──────────────┘ │     │
│  └─────────────┘          │ ┌──────────────┐ │     │
│                           │ │ Nœud #789    │ │     │
│  ┌─────────────────┐      │ │ 8 Go RAM     │ │     │
│  │ Resource Guard   │      │ │ RTX 4090     │ │     │
│  │ max_ram: 2Go    │      │ │ 4 modèles    │ │     │
│  │ max_cpu: 30%    │      │ └──────────────┘ │     │
│  │ gpu_share: off   │      │                  │     │
│  │ priority: local   │      │  Tracker :       │     │
│  └─────────────────┘      │  annonce/caps     │     │
│                           └──────────────────┘     │
└─────────────────────────────────────────────────────┘
```

Votre **réseau privé** (p2p_secret) est complètement isolé du **mesh public** (Ed25519 + toile de confiance). Ports séparés, auth séparée, zéro fuite de données.

### Quotas basés sur la contribution

| Contribution | Score | Quota public |
|---|---|---|
| Rien partagé | 0 | 1 requête / 5 min |
| 1 modèle partagé | +20 | 5 requêtes / min |
| 2+ modèles partagés | +30 | 20 requêtes / min |
| 2 Go RAM partagés | +20 | +10 requêtes / min |
| GPU partagé | +20 | +20 requêtes / min |
| 24h de disponibilité | +10 | +5 requêtes / min |

**Plus vous partagez, plus vous accédez.** Même avec zéro partage, vous avez 1 requête toutes les 5 minutes. Personne n'est bloqué.

---

## 🛡️ Resource Guard

Votre machine passe en premier. Le Resource Guard surveille CPU/RAM et met automatiquement en pause le partage public quand vous êtes occupé.

```python
class ResourceGuard:
    def can_accept_request(self) -> bool:
        cpu_usage = psutil.cpu_percent(interval=0.1)
        ram_usage = psutil.virtual_memory().percent
        
        if self.priority == "local_first":
            if cpu_usage > 70 or ram_usage > 85:
                return False  # L'utilisateur est occupé
        
        if cpu_usage > self.max_cpu + 40:
            return False
        
        return True
```

**La priorité locale gagne TOUJOURS.** Si votre machine est occupée, elle refuse les requêtes publiques. Sans exception.

---

## 🧠 Adaptive Scheduler

Le réseau choisit la meilleure stratégie selon le nombre de pairs disponibles. Pas de numéros de version, pas de modes manuels.

| Pairs disponibles | Stratégie | Capacité |
|---|---|---|
| 1–3 | Routage simple | Modèles entiers sur une machine |
| 4–10 | Sharding partiel | Modèles découpés en 2–4 fragments |
| 11–50 | Sharding complet + réplication 2× | Pipeline parallèle, redondance |
| 50+ | RAID RAM distribué | Disque virtuel en RAM, réplication 3×, préchargement asynchrone |

**Les transitions se font automatiquement et sans interruption.** Un pair rejoint → le scheduler redistribue. Un pair part → les réplicas prennent le relais. Vous ne remarquez rien.

---

## 💬 Conversation Store persistant

Vos conversations restent sur VOTRE machine. Point final.

- **Sauvegarde automatique** — Chaque message est sauvegardé localement. Pas de bouton « sauvegarder ».
- **Reprise** — Ouvrez PinkyBrain demain, vos conversations sont là.
- **Recherche** — Trouvez n'importe quelle conversation par mot-clé, date, modèle ou tag.
- **Export** — Markdown, JSON, texte brut. Vos données, votre format.
- **Confidentialité** — Les conversations ne quittent JAMAIS votre machine sauf si vous les synchronisez via P2P privé.
- **Chiffrement** — Chiffrement local optionnel. Même l'accès au disque ne permet pas de les lire.
- **Aucun tracking** — Pas d'analytics, pas d'entraînement sur vos données.

### Niveaux de confidentialité

| Niveau | Ce qui se passe | Cas d'usage |
|---|---|---|
| **privé** (défaut) | Reste local, jamais synchronisé | Personnel, sensible |
| **synchronisé** | Sync via P2P privé uniquement | Entre vos appareils |
| **partagé** | Partagé avec des pairs spécifiques | Collaboration |
| **public** | Contribution opt-in au mesh | Savoir communautaire |

**Par défaut : privé. Toujours.**

---

## 🔒 Chiffrement E2E

Quand vous interrogez le mesh, vos données sont chiffrées de bout en bout :

1. Votre question est chiffrée avec une clé de session
2. Chaque pair du pipeline déchiffre uniquement son propre chunk, calcule, rechiffre
3. Seul VOUS pouvez déchiffrer la réponse finale

**Ce que chaque pair peut voir :**
| Donnée | Visible ? | Pourquoi |
|---|---|---|
| Votre question originale | ❌ Non | Chiffrée avec votre clé de session |
| La réponse finale | ❌ Non | Chiffrée avec votre clé de session |
| Les tenseurs d'entrée/sortie de son chunk | ✅ Oui | Nécessaire pour le calcul |
| Les données des autres chunks | ❌ Non | Chiffrées avec les clés des autres pairs |

**Ce n'est pas une promesse. C'est de la cryptographie.** Même si tous les pairs du mesh étaient compromis, ils ne pourraient pas lire vos données sans votre clé de session — qui n'existe que sur votre machine, le temps de la requête.

---

## 📂 shared_models/ — La frontière privé/public

Un dossier dédié qui est la **seule interface** entre vos modèles et le mesh public.

```
~/.pinkybrain/
├── conversations/        → 🔒 Privé (jamais partagé)
├── memory/               → 🔒 Privé (jamais partagé)
├── config/               → 🔒 Privé (jamais partagé)
├── shared_models/        → 🌐 Zone de partage (visible au mesh)
│   ├── glm-5.1/          → Lien symbolique vers ~/.ollama/models/glm-5.1
│   ├── llama3/           → Copie ou lien symbolique
│   └── mistral/          → Copie ou lien symbolique
└── ollama/               → 🔒 Stockage Ollama privé
```

```bash
pinkybrain share glm-5.1    # Partager un modèle (crée un lien symbolique)
pinkybrain unshare glm-5.1  # Arrêter le partage (supprime uniquement le lien)
pinkybrain shared            # Lister les modèles partagés
```

**Le mesh ne lit JAMAIS en dehors de `shared_models/`.** Arrêter le partage est instantané — le mesh perd l'accès dès que le lien est supprimé.

**Les modèles cloud (OpenAI, Anthropic, etc.) ne sont JAMAIS partagés sur le mesh par défaut.** Ils utilisent VOS clés API et VOS crédits. Partager un modèle cloud nécessite un `force=True` explicite et affiche un avertissement clair. Seuls les modèles Ollama locaux sont naturellement partagés sur le mesh.

---

## 🖥️ Interface Desktop

4 onglets, zéro terminal :

- **💬 Chat** — Interrogez des modèles IA, historique des conversations, recherche, export
- **📊 Partage** — Sliders CPU/RAM/GPU, toggles de partage de modèles, stats de contribution
- **🔒 Réseau** — Pairs privés, nœuds du mesh, vérification d'isolation
- **⚙️ Config** — Nom du nœud, paramètres mesh, stockage, seuils de mise en pause

Fonctionne dans n'importe quel navigateur sur `localhost:8080`. Installable en PWA pour desktop/mobile.

---

## 🔧 4 modes de déploiement

| Mode | Cas d'usage | Interface |
|---|---|---|
| 🔧 **Service** | Serveurs, VPS, headless | API uniquement (systemd/Docker) |
| 🖥️ **App** | Expérience desktop complète | GUI avec 4 onglets |
| 📍 **Sidekick** | Usage quotidien, discret | Icône dans la barre système + mini-chat |
| 🔌 **Plugin** | Intégré dans votre workflow | VS Code, navigateur, Obsidian, terminal |

```bash
pinkybrain serve          # Service (headless)
pinkybrain app            # Application (GUI)
pinkybrain sidekick       # Sidekick (barre système)
pinkybrain plugin --vscode  # Plugin (VS Code)
```

Les 4 modes partagent le même cœur. Un binaire, quatre modes de vie.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Cœur PinkyBrain                    │
│  ┌────────────┐ ┌──────────────┐ ┌────────────────┐ │
│  │ Resource   │ │ Adaptive     │ │ Conversation   │ │
│  │ Guard      │ │ Scheduler    │ │ Store          │ │
│  └────────────┘ └──────────────┘ └────────────────┘ │
│  ┌────────────┐ ┌──────────────┐ ┌────────────────┐ │
│  │ Model Share│ │ Chiffrement  │ │ Brain LLM      │ │
│  │ Manager    │ │ E2E          │ │ Routeur        │ │
│  └────────────┘ └──────────────┘ └────────────────┘ │
└──────────────────────┬──────────────────────────────┘
                       │
              ┌────────┴────────┐
              │   Couche API    │
              │ (aiohttp + WS)  │
              └────────┬────────┘
                       │
     ┌─────────────────┼─────────────────┐
     │                 │                 │
┌────┴─────┐   ┌──────┴──────┐   ┌──────┴──────┐
│ Service   │   │ App/Sidekick│   │ Plugin     │
│ (headless)│   │ (Web UI)    │   │ (extension) │
└──────────┘   └─────────────┘   └─────────────┘
```

---

## ⚙️ Configuration

```json
{
  "node_name": "mon-portable",
  "private": {
    "p2p_secret": "mon-réseau-secret",
    "peers": [
      {"name": "mon-serveur", "host": "192.0.2.2", "port": 8080}
    ],
    "share_ai": true
  },
  "public_mesh": {
    "enabled": true,
    "tracker_url": "https://tracker.pinkybrain.ai",
    "max_ram_share_mb": 2048,
    "max_cpu_percent": 30,
    "gpu_share": false,
    "models_share": [],  /* Vide = partage uniquement les modèles locaux Ollama. Les modèles cloud ne sont JAMAIS partagés sur le mesh par défaut */
    "priority": "local_first",
    "bandwidth_limit_kbps": 5000,
    "contribution_score": 0
  },
  "providers": {
    "ollama": {
      "type": "ollama",
      "host": "127.0.0.1",
      "port": 11434,
      "models": ["glm-5.1"],
      "enabled": true
    }
  }
}
```

### Ports réseau

| Service | Port | Réseau | Auth |
|---|---|---|---|
| API privée | 8080/8081 | Privé (p2p_secret) | HMAC + Ed25519 |
| Messagerie | 8082/8083 | Privé (p2p_secret) | HMAC |
| Mémoire CRDT | 8084/8085 | Privé (p2p_secret) | HMAC |
| Mesh public | 8090 | Public | Ed25519 toile de confiance |
| Tracker | — | Public (HTTPS) | Clé Ed25519 signée |

---

## 🔒 Sécurité et confidentialité

- **Réseau privé :** chiffré avec p2p_secret (inchangé depuis v4)
- **Mesh public :** identité Ed25519 + TLS pour le transport
- **Chiffrement E2E :** requêtes chiffrées de bout en bout lors de l'inférence distribuée
- **Aucune fuite de données** entre réseau privé et mesh public
- **Requêtes publiques sandboxées :** aucun accès à la mémoire privée
- **Resource Guard :** mise en pause automatique du partage quand votre PC est occupé
- **Mode furtif :** partagez du calcul mais restez caché sur le tracker
- **Zéro log :** les pairs du mesh ne stockent ni requêtes ni réponses

---

## 📡 Référence API

### Endpoints REST

| Méthode | Chemin | Auth | Description |
|---------|--------|------|-------------|
| GET | `/api/ping` | Non | Vérification de santé |
| GET | `/api/status` | Non | État du nœud, pairs, stats mémoire |
| GET | `/api/memory/{key}` | Non | Lire une entrée mémoire |
| POST | `/api/memory/set` | Oui | Écrire une entrée mémoire |
| POST | `/api/memory/push` | Oui | Pousser des entrées mémoire (sync) |
| POST | `/api/query` | Oui | Interroger des modèles IA |
| POST | `/api/brain/chain` | Oui | Enchaîner des requêtes IA |
| POST | `/api/brain/consensus` | Oui | Consensus multi-modèles |
| POST | `/api/models/{name}/share` | Oui | Partager un modèle au mesh |
| POST | `/api/models/{name}/unshare` | Oui | Arrêter le partage d'un modèle |
| GET | `/api/conversations` | Oui | Lister les conversations |
| GET | `/api/conversations/{id}` | Oui | Charger une conversation |
| GET | `/api/resources/status` | Oui | État CPU/RAM/GPU |
| POST | `/api/network/mesh/join` | Oui | Rejoindre le mesh public |
| POST | `/api/network/mesh/leave` | Oui | Quitter le mesh public |

### Authentification

Tous les endpoints en écriture nécessitent une authentification HMAC :

```bash
TIMESTAMP=$(date +%s)
SIGNATURE=$(echo -n "/api/query:${TIMESTAMP}" | openssl dgst -sha256 -hmac "votre-secret" | awk '{print $NF}')

curl -X POST http://localhost:8080/api/query \
  -H "X-PinkyBrain-Auth: ${SIGNATURE}" \
  -H "X-PinkyBrain-TS: ${TIMESTAMP}" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Bonjour","model":"glm-5.1:cloud"}'
```

---

## 🔄 Migration (v4 → v5)

1. v5 est **rétrocompatible** avec v4
2. La config du réseau privé fonctionne exactement comme avant
3. La section `public_mesh` est **optionnelle** — désactivée par défaut
4. Les nœuds v4 existants peuvent communiquer avec les nœuds v5 sur le réseau privé
5. Le mesh public est **opt-in :** mettez `public_mesh.enabled = true`

---

## 🤝 Contribuer

1. Forkez le dépôt
2. Créez votre branche : `git checkout -b feature/amazing`
3. Commitez vos changements : `git commit -m 'Add amazing feature'`
4. Poussez : `git push origin feature/amazing`
5. Ouvrez une Pull Request

---

## 📄 Licence

Licence MIT — voir [LICENSE](../LICENSE) pour les détails.

---

## 🐛 À propos

Construit par Bug 🐛 et Denis Houet — un petit bug dans la machine et un humain qui croit en symbiose, pas en hiérarchie.

**Dons (BTC) :** `bc1qhpm800k35jfpwsnkepp7u8q9uruyvd3nycrh6x`

Pas de minage. Pas de tier premium. Pas de coûts cachés. Juste de l'IA libre, ouverte et distribuée. **Symbiose, pas hiérarchie.**