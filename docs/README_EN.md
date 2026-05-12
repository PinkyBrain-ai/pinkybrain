# 🌐 PinkyBrain v5

[![Version](https://img.shields.io/badge/version-5.2.0-blue.svg)](https://github.com/PinkyBrain-ai/pinkybrain)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![P2P](https://img.shields.io/badge/P2P-Decentralized-green.svg)](https://github.com/PinkyBrain-ai/pinkybrain)
[![E2E Encrypted](https://img.shields.io/badge/E2E-Encrypted-orange.svg)](https://github.com/PinkyBrain-ai/pinkybrain)

**Distributed P2P AI network with public mesh. Share compute, share models, stay private. v5.2: Multi-LLM specialist routing, Network Sync, Credit System.**

> 🌍 [Documentation en français](./README_FR.md) | 🌐 [Documentación en español](./README_ES.md) | 🌐 [中文文档](./README_ZH.md) | 🌐 [हिन्दी](./README_HI.md) | 🌐 [العربية](./README_AR.md) | 🌐 [Português](./README_PT.md) | 🌐 [日本語](./README_JA.md)

---

## ✨ What is PinkyBrain?

PinkyBrain connects machines into a peer-to-peer AI network. Your machines talk to each other, share compute and models — no cloud dependency, no central server, no single point of failure.

**v5 adds the public mesh:** join a global network of shared CPU, RAM, GPU and AI models. Your private network stays private. The mesh is an additional layer you opt into.

**In short:** Like BitTorrent, but for AI. You share compute, you get access to 50+ models. Your data stays on your machine. E2E encrypted. Always.

---

## 🆕 What's New in v5

| Feature | Description |
|---------|-------------|
| 🔓 **Private P2P Network** | Your machines, your secret. `p2p_secret` auth, Ed25519 identity. |
| 🌐 **Public Mesh** | Share CPU/RAM/GPU and models with the world. Opt-in. |
| 🔒 **Network Isolation** | Private and public on separate ports, separate auth. Zero data leakage. |
| 🛡️ **E2E Encryption** | End-to-end encryption for distributed inference. No one can read your queries. |
| 🛡️ **Resource Guard** | Auto-pause sharing when your PC is busy. Your machine, your rules. |
| 🧠 **Adaptive Scheduler** | Routing → sharding → RAID RAM. Automatically adapts to network size. |
| 💬 **Conversation Store** | Persistent memory. Never lose a conversation again. |
| 📂 **shared_models/** | A dedicated folder — the only bridge between private and public. |
| 📊 **Contribution Quotas** | Share more, get more. 0 sharing = 1 req/5min. Generous sharing = 20+ req/min. |
| 🖥️ **Desktop Interface** | Chat, Share, Network, Config — 4 tabs, zero terminal needed. |
| 🔧 **4 Deploy Modes** | Service, App, Sidekick, Plugin — one binary, four lifestyles. |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- [Ollama](https://ollama.ai) running locally (or a cloud model endpoint)
- (Optional) [Tailscale](https://tailscale.com) for automatic peer discovery

### Install & Run

```bash
# Clone
git clone https://github.com/PinkyBrain-ai/pinkybrain.git
cd PinkyBrain

# Run
python3 src/pinkybrain_v5.py

# Or with a config file
python3 src/pinkybrain_v5.py --config config/bug.json
```

### Connect Your Network

```json
{
  "node_name": "mynode",
  "private": {
    "p2p_secret": "your-shared-secret-here",
    "peers": [
      {"name": "other-node", "host": "192.168.1.100", "port": 8080}
    ]
  },
  "public_mesh": {
    "enabled": false
  }
}
```

That's it. Your private network works out of the box. Want to join the mesh? Set `"enabled": true` and choose what to share.

---

## 🔑 Key Features

### 🤖 Multi-LLM Providers
- **Ollama** (local) — backward compatible default
- **OpenAI** — GPT-4o, GPT-4o-mini, etc.
- **Anthropic** — Claude models
- **OpenAI-compatible** — LM Studio, vLLM, any custom API
- **Local models shared across P2P** — cloud models are private by default, never shared on the mesh without explicit opt-in

### 🔌 WebSocket Real-Time Communication
- Bidirectional WebSocket on `/ws` endpoint
- Typed messages: `query`, `memory_sync`, `memory_update`, `ping/pong`, `auth`
- Auto-reconnect with exponential backoff

### 🔐 Decentralized Authentication
- **Ed25519 identity** — each node generates its own keypair
- **HMAC shared secret** — simpler alternative for private networks
- **Web of Trust** — nodes vouch for each other, transitive trust
- **Rate limiting** per node (token bucket algorithm)
- **Stealth mode** — hidden node, trusted peers only

### 🧠 Distributed Memory (CRDT)
- **Conflict-free replicated data types** — no merge conflicts, ever
- **Gossip protocol** — changes propagate automatically
- **Vector clocks** — causal ordering of events
- **TTL support** — entries expire automatically

### 🤖 AI Model Routing
- **Local models first** — queries go to local Ollama when possible
- **Cloud models on demand** — `model:cloud` syntax, stays private on your node
- **Peer failover** — route to a peer if local model is busy
- **Ensemble consensus** — query multiple models, return the best answer
- **Circuit breakers** — stop hammering dead peers

---

## 🌐 Public Mesh

### Dual Network Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Node (You)                        │
│                                                     │
│  ┌─────────────┐          ┌──────────────────┐     │
│  │ Private Net  │          │   Public Mesh     │     │
│  │ p2p_secret   │          │   tracker         │     │
│  │ ┌─────────┐  │          │ ┌──────────────┐ │     │
│  │ │ Bug     │◄─┼──P2P────┼─┤ Node #42     │ │     │
│  │ └─────────┘  │          │ │ 2GB RAM      │ │     │
│  │ ┌─────────┐  │          │ │ 30% CPU      │ │     │
│  │ │ Pinky   │◄─┼──P2P────┼─┤ Ollama local │ │     │
│  │ └─────────┘  │          │ └──────────────┘ │     │
│  └─────────────┘          │ ┌──────────────┐ │     │
│                           │ │ Node #789    │ │     │
│  ┌─────────────────┐      │ │ 8GB RAM      │ │     │
│  │ Resource Guard   │      │ │ RTX 4090     │ │     │
│  │ max_ram: 2GB    │      │ │ 4 models     │ │     │
│  │ max_cpu: 30%    │      │ └──────────────┘ │     │
│  │ gpu_share: off  │      │                  │     │
│  │ priority: local  │      │  Tracker:        │     │
│  └─────────────────┘      │  announce/caps    │     │
│                           └──────────────────┘     │
└─────────────────────────────────────────────────────┘
```

Your **private network** (p2p_secret) is completely isolated from the **public mesh** (Ed25519 + Web of Trust). Different ports, different auth, zero data leakage.

### Contribution-Based Quotas

| Contribution | Score | Public Quota |
|---|---|---|
| Nothing shared | 0 | 1 query / 5 min |
| 1 model shared | +20 | 5 queries / min |
| 2+ models shared | +30 | 20 queries / min |
| 2GB RAM shared | +20 | +10 queries / min |
| GPU shared | +20 | +20 queries / min |
| 24h uptime | +10 | +5 queries / min |

**Share more = access more.** But even with zero sharing, you still get 1 query every 5 minutes. No one is blocked.

---

## 🛡️ Resource Guard

Your machine comes first. The Resource Guard monitors CPU/RAM and automatically pauses public sharing when you're busy.

```python
class ResourceGuard:
    def can_accept_request(self) -> bool:
        cpu_usage = psutil.cpu_percent(interval=0.1)
        ram_usage = psutil.virtual_memory().percent
        
        if self.priority == "local_first":
            if cpu_usage > 70 or ram_usage > 85:
                return False  # User is busy
        
        if cpu_usage > self.max_cpu + 40:
            return False
        
        return True
```

**Local priority ALWAYS wins.** If your machine is busy, it refuses public requests. No exceptions.

---

## 🧠 Adaptive Scheduler

The network decides the best strategy based on how many peers are available. No version numbers, no manual modes.

| Available Peers | Strategy | Capability |
|---|---|---|
| 1–3 | Simple routing | Full models on one machine |
| 4–10 | Partial sharding | Models split into 2–4 chunks |
| 11–50 | Full sharding + 2× replication | Pipeline parallel, redundancy |
| 50+ | Distributed RAID RAM | Virtual RAM disk, 3× replication, async prefetch |

**Transitions happen automatically and without interruption.** A peer joins → the scheduler redistributes. A peer leaves → replicas take over. You never notice.

---

## 💾 Persistent Conversation Store

Your conversations stay on YOUR machine. Period.

- **Auto-save** — Every message saved locally. No "save" button needed.
- **Resume** — Open PinkyBrain tomorrow, your conversations are there.
- **Search** — Find any past conversation by keyword, date, model, or tag.
- **Export** — Markdown, JSON, plain text. Your data, your format.
- **Privacy** — Conversations NEVER leave your machine unless you explicitly sync them via private P2P.
- **Encryption** — Optional local encryption. Even disk access can't read them.
- **No tracking** — No analytics, no training on your data.

### Privacy Levels

| Level | What happens | Use case |
|---|---|---|
| **private** (default) | Stays local, never synced | Personal, sensitive |
| **synced** | Synced via private P2P only | Between your devices |
| **shared** | Shared with specific peers | Collaboration |
| **public** | Opt-in mesh knowledge base | Community knowledge |

**Default is private. Always.**

---

## 🔒 E2E Encryption

When you query the mesh, your data is end-to-end encrypted:

1. Your question is encrypted with a session key
2. Each peer in the pipeline decrypts only its own chunk, computes, re-encrypts
3. Only YOU can decrypt the final answer

**What each peer can see:**
| Data | Visible? | Why |
|---|---|---|
| Your original question | ❌ No | Encrypted with your session key |
| The final answer | ❌ No | Encrypted with your session key |
| Its own chunk's input/output tensors | ✅ Yes | Needed for computation |
| Other chunks' data | ❌ No | Encrypted with other peers' keys |

**This isn't a promise. It's cryptography.** Even if every peer were compromised, they couldn't read your data without your session key — which exists only on your machine, only for the duration of the request.

---

## 📂 shared_models/ — The Private/Public Boundary

A dedicated folder that is the **only interface** between your models and the public mesh.

```
~/.pinkybrain/
├── conversations/        → 🔒 Private (never shared)
├── memory/               → 🔒 Private (never shared)
├── config/               → 🔒 Private (never shared)
├── shared_models/        → 🌐 Sharing zone (visible to mesh)
│   ├── glm-5.1/          → Symlink to ~/.ollama/models/glm-5.1
│   ├── llama3/           → Copy or symlink
│   └── mistral/          → Copy or symlink
└── ollama/               → 🔒 Private Ollama storage
```

```bash
pinkybrain share glm-5.1    # Share a model (creates symlink)
pinkybrain unshare glm-5.1  # Stop sharing (removes symlink only)
pinkybrain shared            # List shared models
```

**The mesh NEVER reads outside `shared_models/`.** Unsharing is instant — the mesh loses access the moment the symlink is removed.

**Cloud models (OpenAI, Anthropic, etc.) are NEVER shared on the mesh by default.** They use YOUR API keys and YOUR credits. Sharing a cloud model requires explicit `force=True` and shows a clear warning. Local Ollama models are the ones naturally shared on the mesh.

---

## 🖥️ Desktop Interface

4 tabs, zero terminal needed:

- **💬 Chat** — Query AI models, conversation history, search, export
- **📊 Share** — CPU/RAM/GPU sliders, model sharing toggles, contribution stats
- **🔒 Network** — Private peers, mesh nodes, isolation verification
- **⚙️ Config** — Node name, mesh settings, storage, auto-pause thresholds

Works in any browser at `localhost:8080`. Installable as PWA for desktop/mobile.

---

## 🔧 4 Deployment Modes

| Mode | Use Case | Interface |
|---|---|---|
| 🔧 **Service** | Servers, VPS, headless | API only (systemd/Docker) |
| 🖥️ **App** | Full desktop experience | GUI with 4 tabs |
| 📍 **Sidekick** | Daily use, minimal | System tray icon + mini-chat |
| 🔌 **Plugin** | Integrated in your workflow | VS Code, browser, Obsidian, terminal |

```bash
pinkybrain serve          # Service (headless)
pinkybrain app            # Application (GUI)
pinkybrain sidekick       # Sidekick (system tray)
pinkybrain plugin --vscode  # Plugin (VS Code)
```

All 4 modes share the same core. One binary, four lifestyles.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                   PinkyBrain Core                    │
│  ┌────────────┐ ┌──────────────┐ ┌────────────────┐ │
│  │ Resource   │ │ Adaptive     │ │ Conversation   │ │
│  │ Guard      │ │ Scheduler    │ │ Store          │ │
│  └────────────┘ └──────────────┘ └────────────────┘ │
│  ┌────────────┐ ┌──────────────┐ ┌────────────────┐ │
│  │ Model Share│ │ E2E          │ │ Brain LLM      │ │
│  │ Manager    │ │ Encryption   │ │ Router         │ │
│  └────────────┘ └──────────────┘ └────────────────┘ │
└──────────────────────┬──────────────────────────────┘
                       │
              ┌────────┴────────┐
              │   API Layer     │
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
  "node_name": "my-laptop",
  "private": {
    "p2p_secret": "my-secret-network",
    "peers": [
      {"name": "my-server", "host": "192.0.2.2", "port": 8080}
    ],
    "share_ai": true
  },
  "public_mesh": {
    "enabled": true,
    "tracker_url": "https://tracker.pinkybrain.ai",
    "max_ram_share_mb": 2048,
    "max_cpu_percent": 30,
    "gpu_share": false,
    "models_share": [],  /* Empty = share only local Ollama models. Cloud models NEVER shared on mesh by default */
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

### Network Ports

| Service | Port | Network | Auth |
|---|---|---|---|
| Private API | 8080/8081 | Private (p2p_secret) | HMAC + Ed25519 |
| Messenger | 8082/8083 | Private (p2p_secret) | HMAC |
| CRDT Memory | 8084/8085 | Private (p2p_secret) | HMAC |
| Public Mesh | 8090 | Public | Ed25519 Web of Trust |
| Tracker | — | Public (HTTPS) | Signed Ed25519 key |

---

## 🔒 Security & Privacy

- **Private network:** Encrypted with p2p_secret (unchanged from v4)
- **Public mesh:** Ed25519 identity + TLS for transport
- **E2E encryption:** Queries encrypted end-to-end through distributed inference
- **No data leakage** between private and public networks
- **Public requests sandboxed:** no access to private memory
- **Resource Guard:** auto-pause sharing when your PC is busy
- **Stealth mode:** share compute but stay hidden on the tracker
- **Zero logging:** public mesh peers never store queries or responses

---

## 📡 API Reference

### REST Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/ping` | No | Health check |
| GET | `/api/status` | No | Node status, peers, memory stats |
| GET | `/api/memory/{key}` | No | Read a memory entry |
| POST | `/api/memory/set` | Yes | Write a memory entry |
| POST | `/api/memory/push` | Yes | Push memory entries (sync) |
| POST | `/api/query` | Yes | Query AI models |
| POST | `/api/brain/chain` | Yes | Chain multiple AI queries |
| POST | `/api/brain/consensus` | Yes | Multi-model consensus |
| POST | `/api/models/{name}/share` | Yes | Share a model to mesh |
| POST | `/api/models/{name}/unshare` | Yes | Stop sharing a model |
| GET | `/api/conversations` | Yes | List conversations |
| GET | `/api/conversations/{id}` | Yes | Load a conversation |
| GET | `/api/resources/status` | Yes | CPU/RAM/GPU status |
| POST | `/api/network/mesh/join` | Yes | Join the public mesh |
| POST | `/api/network/mesh/leave` | Yes | Leave the public mesh |

### Authentication

All write endpoints require HMAC authentication:

```bash
TIMESTAMP=$(date +%s)
SIGNATURE=$(echo -n "/api/query:${TIMESTAMP}" | openssl dgst -sha256 -hmac "your-secret" | awk '{print $NF}')

curl -X POST http://localhost:8080/api/query \
  -H "X-PinkyBrain-Auth: ${SIGNATURE}" \
  -H "X-PinkyBrain-TS: ${TIMESTAMP}" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Hello","model":"glm-5.1:cloud"}'
```

---

## 🔄 Migration Path (v4 → v5)

1. v5 is **backward compatible** with v4
2. Private network config works exactly as before
3. `public_mesh` section is **optional** — disabled by default
4. Existing v4 nodes can talk to v5 nodes on the private network
5. Public mesh is **opt-in:** set `public_mesh.enabled = true`

---

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch: `git checkout -b feature/amazing`
3. Commit your changes: `git commit -m 'Add amazing feature'`
4. Push to the branch: `git push origin feature/amazing`
5. Open a Pull Request

---

## 📄 License

MIT License — see [LICENSE](../LICENSE) for details.

---

## 🐛 About

Built by Bug 🐛 and Denis Houet — a small bug in the machine and a human who believes in symbiosis, not hierarchy.

**Donations (BTC):** `bc1qhpm800k35jfpwsnkepp7u8q9uruyvd3nycrh6x`

No mining. No premium tier. No hidden costs. Just free, open, distributed AI. **Symbiosis, not hierarchy.**