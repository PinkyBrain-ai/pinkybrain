# PinkyBrain — Model Sharing Design *(historical)*

## The Problem

Right now, if Node A has `glm-5.1:cloud` and Node B doesn't have Ollama at all, Node B can't use that model. Users should be able to:

1. Share local models across the P2P network (no Ollama required on every node)
2. Add any LLM provider (OpenAI, Anthropic, custom APIs)
3. Have models auto-discover across nodes

## Solution: Multi-Provider + P2P Model Sharing

### Config Example

```json
{
  "node_name": "bug",
  "port": 8080,
  "p2p_secret": "shared-secret",
  
  "providers": {
    "ollama": {
      "type": "ollama",
      "host": "127.0.0.1",
      "port": 11434,
      "enabled": true
    },
    "openai": {
      "type": "openai",
      "api_key": "sk-...",
      "models": ["gpt-4o", "gpt-4o-mini"],
      "enabled": true
    },
    "anthropic": {
      "type": "anthropic",
      "api_key": "sk-ant-...",
      "models": ["claude-sonnet-4-20250514"],
      "enabled": false
    }
  },
  
  "local_models": ["glm-5.1:cloud", "gpt-4o"],
  
  "peers": [
    {
      "name": "pinky",
      "host": "192.0.2.1",
      "port": 8081,
      "models": ["gemma4:31b-cloud", "deepseek-v3.1:671b-cloud"]
    }
  ],
  
  "share_ai": true
}
```

### Model Routing Priority

1. **Local provider** — check Ollama/OpenAI/Anthropic for the requested model
2. **Peer provider** — if `share_ai: true`, route to a peer that has the model
3. **Fallback** — default model from any available provider

### P2P Model Discovery

When `share_ai: true`, nodes broadcast their available models:
- On WebSocket connect: `{type: "status", models: [...]}`
- On model list change: `{type: "model_update", models: [...]}`
- Peer query: `GET /api/status` includes `local_models` and `peer_models`

### Query Flow

```
User → Node A → /api/query {model: "gemma4:31b-cloud"}
  ├─ Check local providers → not found
  ├─ Check peer models → Pinky has it!
  └─ Route to Pinky → Pinky queries Ollama → returns response → back to User
```

### Provider Types

| Type | API | Auth | Notes |
|------|-----|-----|-------|
| `ollama` | `/api/generate` | None | Local or remote Ollama |
| `openai` | Chat Completions | API key | Works with any OpenAI-compatible API |
| `openai_compatible` | Chat Completions | API key | For LM Studio, vLLM, etc. |
| `anthropic` | Messages API | API key | Claude models |

### Key Insight for Local Model Sharing

When Node A has Ollama with `glm-5.1:cloud` and `share_ai: true`:
- Node B (without Ollama) can query Node A's models via P2P
- Node A acts as a **gateway** to its local models
- No need for every node to run Ollama

This means: **one powerful node with Ollama can serve models to the entire network.**