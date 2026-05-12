# 🧠 PinkyBrain v5.2 — Launch Post

## Show PinkyBrain: P2P Distributed AI Network

**PinkyBrain v5.2** — connect your local AI machines into a peer-to-peer mesh.

### What it is
A lightweight Python framework that connects machines running Ollama (or any LLM provider) into a distributed network. No central server, no accounts, no tracking.

### What's new in v5.2

**Model Registry**
- Rich catalog cards for each model: architecture, quantization, context window, capabilities
- SHA-256 hash verification on catalog load (anti-tampering)
- Optional Ed25519 signatures for P2P catalog sharing
- Schema validation: no unknown keys, no HTML/JS, size limits

**Network Sync**
- When a node connects, it automatically discovers peers via tracker + mDNS
- Dynamic DNS for known nodes with staleness detection (30d stale, 90d purged)
- Syncs model catalog from the mesh, identifies missing models
- Reports which models are available on the mesh but not locally

**Cloud = Private by Default**
- Cloud models (API-based) are NEVER shared on the mesh without explicit opt-in
- `share_model()` refuses cloud/wishlist models by default
- `force=True` override available but shows clear warning about API key exposure
- Mesh catalog excludes cloud models unless explicitly requested

**Security Audit**
- Zero personal data in the public repo (no IPs, no secrets, no usernames)
- Config templates only — real configs in .gitignore
- SHA-256 + Ed25519 catalog integrity verification

**Specialist Router**
- 12 specialty schemas (code, reasoning, creative, math, conversation, general, multilingual, tool use, instruction, science, data, security)
- Auto-detect prompt type → route to the best model
- 6 multi-LLM modes: single, vote, chain, fuse, compare, specialist

### Tech
- Pure Python, asyncio + aiohttp
- 4 dependencies
- 0.16s startup, 17MB RAM
- CRDT distributed memory
- Ed25519 + HMAC auth
- MIT license

### Hardware
Two nodes running 24/7 on recycled hardware:
- Pinky: Fujitsu Esprimo, Core 2 Duo, 2.5GB RAM
- Bug: Samsung, NVMe, 32GB RAM

### Quick start
```bash
git clone https://github.com/PinkyBrain-ai/pinkybrain.git
cd pinkybrain
python3 src/pinkybrain_v5.py --config mynode.json
```

⭐ Star the repo: https://github.com/PinkyBrain-ai/pinkybrain
🌐 **Website & Live Demo:** https://PinkyBrain-ai.github.io/pinkybrain/
