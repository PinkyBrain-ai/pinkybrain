# 🔐 PinkyBrain Auth Design

## Overview

PinkyBrain uses a **decentralized auth model**. There is no central server, no CA, no registry. Authentication is between **nodes** (peers in the P2P network), not between end users. Users don't need accounts.

---

## Identity Model

Each node generates its own **Ed25519 keypair** on first run. Its identity IS its public key. No registration, no central authority.

- **Node identity = Ed25519 public key** (hex-encoded)
- **Fingerprint** = first 16 chars of the public key (human-readable)
- **Fallback**: If PyNaCl is not installed, HMAC-based identity derived from `p2p_secret`

### First Run

```bash
$ pinkybrain start bug
🔑 Node identity generated: bug [fingerprint: a3b2c1d4e5f67890]
📌 Public key: a3b2c1d4e5f67890abcdef1234567890abcdef1234567890abcdef12345678
```

The keypair is stored in `~/.pinkybrain/identity/` (or derived from `p2p_secret` in config).

---

## Challenge-Response Protocol

When two nodes connect for the first time:

```
Node A → Node B:  auth_challenge {nonce, timestamp, from_key, signature}
Node B → Node A:  auth_response {response=sign(challenge), from_key, signature}
Node A verifies:  ✓ signature matches B's public key ✓ timestamp within 60s
```

**Anti-replay protection:**
- Each challenge includes a unique `nonce` + `timestamp`
- Timestamps older than 60 seconds are rejected
- Nonce is one-time use (tracked per session)

---

## Web of Trust

Trust is **transitive** and **decentralized**, inspired by PGP's Web of Trust.

### How it works

1. **Node A vouches for Node B** → A signs B's public key
2. **This signature propagates via gossip** to other nodes
3. **Node C sees A→B trust** → If C trusts A, C partially trusts B
4. **Trust score** = weighted sum of direct + transitive signers

### Trust Score Calculation

- Direct signers: weight 1.0
- 1-hop transitive: weight 0.5
- 2-hop transitive: weight 0.25
- Cap at 10.0

### API

```
POST /api/trust/sign   — Sign (vouch for) another node's public key
GET  /api/trust/score/{public_key} — Get trust score for a key
```

---

## Rate Limiting

Each node enforces **per-IP rate limiting** using a token bucket algorithm:

- Default: 10 requests/second, burst of 20
- Configurable via `rate_limit` and `rate_burst` in config
- Unauthenticated requests share a lower bucket
- Authenticated peers get their own bucket (keyed by public key)

---

## Stealth Mode

When `stealth_mode: true` in config:

- Node **does not respond** to discovery probes from unknown IPs
- Node **does not announce** itself on the DHT or mDNS
- Node **only accepts** connections from whitelisted peer IDs (known public keys)
- Unknown pings receive **silence** (not even a rejection) — the node appears offline
- The dashboard and status endpoints return 404 to unknowns

This is essential for micro-servers exposed to the internet (e.g., via Tailscale).

---

## Bootstrapping

How does a new node find its first peer?

1. **Seed nodes** in config: `seed_nodes: [{"host": "100.x.x.x", "port": 8081, "public_key": "..."}]`
2. **Config file peers** (manual, like SSH known_hosts)
3. **mDNS local discovery** on LAN (auto, zero config)
4. **Tailscale discovery** if both nodes are on the same Tailscale network

No central registry needed. Early adopters share a list of seed nodes in the README.

---

## User vs Node Auth

**Users** who install PinkyBrain **do NOT need to authenticate**. They just:
1. Install → `pip install pinkybrain` or `git clone`
2. Configure → edit `config/bug.json`
3. Start → `python -m pinkybrain bug`
4. Query → `curl http://localhost:8080/api/query`

**Node auth** is automatic and transparent — nodes identify each other via Ed25519 keys.

### Sharing AI

Users can share their AI models with the network:
- Config: `"share_ai": true`
- CLI: `pinkybrain share my-model`

When sharing, the node announces its available models to peers. No registration needed.

---

## Summary

| Aspect | Design |
|--------|--------|
| Identity | Ed25519 keypair (self-generated) |
| Auth | Challenge-response + signature |
| Anti-replay | Nonce + timestamp (60s window) |
| Trust | Web of Trust (transitive, PGP-like) |
| Rate limiting | Token bucket per IP/key |
| Stealth | Hidden node mode for public servers |
| Users | No auth needed (just install & use) |
| Nodes | Auto-auth via Ed25519 |
| Bootstrap | Seed nodes + mDNS + Tailscale |