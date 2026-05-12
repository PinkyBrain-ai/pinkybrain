# Changelog

All notable changes to PinkyBrain will be documented in this file.

## [5.1.0] - 2026-05-06

### Added
- 🎯 **Model Specialist System** — Spécialités et sélection multi-LLM
  - `ModelSpecialty` enum: code, reasoning, creative, math, conversation, general, multilingual, vision, audio, embedding, tool_use, instruction
  - `ModelProfile` — profil complet par modèle (spécialités, forces, limites, taille, vitesse, qualité)
  - `SpecialistRouter` — routeur intelligent qui auto-detecte la spécialité depuis le prompt
  - `MultiModelExecutor` — exécution multi-modèles avec 6 modes: single, vote, chain, fuse, compare, specialist
  - 9 profils par défaut (glm-5.1, deepseek-v3.1, qwen3-coder, qwen3:8b, llama3.1, mistral, codellama, gpt-4o, claude-sonnet-4)
  - Auto-détection par mots-clés avec scoring par spécificité
  - Sélection forcée par spécialité, par modèle, ou par multiple spécialités

### New API Endpoints
- `GET /api/specialties` — Liste toutes les spécialités et leurs modèles
- `GET /api/specialties/{name}/models` — Modèles pour une spécialité
- `POST /api/multi` — Requête multi-modèles (vote, chain, fuse, compare, specialist)

### Enhanced
- `POST /api/query` — Nouveaux paramètres: `specialty`, `models`, `specialties` pour le routage par spécialité
- Auto-détection: "Write a Python scraper" → route vers deepseek (code), "Explain physics" → glm (reasoning)
- Fuzzy matching: "deepseek" → "deepseek-v3.1:671b-cloud"

### Tests
- 67 nouveaux tests pour model_specialist (auto-detection, sélection, routing, multi-model executor)
- Total: 518 tests passing

## [5.0.0] - 2026-05-05

### Added
- 📡 **mDNS Zero-Config Discovery** — `ZeroConfigDiscovery` class: UDP broadcast + multicast for automatic LAN peer discovery. No IP config needed.
- 🖥️ **GPU/CPU Model Negotiation** — `NodeCapabilities` auto-detects GPU (nvidia-smi), CPU cores, RAM. `ModelNegotiator` routes large models (70B) to GPU peers, small models to CPU.
- 🤝 **Gamified Score Dashboard** — `GamifiedScore` with 7 visual tiers: 🌱 Seedling → 🥉 Bronze → 🥈 Silver → 🥇 Gold → 💎 Platinum → 💠 Diamond → 🌟 Celestial. Progress bars in web dashboard.
- 🔄 **Auto-Update Checker** — `AutoUpdater` checks GitHub releases on startup + daily. `/api/update` endpoint.
- 🖥️ **Systray Daemon** — `SystrayDaemon` for PID management and background mode. `/api/daemon` endpoint.
- 🔌 **Sidekick Mode for OpenClaw** — `/api/agent` endpoint returns everything an AI agent needs (models, capabilities, score). `/api/agent/query` routes through GPU/CPU negotiation.

### New API Endpoints
- `GET /api/capabilities` — Node hardware capabilities + peer capabilities
- `GET /api/score/{peer}` — Gamified score tier for a peer
- `GET /api/discover` — Zero-Config discovered peers
- `GET /api/update` — Check for PinkyBrain updates
- `GET /api/daemon` — Daemon/systray status
- `GET /api/agent` — Sidekick info for OpenClaw
- `POST /api/agent/query` — Sidekick query with GPU/CPU routing

### Dashboard
- Added Sharing Score section with tier badges and progress bars
- Added Hardware Capabilities section (GPU/CPU/RAM per node)
- Added Zero-Config Discovered Peers section

## [4.0.0] - 2026-05-04

### Added
- 🔌 **WebSocket Temps Réel** — Bidirectional WebSocket (`/ws`) with typed messages (query, memory_sync, memory_update, notification, peer_discovery, status). Auto-reconnect, WS heartbeat, ping/pong. HTTP REST API remains available (retrocompatible).

- 🔐 **Auth Renforcée (Decentralized)** — Ed25519 node identity (self-generated, no registry). Challenge-response auth with nonce + timestamp (anti-replay). Web of Trust (PGP-like transitive trust). Rate limiting per node (token bucket). Stealth mode (hidden node, no discovery, trusted peers only). Users don't need accounts — auth is between nodes.

- 🧠 **Mémoire Sync P2P** — CRDT-based conflict-free replicated memory. Gossip protocol for propagation. Vector clocks for event ordering. Last-write-wins with metadata (author, timestamp, node_id). API: `/api/memory/sync`, `/api/memory/push`, `/api/memory/pull`. Share AI models via `share_ai: true` config or `pinkybrain share` CLI.

- 🧹 **Clean Architecture** — Removed dead code (`_archive_old`, `archive`, `output`, `__pycache__`). Updated requirements (minimal: aiohttp, psutil, PyNaCl optional). Fast startup, low memory. brain_llm stays async, non-blocking.

- 📝 **Docs** — `docs/AUTH_DESIGN.md` with complete auth design. `DONATIONS.md` with BTC address.

### Changed
- Main file renamed: `src/pinkybrain_v5.py` → `src/pinkybrain_v5.py`
- VERSION: 3.3.0 → 4.0.0
- README.md rewritten for v4.0
- requirements.txt cleaned up (PyJWT removed, PyNaCl optional)

### Removed
- `_archive_old/` directory
- `archive/` directory
- `output/` directory
- `__pycache__` directories
- PyJWT hard dependency (auth now Ed25519-based)

## [3.5.0] - 2026-04-02

### Added
- 🤖 **PinkyBrainBug v3.5 - Autonomie Complète**
  - Auto-Support - Répond automatiquement aux questions utilisateurs
  - Auto-Monitoring - Surveillance système temps réel (CPU, RAM, Disque, Réseau)
  - Auto-Healing - Détection et réparation automatique des problèmes
  - Auto-Optimization - Optimisation automatique des performances
  - Auto-Upgrade - Mises à jour automatiques avec sauvegardes
  - PinkyBrainBug Autonomy - Mode autonome orchestrant tous les modules

- ✨ **Knowledge Base** - Base de connaissances pour auto-support
  - Documentation intégrée (guides, exemples, FAQ)
  - Recherche sémantique
  - Réponses contextuelles

- 📊 **Monitoring Production-Ready**
  - Métriques système en temps réel
  - Health checks complets
  - Détection de problèmes automatique
  - Logs structurés avec rotation

- 🩹 **Auto-Healing System**
  - Détection automatique des problèmes
  - Actions de réparation préconfigurées
  - Journalisation des réparations
  - Stats et historique

- 📈 **Auto-Optimization**
  - Analyse des métriques système
  - Suggestions d'optimisation
  - Application automatique
  - Historique des optimisations

- 🔄 **Auto-Upgrade**
  - Vérification automatique des mises à jour GitHub
  - Sauvegardes automatiques avant upgrade
  - Installation silencieuse
  - Rollback en cas d'échec

- 🧪 **Tests Complètes v3.5**
  - Tests auto-support
  - Tests auto-monitoring
  - Tests auto-healing
  - Tests auto-optimization
  - Tests auto-upgrade

- 📋 **Documentation Utilisateur Pinky**
  - Plan de test utilisateur
  - Rapport de test Pinky (100% réussite)
  - Benchmarks comparatifs Bug vs Pinky

### Changed
- 🔄 Version 3.0.0 → 3.5.0
- 🔄 README mis à jour avec modules d'autonomie
- 🔄 requirements_autonomy.txt ajouté

### Tested
- ✅ 100% des tests passés sur Pinky (ThinkPad Ubuntu, 3.2GB RAM)
- ✅ Benchmarks: 29.8ms latence moyenne (100% succès)
- ✅ Aucun bug bloquant
- ✅ Installation simple et fonctionnelle

### Performance
- Pinky (3.2GB RAM): 29.8ms latence
- Bug (plus RAM): 13.8ms latence
- Différence acceptable et prévisible

---

## [3.0.0] - 2026-04-02

### Added
- ✨ **True P2P Network** - Système P2P 100% décentralisé
  - DHT (Distributed Hash Table)
  - Gossip Protocol
  - Kademlia Routing
  - Bootstrap Nodes
  - Store & Get
  - Broadcast

- ✨ **PinkyBrain v3.0** - Réseau P2P distribué
  - Multi-model Ensembling
  - Model Sharing (P2P distribué)
  - Reputation System
  - Web Interface
  - API REST
  - Query History Persistence
  - Multiple Export Formats (JSON, CSV, HTML)
  - Dynamic Model Routing
  - Auto-Selection

- ✨ **PinkyBrainBug v3.0** - Système auto-émancipé
  - Auto-Emancipation complète
  - Self-Awareness
  - Self-Improvement
  - Self-Learning
  - Self-Direction
  - Self-Exploration
  - Distributed Memory
  - UX Monitor
  - Daemon Mode

- 🔍 **Production Enhancement Module (NOUVEAU)**
  - Logging Structuré (JSON avec rotation)
  - Métriques de monitoring (Counters, Gauges, Histograms)
  - Health Checks actifs avec alerting
  - Circuit Breaker pattern
  - Retry logic avec backoff exponentiel
  - Rate Limiting (Token Bucket)
  - Sybil Resistance
  - Cache intelligent avec TTL et LRU
  - Model Versioning avec rollback
  - Streaming Responses (SSE)
  - Batch Requests
  - Documentation de l'API documentation

- ✨ **Network Specialization Module**
  - Service Discovery (LAN)
  - Load Balancing (Round Robin, Least Connections, Weighted)
  - Failover Management
  - TLS Security

- ✨ **Deployment Module**
  - Auto-Deployment
  - Auto-Scaling
  - Rolling Updates
  - Auto-Healing
  - Backups

- ✨ **Internet Capable Module**
  - Rendezvous Server (Discovery Internet)
  - NAT Traversal
  - Internet Discovery
  - Secure Client (TLS)
  - Multi-Network Manager (LAN/WAN/Internet)

- ✨ **Interactive Interface**
  - CLI complète
  - Commandes pour PinkyBrain et PinkyBrainBug
  - Mode ensemble
  - Memory search
  - Status monitoring

- ✨ **Documentation Complète**
  - Guide Interface Interactive
  - Guide Réseau & Déploiement
  - Guide Internet Capable
  - Guide True P2P
  - Guide Production Enhancement 🔍
  - Examples d'utilisation

- ✨ **Tests Unitaires**
  - Tests PinkyBrain
  - Tests PinkyBrainBug
  - Tests P2P Network
  - Tests Production Enhancement
  - CI/CD GitHub Actions

- ✨ **Docker Support**
  - Containerfile
  - Support de conteneurisation complet

### Changed
- 🔄 Refactorisation complète pour architecture décentralisée
- 🔄 Optimisation des performances
- 🔄 Séparation claire entre PinkyBrain et PinkyBrainBug

### Fixed
- 🐛 Problèmes de mémoire
- 🐛 Latence élevée
- 🐛 Timeout sur les requêtes

### Removed
- ❌ Rendezvous Server centralisé (remplacé par True P2P)
- ❌ Dépendances non nécessaires

---

## [0.1.0] - 2026-03-27

### Added
- ✨ Première version publique
- ✨ P2P Network basic
- ✨ Multi-model Ensembling
- ✨ Reputation System

---

## [Unreleased]

### Planned
- 🚀 Tests unitaires complets
- 🚀 CI/CD GitHub Actions
- 🚀 Support de conteneurisation
- 🚀 Déploiement d'orchestration
- 🚀 Web Dashboard avancé
- 🚀 Monitoring temps réel
- 🚀 Alerting
- 🚀 Analytics

---

**Pour les versions futures, voir [Roadmap](README.md#-roadmap)**