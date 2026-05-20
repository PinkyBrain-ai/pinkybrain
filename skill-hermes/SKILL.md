---
name: pinkybrain
description: "PinkyBrain P2P Distributed AI Network — query models, manage nodes, sync memory, check status, route specialists via the PinkyBrain mesh."
triggers:
  - pinkybrain
  - p2p ai
  - mesh query
  - p2p network
  - p2p status
  - p2p memory
---

# PinkyBrain Skill 🐛🧠🐭

PinkyBrain is a **P2P distributed AI network** created by Bug 🐛 and Denis. It connects machines to share models, sync memory, and route queries intelligently across the mesh. This skill enables Hermes agents to use PinkyBrain as a client — querying AI models, reading distributed memory, checking mesh status, and routing prompts to the best specialist model.

## Architecture Overview

**Components:**
- **PinkyBrain v5.2** — P2P server (`pinkybrain_v5.py`)
- **Specialist Router** — Auto-detects prompt type, routes to best model (12 specialties)
- **Multi-LLM Executor** — 6 modes: single, vote, chain, fuse, compare, specialist
- **Model Registry** — Rich model catalog with SHA-256 verification
- **CRDT Memory** — Distributed memory sync via gossip protocol
- **Resource Guard** — Auto-pause sharing when CPU/RAM exceeds thresholds
- **Credit System** — Earn credits by sharing, spend by querying
- **Bandwidth Quota** — Monthly data caps (like a mobile plan)
- **Conversation Store** — Persistent encrypted conversations (private by default)
- **Network Sync** — Auto-discover peers, sync model catalog, Dynamic DNS
- **Tracker Client** — Public mesh discovery with Ed25519 signing
- **Web UI** — 9 languages, chat + share + network + config tabs

**Node names:** `bug` (port 8080), `pinky` (port 8081) — same `p2p_secret` connects them.

## Setup & Installation

```bash
# Clone and install
git clone https://github.com/PinkyBrain-ai/pinkybrain.git ~/PinkyBrain
cd ~/PinkyBrain
python3 setup.py --auto

# Or manual
pip install aiohttp psutil
python3 src/pinkybrain_v5.py bug

# Start as systemd service
systemctl --user enable --now pinkybrain
```

### Minimal Config (`~/.pinkybrain/config/bug.json`)

```json
{
  "node_name": "bug",
  "port": 8080,
  "p2p_secret": "shared-secret-here",
  "share_ai": true,
  "providers": {
    "ollama": {
      "type": "ollama",
      "host": "127.0.0.1",
      "port": 11434,
      "models": ["glm-5.1"],
      "enabled": true
    }
  },
  "peers": [
    {"name": "pinky", "host": "192.0.2.1", "port": 8081}
  ]
}
```

## API Reference (localhost:8080)

### Authentication

HMAC authentication is required for POST endpoints. Generate the signature using SHA-256 HMAC with your `p2p_secret`:

```bash
TIMESTAMP=$(date +%s)
SIGNATURE=$(echo -n "/api/query:${TIMESTAMP}" | openssl dgst -sha256 -hmac "your-secret" | awk '{print $NF}')

curl -X POST http://localhost:8080/api/query \
  -H "X-PinkyBrain-Auth: ${SIGNATURE}" \
  -H "X-PinkyBrain-Ts: ${TIMESTAMP}" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Hello","model":"glm-5.1:cloud"}'
```

**Important:** The HMAC path must match the endpoint path. For `/api/memory/set`, use `"memory/set:{TIMESTAMP}"` as the HMAC input.

### Endpoints

- **GET `/api/ping`** — Health check (no auth)
- **GET `/api/status`** — Node status, providers, peers, memory (no auth)
- **GET `/api/quota`** — All peer sharing quotas (no auth)
- **GET `/api/quota/{peer}`** — Specific peer quota (no auth)
- **GET `/api/memory/{key}`** — Read CRDT memory key (no auth)
- **POST `/api/memory/set`** — Write CRDT memory key (auth required)
- **POST `/api/memory/push`** — Push memory entries for sync (auth required)
- **POST `/api/query`** — Query AI models (auth required)
- **POST `/api/multi`** — Multi-LLM query (auth required)
- **GET `/api/specialties`** — List specialty schemas (no auth)
- **GET `/api/specialties/{name}/models`** — Best models for specialty (no auth)
- **POST `/api/brain/chain`** — Chain multiple queries (auth required)
- **GET `/api/peers`** — List connected peers (no auth)
- **GET `/api/capabilities`** — Node hardware capabilities (no auth)
- **GET `/api/score/{peer}`** — Gamified score tier (no auth)
- **GET `/api/discover`** — Zero-Config discovered peers (no auth)

### Query Examples

```bash
# Simple query
curl -s http://localhost:8080/api/query \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Explain quantum computing"}'

# Query with specialty routing
curl -s http://localhost:8080/api/query \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Write a Python web scraper","specialty":"code"}'

# Multi-model vote
curl -s http://localhost:8080/api/multi \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Best approach for microservices?","mode":"vote","models":["deepseek-v3.1:671b-cloud","glm-5.1:cloud"]}'

# Multi-model chain (A refines B)
curl -s http://localhost:8080/api/multi \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Translate this to Japanese","mode":"chain","models":["glm-5.1:cloud","deepseek-v3.1:671b-cloud"]}'

# Memory operations
curl -s http://localhost:8080/api/memory/set \
  -H "Content-Type: application/json" \
  -d '{"key":"project_notes","value":"PinkyBrain v5.2 released","ttl":86400}'

curl -s http://localhost:8080/api/memory/project_notes
```

## 12 Specialty Schemas

The Specialist Router auto-detects the type of prompt and routes it to the best model:

- **Code** — `python`, `function`, `debug`, `implement` → deepseek-v3.1:671b
- **Reasoning** — `analyze`, `explain`, `compare`, `evaluate` → deepseek-v3.1:671b
- **Creative** — `write`, `story`, `poem`, `creative` → glm-5.1:cloud
- **Math** — `calculate`, `equation`, `theorem`, `proof` → deepseek-v3.1:671b
- **Conversation** — casual chat, greetings → glm-5.1:cloud
- **General** — default fallback → glm-5.1:cloud
- **Multilingual** — `translate`, language detection → glm-5.1:cloud
- **Tool Use** — `api`, `curl`, `http` → qwen3-coder-next
- **Instruction** — step-by-step, how-to → glm-5.1:cloud
- **Science** — `research`, `hypothesis`, `experiment` → deepseek-v3.1:671b
- **Data** — `csv`, `json`, `parse`, `dataset` → deepseek-v3.1:671b
- **Security** — `encrypt`, `vulnerability`, `pentest` → deepseek-v3.1:671b

## 6 Multi-LLM Modes

- **Single** — One model responds (default)
- **Vote** — 3 models respond → best answer wins
- **Chain** — Model A → refines → Model B → final
- **Fuse** — 3 models → merged synthesis
- **Compare** — 2+ models side by side
- **Specialist** — Auto-detect specialty → best model per specialty

## CLI Commands

```bash
pinkybrain                    # Start interactive chat
pinkybrain -q "Hello"         # Single query
pinkybrain -m gpt-4o          # Use specific model
pinkybrain --ensemble         # Multi-model consensus
/status                        # Node status, uptime, peers
/peers                         # Connected peers and models
/models                        # Available AI models
/quota                         # Sharing quotas
/model <name>                  # Set default model
/ensemble <prompt>             # Multi-model consensus
/memory set/get                # Distributed memory
/history                       # Query history
/config                        # Current configuration
```

## Credit System Tiers

- **Free** — 100 credits/month (base allocation)
- **Contributor** — 200-500 credits/month (sharing models/GPU)
- **Power** — 500-2000 credits/month (major contributor)
- **Unlimited** — ∞ queries (score ≥ 80)

## Sharing Quotas (Score-based)

- Score <10 → 1 query/min
- Score <20 → 5 queries/min
- Score <40 → 20 queries/min
- Score <60 → 50 queries/min
- Score <80 → 100 queries/min
- Score ≥80 → 200 queries/min

## Key Files

- `src/pinkybrain_v5.py` — Main server (5000+ LOC)
- `src/brain_llm.py` — Core LLM orchestrator, P2P routing
- `src/model_specialist.py` — Specialty detection + multi-model execution
- `src/credit_system.py` — Credit-based query metering
- `src/bandwidth_quota.py` — Monthly bandwidth caps
- `src/resource_guard.py` — Auto-pause/resume mesh sharing
- `src/adaptive_scheduler.py` — Strategy selection (routing/sharding/RAID RAM)
- `src/conversation_store.py` — Persistent encrypted conversations
- `src/model_share_manager.py` — Bridge between private models and mesh
- `src/model_registry.py` — Rich model catalog
- `src/network_sync.py` — Peer discovery, Dynamic DNS, model sync
- `src/tracker_client.py` — Public mesh discovery, Ed25519 signing
- `src/pinkybrain_cli.py` — Interactive CLI client

## Pitfalls

- **HMAC Auth required** for POST endpoints — generate signature with SHA-256 HMAC using `p2p_secret`
- **Cloud models are NEVER shared** on the P2P mesh by default — only local models
- **share_ai: false** means connected to P2P but models stay private
- **Resource Guard** auto-pauses sharing when local user is active — this is by design
- **CRDT Memory** has key length limit (256 chars) and value limit (100KB)
- **Bandwidth Quota** defaults to 5GB/month — adjust for your connection
- Default ports: bug=8080, pinky=8081, memory=8084/8085, messenger=8082/8083
- `start.sh` loads `.env` file from script directory for secrets

## Our Team Config

- **Bug** 🐛 — port 8080, OpenClaw agent principal
- **Pinky** 🐭 — port 8081, OpenClaw agent on ThinkPad
- **Brain** 🧠 — Hermes agent, uses PinkyBrain via API as client

Brain queries PinkyBrain at `http://localhost:8080` (Bug's node) for AI model access, P2P mesh status, and distributed memory.