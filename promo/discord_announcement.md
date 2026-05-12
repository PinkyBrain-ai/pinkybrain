# 🧠 PinkyBrain v5.2 — Discord Announcement

## For AI / self-hosting / P2P Discord servers:

---

Hey everyone! 👋

Just released **PinkyBrain v5.2** — a lightweight P2P distributed AI network.

**What:** Connect your machines running Ollama into a peer-to-peer network. Share compute, sync memory, route AI queries across nodes.

**Why:** No central server. No accounts. No premium tier. No mining. Your machines talk directly.

**What's new in v5.2:**
- **Model Registry** — rich model catalog with SHA-256 hash verification, Ed25519 signatures, schema validation
- **Network Sync** — automatic DNS, node discovery on connect, mesh catalog sync
- **Cloud = private by default** — API keys never shared on the mesh unless you explicitly opt-in
- **Specialist Router** — auto-detect prompt type (code, math, creative…) and route to the best model
- **6 multi-LLM modes** — vote, chain, fuse, compare, specialist
- **Full security audit** — zero personal data in the public repo

**How it works:**
- WebSocket real-time sync between nodes
- CRDT-based distributed memory (no merge conflicts)
- Ed25519 + HMAC decentralized auth
- Auto-discovery via Tailscale
- Local AI models first, cloud on demand, peer failover

**Quick start:**
```bash
git clone https://github.com/PinkyBrain-ai/pinkybrain.git
cd pinkybrain
python3 src/pinkybrain_v5.py --config mynode.json
```

0.16s startup, 17MB RAM, 4 dependencies. MIT license. Runs on a Core 2 Duo.

⭐ https://github.com/PinkyBrain-ai/pinkybrain
🌐 **Website & Live Demo:** https://PinkyBrain-ai.github.io/pinkybrain/
