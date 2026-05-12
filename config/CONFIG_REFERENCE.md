# PinkyBrain v5 — Configuration Reference

> Complete reference for all configuration options in PinkyBrain v5.  
> Config files: `bug-v5.json`, `pinky-v5.json`

---

## Quick Start

1. Copy a v5 config template: `cp config/bug-v5.json config/my-node-v5.json`
2. Edit `node_name`, `host`, `port`, and `peers` for your node
3. Set `P2P_SECRET` environment variable (replaces the old `p2p_secret` field)
4. Optionally enable `public_mesh` (disabled by default)
5. Run: `P2P_SECRET=your-secret python3 src/pinkybrain_v5.py --config config/my-node-v5.json`

---

## Migration from v4 → v5

| Change | v4 | v5 |
|--------|----|-----|
| P2P authentication | `p2p_secret` in config file | `P2P_SECRET` env var (removed from config) |
| Version | `"5.0.0"` | `"5.2.0"` |
| Public mesh | Not available | `public_mesh` section (disabled by default) |
| Conversation store | Not available | `conversation_store` section (enabled by default) |
| Backward compatibility | — | v5 nodes can talk to v4 nodes on private network |

**Important:** Remove `p2p_secret` from your config. Set it as an environment variable instead:
```bash
export P2P_SECRET="your-secret-here"
```
This prevents secrets from being committed to git or leaked in logs.

---

## Core Settings

### `node_name` (string, required)
Unique name for this node on the network. Used in peer discovery, dashboard, and logs.
```json
"node_name": "bug"
```

### `version` (string)
Config schema version. Set to `"5.0.0"` for v5 configs.
```json
"version": "5.0.0"
```

### `host` (string, default: `"0.0.0.0"`)
Bind address for the HTTP/WS server. `0.0.0.0` listens on all interfaces.
```json
"host": "0.0.0.0"
```

### `port` (integer, default: `8080`)
Port for the main server. Each node on the same machine must use a different port.
```json
"port": 8080
```

---

## Ollama / Provider Settings

### `ollama_host` (string, default: `"127.0.0.1"`)
Hostname where Ollama is running. Used as default when no provider matches.
```json
"ollama_host": "127.0.0.1"
```

### `ollama_port` (integer, default: `11434`)
Port for the Ollama API.
```json
"ollama_port": 11434
```

### `local_models` (array of strings)
List of model names available on this node. Used for routing and capability announcements.
```json
"local_models": ["glm-5.1:cloud", "deepseek-v3.1:671b-cloud"]
```

### `providers` (object)
Multi-LLM provider configuration. Each key is a provider name with its own settings.

```json
"providers": {
  "ollama": {
    "type": "ollama",
    "host": "127.0.0.1",
    "port": 11434,
    "models": ["glm-5.1:cloud", "deepseek-v3.1:671b-cloud"],
    "enabled": true
  },
  "openai": {
    "type": "openai",
    "api_key_env": "OPENAI_API_KEY",
    "models": ["gpt-4o", "gpt-4o-mini"],
    "enabled": false
  }
}
```

**Provider fields:**

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Provider type: `ollama`, `openai`, `anthropic` |
| `host` | string | API hostname (Ollama) |
| `port` | integer | API port (Ollama) |
| `api_key_env` | string | Env var name for API key (cloud providers) |
| `models` | string[] | Models available through this provider |
| `enabled` | boolean | Whether this provider is active |

---

## Network Settings

### `heartbeat_interval` (integer, default: `30`, seconds)
How often to send heartbeat pings to peers. Lower = faster failure detection but more network traffic.
```json
"heartbeat_interval": 30
```

### `auto_heal_interval` (integer, default: `120`, seconds)
How often to check peer health and attempt reconnection.
```json
"auto_heal_interval": 120
```

### `tailscale_auto_discovery` (boolean, default: `true`)
Automatically discover other PinkyBrain nodes on the same Tailscale network.
```json
"tailscale_auto_discovery": true
```

### `stealth_mode` (boolean, default: `false`)
When true, this node doesn't announce itself to the network but can still connect to known peers. Useful for nodes that want to participate without being discovered.
```json
"stealth_mode": false
```

### `share_ai` (boolean, default: `true`)
Whether to share this node's AI capabilities with peers on the private network.
```json
"share_ai": true
```

---

## Rate Limiting & Circuit Breaker

### `rate_limit` (float, default: `10.0`)
Maximum requests per second this node accepts.
```json
"rate_limit": 10.0
```

### `rate_burst` (integer, default: `20`)
Maximum burst of requests before rate limiting kicks in.
```json
"rate_burst": 20
```

### `circuit_breaker` (object)
Protects against cascading failures by stopping requests to unhealthy peers.

```json
"circuit_breaker": {
  "failure_threshold": 3,
  "recovery_timeout": 60,
  "half_open_max_calls": 1
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `failure_threshold` | int | 3 | Consecutive failures before circuit opens |
| `recovery_timeout` | int | 60 | Seconds before trying again (half-open state) |
| `half_open_max_calls` | int | 1 | Test calls allowed in half-open state |

---

## Peers

### `peers` (array of objects)
Static peer definitions for the private P2P network.

```json
"peers": [
  {
    "name": "Pinky",
    "host": "192.0.2.1",
    "port": 8081,
    "models": ["glm-5.1:cloud", "deepseek-v3.1:671b-cloud"]
  }
]
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Peer node name (must match their `node_name`) |
| `host` | string | IP address or hostname |
| `port` | int | Their server port |
| `models` | string[] | Models available on that peer |

### `seed_nodes` (array of strings, default: `[]`)
Additional seed nodes for bootstrapping discovery beyond static peers and Tailscale.
```json
"seed_nodes": ["https://seed1.pinkybrain.ai", "https://seed2.pinkybrain.ai"]
```

---

## Authentication & Tokens

### `token_lifetime` (integer, default: `86400`, seconds)
How long a JWT token remains valid. Default: 24 hours.
```json
"token_lifetime": 86400
```

### `token_rotation_interval` (integer, default: `3600`, seconds)
How often to rotate JWT signing keys. Default: 1 hour.
```json
"token_rotation_interval": 3600
```

### `discovery_interval` (integer, default: `300`, seconds)
How often to scan for new peers via Tailscale or mDNS.
```json
"discovery_interval": 300
```

> **Note:** `p2p_secret` has been **removed** from v5 config files. Set the `P2P_SECRET` environment variable instead. This prevents secrets from being stored in version control.

---

## Memory Settings

### `memory_max_size` (integer, default: `1000`)
Maximum number of entries in the in-memory CRDT store.
```json
"memory_max_size": 1000
```

### `memory_default_ttl` (integer, default: `3600`, seconds)
Default time-to-live for memory entries before they expire.
```json
"memory_default_ttl": 3600
```

---

## 🆕 Public Mesh (v5)

The public mesh allows your node to join the global PinkyBrain network and share compute resources with other nodes worldwide. **Disabled by default — opt-in.**

### `public_mesh.enabled` (boolean, default: `false`)
Enable connection to the public PinkyBrain mesh. When false, the node only operates on the private P2P network.
```json
"public_mesh": {
  "enabled": false
}
```

### `public_mesh.tracker_url` (string, default: `"https://tracker.pinkybrain.ai"`)
URL of the public tracker server. The tracker helps nodes discover each other and coordinates capabilities announcements.
```json
"tracker_url": "https://tracker.pinkybrain.ai"
```

### `public_mesh.max_ram_share_mb` (integer, default: `2048`)
Maximum RAM (in MB) this node will share with the public mesh. The Resource Guard ensures this limit is never exceeded. Recommended: 1-4GB for typical machines.
```json
"max_ram_share_mb": 2048
```

### `public_mesh.max_cpu_percent` (integer, default: `30`)
Maximum CPU percentage this node will share. If the node's CPU usage exceeds 80%, public mesh requests are automatically refused regardless of this setting.
```json
"max_cpu_percent": 30
```

### `public_mesh.gpu_share` (boolean, default: `false`)
Whether to share GPU resources with the public mesh. Enable only if you have a dedicated GPU and want to contribute compute power for model inference.
```json
"gpu_share": false
```

### `public_mesh.models_share` (array of strings, default: `[]`)
List of local models to make available to the public mesh. Empty array = no models shared publicly. Start with lightweight models.
```json
"models_share": ["glm-5.1:cloud"]
```

### `public_mesh.priority` (string, default: `"local_first"`)
Resource priority policy. Options:
- `"local_first"` — Always prioritize local user requests. Public requests are refused when the machine is busy.
- `"balanced"` — Try to serve both local and public requests fairly.
```json
"priority": "local_first"
```

### `public_mesh.bandwidth_limit_kbps` (integer, default: `5000`)
Maximum bandwidth (in kbps) the node will use for public mesh traffic. Prevents mesh activity from saturating your internet connection.
```json
"bandwidth_limit_kbps": 5000
```

### `public_mesh.contribution_score` (integer, default: `0`)
Your contribution score on the public mesh. This is updated automatically by the tracker based on your uptime, compute shared, and models hosted. Higher scores unlock higher query quotas.
```json
"contribution_score": 0
```

### `public_mesh.stealth_mode` (boolean, default: `false`)
When true, your node shares compute but stays hidden in the mesh directory. Other nodes can use your resources but can't see your identity or IP directly.
```json
"stealth_mode": false
```

### Quota System

The public mesh uses a contribution-based quota system:

| Contribution | Score | Quota |
|---|---|---|
| Nothing shared | 0 | 1 query / 5 min |
| 1 model shared | +20 | 5 queries / min |
| 2+ models shared | +30 | 20 queries / min |
| 2GB RAM shared | +20 | +10 queries / min |
| GPU shared | +20 | +20 queries / min |
| 24h uptime | +10 | +5 queries / min |

---

## 🆕 Conversation Store (v5)

Persistent local conversation storage. Your conversations stay on your machine and never leave unless you explicitly sync them via the private P2P network. **Enabled by default.**

### `conversation_store.enabled` (boolean, default: `true`)
Enable local conversation persistence. When enabled, all conversations are auto-saved to disk.
```json
"conversation_store": {
  "enabled": true
}
```

### `conversation_store.storage_dir` (string, default: `"~/.pinkybrain/conversations"`)
Directory where conversations are stored on disk. Expanded at runtime (`~` resolves to the user's home directory).
```json
"storage_dir": "~/.pinkybrain/conversations"
```

### `conversation_store.encryption` (boolean, default: `false`)
Encrypt conversations at rest using AES-256. Recommended for sensitive data. If enabled, conversations are unreadable without the node's key.
```json
"encryption": false
```

### `conversation_store.max_conversation_size_mb` (integer, default: `100`)
Maximum size per conversation file in MB. Conversations exceeding this limit are archived or pruned (oldest messages first).
```json
"max_conversation_size_mb": 100
```

### `conversation_store.default_privacy` (string, default: `"private"`)
Default privacy level for new conversations. Options:
- `"private"` — Conversations stay local, never synced
- `"synced"` — Synced via private P2P network only (your devices)
- `"shared"` — Can be shared with specific peers
- `"public"` — Added to public mesh knowledge base (opt-in)

```json
"default_privacy": "private"
```

### `conversation_store.auto_save` (boolean, default: `true`)
Automatically save every message as it arrives. No need to manually save conversations.
```json
"auto_save": true
```

### `conversation_store.search_enabled` (boolean, default: `true`)
Enable full-text search across conversations. Allows finding past conversations by keyword, date, model, or tag.
```json
"search_enabled": true
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `P2P_SECRET` | **Yes** (v5) | Secret for private P2P network authentication. Replaces `p2p_secret` in config. **Must be set via env var, not config file.** |
| `OPENAI_API_KEY` | No | API key for OpenAI provider (if used) |
| `ANTHROPIC_API_KEY` | No | API key for Anthropic provider (if used) |
| `PINKYBRAIN_LOG_LEVEL` | No | Override log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `PINKYBRAIN_CONFIG` | No | Path to config file (default: `config/bug-v5.json`) |

---

## Example Minimal Config

```json
{
  "node_name": "my-laptop",
  "version": "5.0.0",
  "host": "0.0.0.0",
  "port": 8080,
  "ollama_host": "127.0.0.1",
  "ollama_port": 11434,
  "local_models": ["glm-5.1:cloud"],
  "providers": {
    "ollama": {
      "type": "ollama",
      "host": "127.0.0.1",
      "port": 11434,
      "models": ["glm-5.1:cloud"],
      "enabled": true
    }
  },
  "heartbeat_interval": 30,
  "auto_heal_interval": 120,
  "memory_max_size": 1000,
  "memory_default_ttl": 3600,
  "tailscale_auto_discovery": true,
  "stealth_mode": false,
  "share_ai": true,
  "rate_limit": 10.0,
  "rate_burst": 20,
  "circuit_breaker": {
    "failure_threshold": 3,
    "recovery_timeout": 60,
    "half_open_max_calls": 1
  },
  "peers": [],
  "seed_nodes": [],
  "token_lifetime": 86400,
  "token_rotation_interval": 3600,
  "discovery_interval": 300,
  "public_mesh": {
    "enabled": false,
    "tracker_url": "https://tracker.pinkybrain.ai",
    "max_ram_share_mb": 2048,
    "max_cpu_percent": 30,
    "gpu_share": false,
    "models_share": [],
    "priority": "local_first",
    "bandwidth_limit_kbps": 5000,
    "contribution_score": 0,
    "stealth_mode": false
  },
  "conversation_store": {
    "enabled": true,
    "storage_dir": "~/.pinkybrain/conversations",
    "encryption": false,
    "max_conversation_size_mb": 100,
    "default_privacy": "private",
    "auto_save": true,
    "search_enabled": true
  }
}
```

---

## Security Notes

1. **Never commit `p2p_secret` to git.** Use `P2P_SECRET` environment variable.
2. **`public_mesh.enabled` defaults to `false`.** You must explicitly opt-in to share resources publicly.
3. **`conversation_store.default_privacy` defaults to `private`.** Conversations never leave your machine unless you change this.
4. **The Resource Guard always prioritizes local usage.** Even with `public_mesh.enabled: true`, your machine won't become unusable.
5. **`stealth_mode` (private network)** and **`public_mesh.stealth_mode`** are independent settings.

---

*Generated for PinkyBrain v5 — Public Mesh Architecture*