# 🧠 Architecture PinkyBrain v5 — Audit des Capacités

## Question de Denis
> Les capacités de réseaux, cryptage, RAID et agentique font-elles bien partie de brain.llm ?
> Est-ce bien lui qui gère PinkyBrain ?

## Réponse courte : **Non.** `brain_llm.py` est un orchestrateur LLM minimal. Il ne gère PAS les capacités clés du système.

## Qui gère quoi ?

```
┌─────────────────────────────────────────────────────────────┐
│                   pinkybrain_v5.py (206 KB)                  │
│                   LE CŒUR DU SYSTÈME                         │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────┐ │
│  │ HTTP Server │  │  WebSocket  │  │   P2P Discovery      │ │
│  │ (aiohttp)   │  │  Server     │  │   (mDNS + Tailscale)  │ │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬───────────┘ │
│         │                │                     │              │
│  ┌──────┴────────────────┴─────────────────────┴──────┐     │
│  │              AUTH & SECURITY LAYER                   │     │
│  │  NodeIdentity (Ed25519/HMAC) + RateLimiter + CORS   │     │
│  └──────┬──────────────────────────────────────────────┘     │
│         │                                                    │
│  ┌──────┴──────────────────────────────────────────────┐     │
│  │         ROUTING & QUERY ORCHESTRATION               │     │
│  │  ModelNegotiator + SpecialistRouter + Router        │     │
│  └──────┬──────────────────────────────────────────────┘     │
│         │                                                    │
│  ┌──────┴───────────────────────────────────────────────┐    │
│  │  handle_query() ← CENTRAL :                           │    │
│  │  1. Auth check (is it a peer?)                        │    │
│  │  2. BandwidthQuota check                              │    │
│  │  3. share_ai check                                    │    │
│  │  4. CreditSystem check (peer requests)                │    │
│  │  5. SharingQuota rate limit check                     │    │
│  │  6. SpecialistRouter routing (if specialty/models)    │    │
│  │  7. Fallback: ModelRouter → local/cloud/P2P           │    │
│  └───────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────┐  ┌──────────────────┐  ┌────────────┐   │
│  │ CRDTMemory       │  │ WebOfTrust       │  │AutoUpdater │   │
│  │ (P2P sync)       │  │ (Trust scoring)  │  │ (SHA-256) │   │
│  └─────────────────┘  └──────────────────┘  └────────────┘   │
│                                                              │
│  ┌─────────────────┐  ┌──────────────────┐  ┌────────────┐   │
│  │ Dashboard Web UI │  │ ConversationStore│  │GamifiedScore│  │
│  │ (HTML/CSS/JS)    │  │ (Persistent chat)│  │ (Levels)   │   │
│  └─────────────────┘  └──────────────────┘  └────────────┘   │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ model_networks (v5.2) — Permissions par réseau         │  │
│  │ private_networks + model_permissions matrix              │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘

         Modules externes (importés par v5, optionnels)

┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ resource_guard   │  │ adaptive_scheduler│  │ bandwidth_quota  │
│ (Auto-pause     │  │ (Strategy auto:  │  │ (Data cap like   │
│  sharing when   │  │  routing→shard→  │  │  mobile plan)    │
│  user is active)│  │  raid)           │  │                  │
└──────────────────┘  └──────────────────┘  └──────────────────┘
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ credit_system     │  │ model_specialist │  │model_share_mgr  │
│ (Earn/spend      │  │ (12 specialties │  │ (Secure symlink  │
│  credits by      │  │  + auto-route)  │  │  bridge)         │
│  sharing)        │  │                 │  │                  │
└──────────────────┘  └──────────────────┘  └──────────────────┘
┌──────────────────┐  ┌──────────────────┐
│ tracker_client    │  │ conversation_store│
│ (Public mesh     │  │ (Persistent chat │
│  discovery)      │  │  with encryption)│
└──────────────────┘  └──────────────────┘

┌──────────────────────────────────────────────────┐
│              brain_llm.py (163 KB)               │
│                                                  │
│  BrainLLM class:                                 │
│  ├── _discover_models() → Ollama + P2P + Cloud   │
│  ├── query(prompt, model, strategy)              │
│  │   ├── auto: local → cloud → P2P               │
│  │   ├── local / cloud / P2P (forced)             │
│  │   ├── consensus: multi-model vote              │
│  │   └── chain: decompose + chain                 │
│  ├── _query_ollama()                              │
│  ├── _query_p2p()                                 │
│  ├── _consensus_query()                           │
│  ├── _chain_query()                               │
│  └── get_context() → PersistentMemory             │
│                                                  │
│  ⚠️ NE GÈRE PAS:                                │
│  ✗ Auth/P2P security (pas de headers auth)       │
│  ✗ Sharding/RAID (rien dans ce module)            │
│  ✗ Resource Guard                                 │
│  ✗ Credit System                                  │
│  ✗ Bandwidth Quota                                │
│  ✗ Model Permissions / Networks                   │
│  ✗ SpecialistRouter (géré par v5 directement)     │
│  ✗ Cryptage des communications                    │
└──────────────────────────────────────────────────┘
```

## Problèmes identifiés dans brain_llm.py

### 1. 🔴 P2P SANS AUTH (CRITIQUE)
`_query_p2p()` envoie des requêtes POST à `/api/query` **sans aucun header d'authentification**.
→ Les pairs rejettent ces requêtes (v5 nécessite auth).

```python
# brain_llm.py ligne 277 — MANQUE:
async with self.session.post(
    f"http://{peer['host']}:{peer['port']}/api/query",
    json={"prompt": prompt, "model": model},
    timeout=aiohttp.ClientTimeout(total=120)
) as resp:
```

Devrait inclure :
```python
headers = self._auth_headers(path="/api/query")
async with self.session.post(..., headers=headers) as resp:
```

### 2. 🟠 Pas de chiffrement des communications
- Les requêtes P2P se font en HTTP (pas HTTPS)
- Les réponses transitent en clair sur le réseau
- Pas de TLS entre nœuds
- Seul le `/search` memory utilise `X-Node-Secret` (en header, non chiffré)

### 3. 🟠 brain_llm est déconnecté du reste
- Il ne connaît PAS les permissions modèles/réseaux (`model_networks`)
- Il ne vérifie PAS les quotas bande passante
- Il ne vérifie PAS les crédits
- Il ne vérifie PAS si share_ai est activé
- Il ne sait PAS si le ResourceGuard est en pause

### 4. 🟡 brain_llm ne participe pas au sharding/RAID
- `adaptive_scheduler.py` gère le sharding, RAID-RAM, partial_sharding
- Mais brain_llm n'utilise PAS l'adaptive_scheduler
- Les stratégies de brain_llm sont : auto/local/cloud/P2P/consensus/chain
- AUCUN sharding de modèle n'est fait via brain_llm

## Capacités demandées vs Réalité

| Capacité | brain_llm ? | v5 + modules ? | Status |
|---|---|---|---|
| **Réseau P2P** | ❌ Sans auth | ✅ v5 gère | ⚠️ brain_llm cassé |
| **Cryptage** | ❌ Aucun | ⚠️ Partiel (HMAC/Ed25519 auth, pas TLS) | À améliorer |
| **RAID/Sharding** | ❌ Non | ✅ adaptive_scheduler | Non connecté |
| **Agentique** | ⚠️ Basique (chain) | ✅ SpecialistRouter + MultiModel | Partiel |
| **Partage modèles** | ❌ Non | ✅ ModelShareManager + model_networks | OK |
| **Quota/bande passante** | ❌ Non | ✅ BandwidthQuota + CreditSystem | OK |
| **Protection ressources** | ❌ Non | ✅ ResourceGuard | OK |
| **Routing intelligent** | ⚠️ Basique | ✅ SpecialistRouter (12 spécialités) | Partiel |

## Recommandations

1. **Réparer brain_llm.py** — Ajouter les headers d'auth P2P (PRIORITY 1)
2. **Connecter brain_llm aux modules** — Credit check, ResourceGuard, ModelPermissions
3. **Intégrer adaptive_scheduler dans brain_llm** — Pour le sharding/RAID
4. **Ajouter TLS** — Pour les communications inter-nœuds
5. **Ajouter le chiffrement des payloads** — Au moins AES pour les prompts/réponses P2P