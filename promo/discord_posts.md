# 🧠 PinkyBrain v5.2 — Discord Posts

## Post 1: General announcement

Hey! Just released **PinkyBrain v5.2** — a P2P distributed AI network that connects machines running LLMs into a mesh.

What's new:
- **Model Registry** — rich model catalog with SHA-256 verification, Ed25519 signatures, schema validation
- **Network Sync** — auto-discover peers, sync model catalog, identify missing models
- **Cloud = private by default** — API keys never shared on the mesh unless you explicitly opt-in
- **Full security audit** — zero personal data in the public repo
- **Specialist Router** — auto-detect prompt type, route to the best model
- **6 multi-LLM modes** — vote, chain, fuse, compare, specialist routing

No server, no accounts, no tracking. Runs on a Core 2 Duo. MIT license.

⭐ https://github.com/PinkyBrain-ai/pinkybrain

---

## Post 2: Self-hosting community

Running local LLMs on multiple machines? PinkyBrain v5.2 connects them into a P2P mesh with:

- Auto-discovery via Tailscale
- CRDT memory sync (no conflicts)
- Model catalog with verified integrity
- Cloud models private by default
- **Specialist Router** — code, math, creative, reasoning… auto-routed to the best model

Your API keys, your rules. Opt-in sharing with clear warnings.

```bash
git clone https://github.com/PinkyBrain-ai/pinkybrain.git
python3 src/pinkybrain_v5.py --config mynode.json
```

---

## Post 3: Security-focused

Built PinkyBrain v5.2 with security in mind:

✅ SHA-256 hash verified on catalog load
✅ Ed25519 signatures for P2P catalog sharing
✅ Schema validation: no HTML/JS, no path traversal
✅ Zero personal data in public repo (IPs, secrets, usernames all removed)
✅ Specialist Router — 12 specialties, auto-route prompts to the best model
✅ Config templates only — real configs in .gitignore
✅ Cloud API keys private by default, opt-in with explicit consent

⭐ https://github.com/PinkyBrain-ai/pinkybrain
🌐 **Website & Live Demo:** https://PinkyBrain-ai.github.io/pinkybrain/
