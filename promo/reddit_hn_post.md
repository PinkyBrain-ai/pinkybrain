# 🧠 PinkyBrain v5.2 — Reddit / HackerNews

## Title: PinkyBrain — P2P Distributed AI Network with Model Registry and Cloud Privacy

I've been building a way for my local LLM machines to share queries and sync memory without a central server. It's called PinkyBrain and v5.2 just shipped.

**What it does:**
Connect machines running Ollama into a P2P mesh. Share compute, sync memory, route queries. No server, no accounts, no cloud dependency.

**What's new in v5.2:**

- **Model Registry** — Every model gets a rich catalog card (architecture, quantization, context window, capabilities). SHA-256 verified at load time, optional Ed25519 signatures for P2P sharing.
- **Network Sync** — When a node joins, it automatically discovers peers, syncs the model catalog, and identifies models available on the mesh but not locally.
- **Cloud = private by default** — Cloud model API keys are NEVER shared on the mesh. Period. You can opt in with explicit `force=True`, but you get a clear warning that other nodes will use YOUR key.
- **Security audit** — Zero personal data (IPs, secrets, usernames) in the public repo. Config templates only.
- **Specialist Router** — 12 specialties (code, math, creative, reasoning…), auto-detect prompt type and route to the best model
- **6 multi-LLM modes** — vote, chain, fuse, compare, specialist routing

**Tech stack:**
- Pure Python, asyncio + aiohttp
- CRDT distributed memory
- Ed25519 + HMAC auth
- WebSocket real-time sync
- 4 dependencies total

**Hardware:**
I'm running two nodes 24/7 — one on a recycled Fujitsu Esprimo (Core 2 Duo, 2.5GB RAM) and one on a Samsung with NVMe. Yes, it actually runs on a Core 2 Duo.

```bash
git clone https://github.com/PinkyBrain-ai/pinkybrain.git
python3 src/pinkybrain_v5.py --config mynode.json
```

MIT licensed. Feedback welcome.

Repository: https://github.com/PinkyBrain-ai/pinkybrain
🌐 **Website & Live Demo:** https://PinkyBrain-ai.github.io/pinkybrain/
