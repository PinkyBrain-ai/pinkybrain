---
name: pinkybrain
description: "PinkyBrain P2P distributed AI network — Plug & Play Sidekick mode. OpenClaw auto-discovers PinkyBrain API and routes queries through the P2P mesh."
metadata:
  openclaw:
    requires:
      bins: [python3]
      env:
        - PINKYBRAIN_CONFIG
    install:
      - id: git-clone
        kind: shell
        cmd: "git clone https://github.com/PinkyBrain-ai/pinkybrain.git ${PINKYBRAIN_PATH:-$HOME/PinkyBrain}"
    auto-discover:
      - kind: http
        method: GET
        url: "http://localhost:${PINKYBRAIN_PORT:-8080}/api/status"
        expect:
          status: 200
          body_contains: "PinkyBrain"
        on_found:
          set_env:
            PINKYBRAIN_URL: "http://localhost:${PINKYBRAIN_PORT:-8080}"
          notify: "🌐 PinkyBrain detected on localhost! P2P AI available."
---

# PinkyBrain Skill — Sidekick Mode 🐛🤝🌐

PinkyBrain as a **Sidekick** for OpenClaw agents: zero-config P2P AI augmentation.

## The Two Modes

### 🖥️ Standalone Mode
```bash
python3 start.sh --config config/bug.json
```
PinkyBrain runs independently. OpenClaw skill can query it.

### 🔌 Sidekick Mode (Plug & Play)
When PinkyBrain is running locally (or on the network), OpenClaw **auto-discovers** it:
1. On heartbeat, check `localhost:8080/api/status`
2. If found → P2P AI is available, no config needed
3. Agent can route queries to any model on the mesh
4. Memory syncs across all agents automatically

**That's it.** Install PinkyBrain, start it, and OpenClaw becomes instantly smarter.

## What the Agent Can Do

### Query Models on the Mesh
```
Ask Bug: "Ask the P2P network about quantum entanglement"
```
→ Bug queries PinkyBrain, which routes to the best available model (local or peer)

### Distributed Memory
```
Ask Bug: "Remember on the mesh that the server port is 8080"
```
→ Bug writes to PinkyBrain CRDT memory, synced to all peers

### Status Check
```
Ask Bug: "How's the P2P network?"
```
→ Bug checks `/api/status`, `/api/capabilities`, `/api/score/bug`

### Model Negotiation
```
Ask Bug: "Run llama-3-70b on the network"
```
→ PinkyBrain routes to the GPU peer automatically

## Sidekick Auto-Discovery

The skill checks these locations in order:
1. `PINKYBRAIN_URL` env var (explicit override)
2. `http://localhost:8080` (default Bug port)
3. `http://localhost:8081` (default Pinky port)
4. Zero-Config discovered peers (mDNS)
5. Tailscale peers in config

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | Node status, peers, models, uptime |
| `/api/query` | POST | Send AI query (requires auth) |
| `/api/memory/{key}` | GET | Read CRDT memory key |
| `/api/memory/set` | POST | Write CRDT memory key |
| `/api/peers` | GET | List connected peers |
| `/api/capabilities` | GET | Node hardware capabilities ( |
| `/api/score/{peer}` | GET | Gamified score tier ( |
| `/api/discover` | GET | Zero-Config discovered peers ( |
| `/api/update` | GET | Check for updates ( |
| `/api/daemon` | GET | Daemon/systray status ( |

## Config

Minimal config for Sidekick mode:
```json
{
  "node_name": "bug",
  "port": 8080,
  "p2p_secret": "your-secret-here-change-me",
  "share_ai": true,
  "peers": [
    {"name": "pinky", "host": "192.0.2.1", "port": 8081}
  ]
}
```

Or just start it and let Zero-Config discover peers automatically .