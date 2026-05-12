# PinkyBrain v5 — Public Mesh Architecture

## Vision

PinkyBrain v4 = routeur P2P privé.  
PinkyBrain v5 = routeur P2P privé **+** mesh public de calcul partagé.

Un utilisateur peut :
1. Garder son réseau privé (p2p_secret) pour ses propres machines
2. Rejoindre le mesh public pour partager et utiliser du calcul CPU/GPU/RAM et des modèles IA
3. Contrôler exactement combien de ressources il partage — jamais plus que ce qu'il autorise

**Le réseau privé ne change pas. Le mesh public est un layer additionnel.**

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Node (You)                        │
│                                                     │
│  ┌─────────────┐          ┌──────────────────┐     │
│  │ Private Net  │          │   Public Mesh     │     │
│  │ p2p_secret   │          │   tracker公开     │     │
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
│  └─────────────────┘      │  announce/capabilities│
│                           └──────────────────┘     │
└─────────────────────────────────────────────────────┘
```

---

## Dual Network Design

### Private Network (unchanged from v4)

- **Auth:** p2p_secret (HMAC) + Ed25519
- **Discovery:** Static config, Tailscale, mDNS
- **Routing:** Local → Cloud → Peer failover
- **Quota:** Internal, score-based
- **Data:** Stays within trusted nodes

### Public Mesh (NEW)

- **Auth:** Ed25519 identity + Web of Trust
- **Discovery:** Public tracker server (like uTorrent trackers)
- **Routing:** Find best node for model → route request
- **Quota:** Public, contribution-based
  - Share 2GB RAM → earn X queries/minute
  - Share a model → earn Y queries/minute
  - Share nothing → 1 query/5min (throttled, not blocked)
- **Resource Control:**
  ```json
  {
    "public_mesh": {
      "enabled": true,
      "tracker_url": "https://tracker.pinkybrain.ai",
      "max_ram_share_mb": 2048,
      "max_cpu_percent": 30,
      "gpu_share": false,
      "models_share": ["glm-5.1:cloud"],
      "priority": "local_first",
      "bandwidth_limit_kbps": 5000
    }
  }
  ```
- **Self-protection:**
  - Monitor local CPU/RAM usage
  - If CPU > 80% or RAM > 90% → auto-pause public sharing
  - If user is actively using the machine → refuse public requests
  - Resume sharing when resources are available again

---

## Public Tracker

The tracker is a lightweight HTTP/WebSocket server that:

1. **Announce:** Nodes register their capabilities
   ```json
   {
     "node_id": "ed25519_pubkey_hex",
     "capabilities": {
       "cpu_cores": 4,
       "ram_total_mb": 16384,
       "ram_share_mb": 2048,
       "gpu": null,
       "models": ["glm-5.1:cloud", "llama3:8b"],
       "bandwidth_kbps": 10000
     },
     "uptime_seconds": 86400,
     "address": "192.0.2.1:8081"
   }
   ```

2. **Discover:** Find nodes that have what you need
   ```json
   GET /api/find?model=glm-5.1:cloud&min_ram=1024
   → [{"node_id": "...", "address": "...", "latency_ms": 45, "score": 85}]
   ```

3. **Score:** Track contribution scores
   - Models hosted: weight
   - Uptime: weight
   - Queries served: weight
   - Compute shared: weight

### Tracker Implementation

Simple Python/asyncio server. Can run on:
- The official PinkyBrain tracker (pinkybrain.ai)
- Any community tracker (self-hosted)
- Tailscale MagicDNS for private meshes

---

## Model Sharing (Public Mesh)

### Phase 1: Model Routing (v5.0)
- Node announces which models it can serve
- Other nodes route queries to it
- Models run ENTIRELY on the hosting node (no sharding yet)
- Like current routing but across the public mesh

### Phase 2: Model Sharding (v5.x)
- Large models split into layers
- Each node holds a fraction
- Pipeline parallel across nodes
- Like Petals, but P2P

### Phase 3: RAID RAM (v6)
- Model weights stored in distributed RAM
- Each node contributes a fraction
- Redundancy: each chunk on 3+ nodes
- Async pre-fetching for inference speed

---

## Resource Guard (Self-Protection)

The Resource Guard monitors local system resources and automatically adjusts sharing:

```python
class ResourceGuard:
    """Ensures sharing never impacts the user's experience."""
    
    def __init__(self, config):
        self.max_cpu = config.get("max_cpu_percent", 30)
        self.max_ram = config.get("max_ram_share_mb", 2048)
        self.gpu_share = config.get("gpu_share", False)
        self.priority = config.get("priority", "local_first")
    
    def can_accept_request(self) -> bool:
        """Check if we can accept a public request RIGHT NOW."""
        cpu_usage = psutil.cpu_percent(interval=0.1)
        ram_usage = psutil.virtual_memory().percent
        
        # Always prioritize local user
        if self.priority == "local_first":
            if cpu_usage > 70 or ram_usage > 85:
                return False  # User is busy, don't steal resources
        
        # Never exceed configured limits
        if cpu_usage > self.max_cpu + 40:  # base + share limit
            return False
        
        return True
    
    def get_available_resources(self) -> dict:
        """Report what we can share right now."""
        available_ram = min(
            self.max_ram,
            int(psutil.virtual_memory().available * 0.5 / 1024 / 1024)  # max 50% of free
        )
        return {
            "ram_mb": available_ram,
            "cpu_available": max(0, self.max_cpu - psutil.cpu_percent()),
            "gpu": self.gpu_share
        }
```

---

## Configuration (v5)

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
    "models_share": ["glm-5.1:cloud"],
    "priority": "local_first",
    "bandwidth_limit_kbps": 5000,
    "contribution_score": 0
  },
  
  "providers": {
    "ollama": {
      "type": "ollama",
      "host": "127.0.0.1",
      "port": 11434,
      "models": ["glm-5.1:cloud"],
      "enabled": true
    }
  }
}
```

---

## Public Quota System

| Contribution | Score | Public Quota |
|---|---|---|
| Nothing shared | 0 | 1 query / 5 min |
| 1 model shared | +20 | 5 queries / min |
| 2+ models shared | +30 | 20 queries / min |
| 2GB RAM shared | +20 | +10 queries / min |
| GPU shared | +20 | +20 queries / min |
| 24h uptime | +10 | +5 queries / min |

**Local priority ALWAYS wins.** If your machine is busy, it refuses public requests.

---

## Security

- Private network: encrypted with p2p_secret (unchanged)
- Public mesh: Ed25519 identity, TLS for transport
- No data leaks between private and public networks
- Public requests are sandboxed: no access to private memory
- Rate limiting per node and per IP
- Stealth mode still available: share compute but stay hidden

---

## Migration Path (v4 → v5)

1. v5 is backward compatible with v4
2. Private network config works exactly as before
3. `public_mesh` section is optional — disabled by default
4. Existing v4 nodes can talk to v5 nodes on the private network
5. Public mesh is opt-in: set `public_mesh.enabled = true`

---

## Implementation Priority

1. ✅ Resource Guard (self-protection) — prevents PC from becoming unusable
2. ✅ Public tracker client (announce/discover) — connect to mesh
3. ✅ Public mesh routing — route queries to public nodes
4. ✅ Public quota system — contribution-based limits
5. ⏳ Model sharding — Phase 2
6. ⏳ RAID RAM — Phase 3

---

## Philosophy

**Like uTorrent, but for AI.**

- You choose what you share (models, CPU, RAM, GPU)
- You choose how much you share
- More sharing = more access to the network
- Less sharing = still works, just slower
- Your machine is NEVER unusable because of sharing
- Private network stays private. Public mesh is opt-in.
---

## 💾 Persistent Conversation Memory (NEW in v5)

### The Problem

Most AI services (ChatGPT, Claude, etc.) either:
- Delete your conversations after a session
- Store them on THEIR servers (you lose control)
- Use them for training (your private thoughts become their data)
- Require payment to keep history

When you come back the next day → **blank page**. Everything you discussed, every insight, gone.

### The PinkyBrain Solution

**Your conversations stay on YOUR machine. Period.**

```json
// ~/.pinkybrain/conversations/
{
  "conv_2026-05-05_001": {
    "created": "2026-05-05T22:00:00Z",
    "messages": [
      {"role": "user", "content": "Comment faire un potager en ville?"},
      {"role": "assistant", "content": "Un potager en ville, c'est un acte de résistance...", "model": "glm-5.1:cloud", "node": "local"}
    ],
    "metadata": {
      "model": "glm-5.1:cloud",
      "tokens_used": 450,
      "tags": ["potager", "ville", "jardinage"]
    }
  }
}
```

### Features

1. **Auto-save** — Every message saved locally as you type. No "save" button needed.
2. **Resume** — Open PinkyBrain tomorrow, your conversations are there. Like reopening a book.
3. **Search** — Find any past conversation by keyword, date, model, or tag.
4. **Export** — Export to Markdown, JSON, or plain text. Your data, your format.
5. **Privacy** — Conversations NEVER leave your machine unless YOU choose to sync them via the private P2P network.
6. **Encryption** — Optional local encryption. Even if someone accesses your disk, they can't read your conversations.
7. **No tracking** — No analytics, no "we use your data to improve our models". Your thoughts are not our training data.

### CLI Usage

```bash
pinkybrain                          # Start chat (auto-loads last conversation)
pinkybrain --list                   # List all conversations
pinkybrain --search "potager"       # Find conversations about "potager"
pinkybrain --resume conv_2026-05-05_001  # Resume specific conversation
pinkybrain --export markdown         # Export all conversations to markdown
```

### In Chat

```
You: /history          → Show conversation history
You: /save potager     → Tag this conversation as "potager"
You: /search ville     → Search all conversations for "ville"
You: /export           → Export current conversation
You: /new              → Start new conversation
```

### Privacy Levels

| Level | What happens | Use case |
|-------|-------------|----------|
| **private** (default) | Conversations stay local, never synced | Personal, sensitive |
| **synced** | Synced via private P2P network only | Shared between your devices |
| **shared** | Can be shared with specific peers | Collaboration |
| **public** | Added to public mesh knowledge base (opt-in) | Community knowledge |

**Default is private. Always.** The user must explicitly choose to share anything.

### Why This Matters

When Denis pays for a ChatGPT subscription:
- His conversations live on OpenAI servers
- OpenAI can use them for training
- If he stops paying → blank page
- If OpenAI has a data breach → his private thoughts are exposed

When Denis uses PinkyBrain:
- His conversations live on his machine
- Nobody can use them for training
- He stops sharing compute → his conversations are STILL there
- No data breach possible (data never left his machine)

**This is data sovereignty. Not a feature — a right.**

---

## 🔄 Adaptive Resource Management — Le réseau s'adapte tout seul

### Principe fondamental

**Ce n'est pas la version qui définit les capacités. C'est le nombre de pairs.**

Pas de v5 vs v6. Pas de "mode sharding" vs "mode routing". Le système détecte combien de pairs sont disponibles et choisit automatiquement la meilleure stratégie.

### Niveaux adaptatifs

```
┌──────────────────────────────────────────────────────────────────┐
│  PAIRS DISPONIBLES    STRATÉGIE              CAPACITÉ             │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1-3 pairs     →   Routage simple          Modèles entiers       │
│                     (comme v4)            sur 1 machine           │
│                                                                  │
│  4-10 pairs    →   Sharding partiel       Modèles découpés      │
│                     couches réparties     en 2-4 fragments       │
│                     sur quelques nodes     sur quelques nodes    │
│                                                                  │
│  11-50 pairs   →   Sharding complet       Pipeline parallel     │
│                     + réplication 2x       + redondance          │
│                     chaque chunk x2        jamais de perte       │
│                                                                  │
│  50+ pairs     →   RAID RAM distribué     Disque virtuel         │
│                     réplication 3x         dans la RAM de tous    │
│                     pré-chargement async   latence minimale      │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Comment ça marche en pratique

**2 pairs (toi + 1 ami)**

```
Toi:  [Ollama - glm-5.1]     Ami:  [Ollama - llama3]
       8GB RAM                      16GB RAM

→ Routage simple:
  "glm-5.1" → va sur ta machine
  "llama3"  → va sur la machine de ton ami
  Aucun sharding nécessaire, pas assez de pairs
```

**8 pairs (petit réseau)**

```
Toi:  [glm-5.1, 2GB RAM]    Pair2: [2GB RAM]
Pair3: [4GB RAM]              Pair4: [8GB RAM]
Pair5: [2GB RAM]             Pair6: [4GB RAM]
Pair7: [2GB RAM]             Pair8: [16GB RAM, RTX 3060]

→ Sharding partiel:
  glm-5.1 (8GB total) découpé en 4 chunks de 2GB
  Chunk 1 → Pair4 (a de la place)
  Chunk 2 → Pair8 (a de la place + GPU)
  Chunk 3 → Toi + Pair3 (chacun 2GB)
  Chunk 4 → Pair6 (4GB dispo)
  
  Si Pair4 se déconnecte → Chunk 1 recalculé sur Pair2
  Requête → traverse Chunk1→Chunk2→Chunk3→Chunk4 = réponse
```

**50+ pairs (mesh public)**

```
→ RAID RAM distribué:
  Chaque chunk répliqué 3x
  Pré-chargement asynchrone des chunks adjacents
  Si 3 pairs se déconnectent → 0 impact (copies existent)
  Latence ~50-100ms par token (pipeline optimisé)
  40GB de modèles qui tournent sur des machines qui n'ont que 2GB chacune
```

### Le Adaptive Scheduler

C'est le cerveau qui décide TOUT AUTOMATIQUEMENT :

```python
class AdaptiveScheduler:
    """Decides resource strategy based on available peers."""
    
    def __init__(self, identity, resource_guard, tracker_client):
        self.identity = identity
        self.resource_guard = resource_guard
        self.tracker = tracker_client
        self.strategy = "routing"  # default
        self.model_chunks = {}     # which peer has which chunk
    
    async def update_strategy(self):
        """Called periodically or when peers change."""
        peers = await self.tracker.get_available_peers()
        total_ram = sum(p.capabilities.ram_share_mb for p in peers)
        total_gpu = sum(1 for p in peers if p.capabilities.gpu)
        
        if len(peers) < 4:
            self.strategy = "routing"
            # Models run entirely on one node
        elif len(peers) < 11:
            self.strategy = "partial_sharding"
            # Split models into 2-4 chunks
            self.replication_factor = 2
        elif len(peers) < 51:
            self.strategy = "full_sharding"
            # Full pipeline parallel + replication
            self.replication_factor = 2
        else:
            self.strategy = "raid_ram"
            # Distributed RAM disk + async prefetch
            self.replication_factor = 3
    
    async def route_query(self, prompt: str, model: str) -> str:
        """Route a query using the current strategy."""
        if self.strategy == "routing":
            return await self._route_simple(prompt, model)
        elif self.strategy == "partial_sharding":
            return await self._route_sharded(prompt, model, chunks=2)
        elif self.strategy == "full_sharding":
            return await self._route_sharded(prompt, model, chunks=4)
        else:  # raid_ram
            return await self._route_raid(prompt, model)
    
    async def _route_sharded(self, prompt, model, chunks):
        """Pipeline parallel inference across shards."""
        # 1. Find which peers hold which chunks
        # 2. Send prompt to first chunk
        # 3. Intermediate results flow through pipeline
        # 4. Last chunk returns final response
        # 5. If any chunk node is down → use replica
        pass
    
    async def _route_raid(self, prompt, model):
        """RAID RAM distributed inference."""
        # 1. All chunks in RAM across network
        # 2. Pre-fetch adjacent chunks asynchronously
        # 3. Pipeline with minimal latency
        # 4. Auto-rebalance if nodes join/leave
        pass
    
    async def redistribute_chunks(self):
        """Rebalance chunks when peers join/leave."""
        # Called when:
        # - A peer disconnects (replicas take over)
        # - New peers join (redistribute for balance)
        # - Resource limits change (peer reduced sharing)
        pass
```

### Transition automatique

Le passage d'un niveau à l'autre se fait **sans interruption** :

```
[3 pairs en routage]
  → Pair #4 rejoint
  → Scheduler: "4 pairs → passage en partial_sharding"
  → Découpe le modèle en chunks en arrière-plan
  → Transfert des chunks vers les pairs disponibles
  → Quand tous les chunks sont en place → sharding actif
  → Si un pair part → fallback sur routage le temps de rééquilibrer
  
[8 pairs en sharding partiel]
  → Pairs 9-12 rejoignent
  → Scheduler: "12 pairs → passage en full_sharding"
  → Redécoupe en plus de chunks + réplication
  → Transition progressive, pas de coupure
  
[49 pairs en full_sharding]
  → Pairs 50-55 rejoignent
  → Scheduler: "55 pairs → passage en raid_ram"
  → Pré-chargement des chunks en RAM sur les nouveaux pairs
  → Réplication 3x progressive
```

### Règles d'or

1. **Le scheduler décide, pas l'utilisateur.** L'utilisateur dit "je partage 2GB RAM", le scheduler décide quoi en faire.
2. **Toujours un fallback.** Si le sharding échoue → routage simple. Si le RAID échoue → sharding. Jamais de "désolé, ça ne marche plus".
3. **Zéro interruption.** Les transitions se font en arrière-plan. L'utilisateur ne remarque rien.
4. **Redondance automatique.** Plus de pairs = plus de copies = plus de sécurité. Jamais un seul point de défaillance.
5. **L'utilisateur garde le contrôle.** Il dit combien il partage. Le scheduler respecte toujours les limites du Resource Guard.

### Pourquoi c'est important

- 2 étudiants avec des vieux PCs → ça marche (routage)
- 10 personnes sur un forum → ça marche mieux (sharding)
- 1000 personnes sur le mesh public → ça marche encore mieux (RAID RAM)
- **Le même logiciel, le même code, la même configuration.**
- **C'est le réseau qui grandit, pas la version.**

---

## 🌊 The Network Effect — De l'individuel au super-ordinateur distribué

### Au début (2-10 pairs)

Chacun partage ce qu'il a physiquement sur sa machine.

```
Toi:     [Ollama glm-5.1, 2GB RAM]
Ami:     [Ollama llama3, 4GB RAM]

→ Tu as accès à 2 modèles au lieu de 1
→ Ton ami pareil
→ C'est du dépannage entre potes
```

**C'est déjà utile.** Ton vieux PC de 2GB peut utiliser llama3 qui tourne chez ton ami. Sans payer, sans cloud, sans donner tes données.

### Avec plus de monde (50-500 pairs)

Le système commence à devenir **latent** — il y a TOUJOURS quelqu'un de connecté, TOUJOURS un modèle disponible.

```
50 pairs connectés en moyenne:
- 12 avec Ollama (différents modèles)
- 8 avec GPU (NVIDIA, AMD, Apple Silicon)
- 30 qui partagent juste CPU/RAM

→ Tu peux utiliser glm-5.1, llama3, mistral, phi-3...
  à n'importe quelle heure, sans les installer
→ Les modèles les plus demandés sont pré-chargés
  sur les pairs qui ont de la RAM disponible
→ Pipeline parallel : un token traverse 4 pairs en 200ms
```

**C'est un système d'IA qui existe de manière latente.** Pas de serveur, pas de data center. Juste 50 personnes qui partagent du calcul.

### À l'échelle (1000+ pairs)

C'est un **multi-IA distribué décentralisé**.

```
1000+ pairs:
- Modèles disponibles: 50+ (de phi-2 à GPT-4 class)
- Uptime: 99.9% (toujours quelqu'un de connecté)
- Latence: <500ms pour n'importe quel modèle
- GPU: des centaines de GPU partagés
- RAM distribuée: des terabytes virtuels

→ Un utilisateur avec un Raspberry Pi peut utiliser
  des modèles qui nécessitent 40GB de RAM
→ Les conversations restent sur sa machine
→ Il ne paie rien
→ Ses données ne quittent jamais son appareil
```

### L'effet réseau est exponentiel

| Pairs | Capacité | Analogie |
|-------|----------|----------|
| 1 | 1 modèle, ta machine | Ton PC tout seul |
| 10 | 5 modèles, sharding partiel | Un groupe d'amis |
| 100 | 20+ modèles, redondance | Un forum actif |
| 1000 | 50+ modèles, RAID RAM | Un service IA |
| 10000+ | Super-ordinateur distribué | Un movement |

**Plus de monde = plus de capacités = plus de gens qui rejoignent = plus de capacités.**

C'est exactement comme BitTorrent :
- 1 seeder → téléchargement lent
- 10 seeders → ça commence à aller
- 1000 seeders → plus rapide que n'importe quel serveur

**Sauf qu'au lieu de partager des fichiers, on partage de l'intelligence.**

### Pourquoi c'est différent des services centralisés

| | OpenAI / Anthropic | PinkyBrain |
|---|---|---|
| Plus d'utilisateurs | Serveurs surchargés | Plus de capacités |
| Coût | 20$/mois par utilisateur | Gratuit (chacun participe) |
| Données | Leurs serveurs | Tes machines |
| Disponibilité | Dépend de leur infra | Dépend du réseau = résilient |
| Censure | Ils décident | Personne ne décide |

### La promesse

**Un Raspberry Pi de 35€ + PinkyBrain = accès à une IA qui vaut des milliers d'euros.**

Pas parce qu'on a des serveurs. Parce que d'autres humains partagent leurs machines. Comme BitTorrent a rendu le partage de fichiers libre, PinkyBrain rend l'accès à l'IA libre.

**La seule condition : participer.** Tu donnes un peu de CPU/RAM, tu reçois beaucoup d'IA. Plus tu donnes, plus tu reçois. Mais même à 0, tu as accès — juste plus lentement.

C'est pas du communisme. C'est pas du capitalisme. C'est de la **symbiose**.

---

## 🧠 brain.llm — Le cerveau qui grandit avec le réseau

### La boucle de croissance

```
  Plus de pairs
      ↓
  Plus de modèles disponibles
      ↓
  Plus de requêtes traitées
      ↓
  brain.llm apprend de chaque interaction
      ↓
  brain.llm devient meilleur pour :
    - Router les requêtes (quel modèle pour quel type de question)
    - Prédire la charge (anticiper les pics d'utilisation)
    - Optimiser le sharding (quels chunks où)
    - Équilibrer le réseau (redistribuer intelligemment)
      ↓
  Meilleure expérience pour tout le monde
      ↓
  Plus d'utilisateurs rejoignent
      ↓
  (retour au début)
```

### Ce que brain.llm fait déjà

brain.llm est le cerveau d'PinkyBrain. Il est déjà intégré dans le nœud :

```python
# Endpoints existants dans pinkybrain_v5.py
/api/brain/status     → État du cerveau (modèles, latence, santé)
/api/brain/models     → Modèles disponibles (local + cloud + P2P)
/api/brain/query      → Requête IA avec routage intelligent
/api/brain/consensus  → Consensus multi-modèles (3+ modèles votent)
/api/brain/chain      → Enchaînement de requêtes (décomposition de tâches)
```

### Ce que brain.llm apprend du mesh public

**Routage adaptatif** — Quand une requête arrive, brain.llm sait :
- Quel modèle est le plus rapide pour ce type de question
- Quel pair a le moins de latence en ce moment
- Quel pair est fiable (score de contribution) vs quel pair est nouveau
- Si un modèle local est assez bon ou s'il faut aller chercher un cloud model

**Prédiction de charge** — brain.llm observe les patterns :
- "Entre 20h et 23h, y a plus de monde connecté"
- "Le matin, les requêtes sont plus longues (travail)"
- "Le week-end, plus de requêtes créatives"
- Il pré-charge les modèles qui seront demandés

**Optimisation du sharding** — Avec le scheduler adaptatif :
- brain.llm décide où placer les chunks en fonction de la fiabilité des pairs
- Si un pair est souvent déconnecté entre 22h et 6h → ne pas lui confier de chunks critiques
- Si un pair a une connexion rapide → lui donner les chunks qui servent souvent

**Consensus pour la qualité** — Quand un nœud du mesh reçoit une requête importante :
```python
# Au lieu d'un seul modèle :
response = brain_llm.query("Explique la relativité", model="glm-5.1")

# Consensus multi-modèles :
response = brain_llm.consensus("Explique la relativité", models=["glm-5.1", "llama3", "mistral"])
# → Les 3 modèles répondent
# → brain.llm compare et retourne la meilleure réponse
# → Ou combine les 3 pour une réponse plus riche
```

### Le cycle vertueux

```
Utilisateur avec un vieux PC
    ↓
Rejoint le mesh (gratuit)
    ↓
Partage 2GB RAM + 30% CPU
    ↓
Accède à 50+ modèles IA
    ↓
Ses conversations restent sur SA machine
    ↓
brain.llm apprend de ses patterns d'utilisation
    ↓
Routage de plus en plus précis
    ↓
Latence qui diminue, qualité qui augmente
    ↓
L'utilisateur parle de PinkyBrain à ses amis
    ↓
Plus d'utilisateurs
    ↓
Meilleur réseau pour tout le monde
```

### brain.llm n'est pas une IA centrale

**Important :** brain.llm n'est PAS un modèle central qui contrôle tout. C'est un orchestrateur distribué.

Chaque nœud a son propre brain.llm. Ils se coordonnent via le mesh. Si un brain.llm tombe, les autres prennent le relais. Il n'y a pas de point de défaillance central.

brain.llm apprend localement (de son propre nœud) et partage les insights via le mesh (mémoire CRDT). C'est de l'intelligence distribuée, pas de la centralisation.

### La vision finale

**PinkyBrain = cerveau collectif.**

Pas un cerveau qui contrôle. Un cerveau qui **coordone**, **apprend**, et **s'adapte** — collectivement, de manière distribuée.

Chaque humain qui rejoint rend le réseau plus intelligent. Chaque machine qui partage rend le réseau plus puissant. Et brain.llm est le tissu nerveux qui connecte tout ça.

**Plus on est, plus on est intelligent.**

---

## 🔒 Isolation Réseau Privé / Réseau Public — CRITIQUE

### Règle absolue : LES DEUX RÉSEAUX SONT ISOLÉS

**Le réseau public n'a JAMAIS accès au réseau privé. Point final.**

```
┌─────────────────────────────────────────────────────────────────┐
│                        NODE (You)                              │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  RÉSEAU PRIVÉ (p2p_secret)                              │   │
│  │                                                         │   │
│  │  • Accès par p2p_secret UNIQUEMENT                      │   │
│  │  • Mémoire P2P synchronisée (CRDT)                      │   │
│  │  • Messagerie privée                                    │   │
│  │  • Tous les endpoints privés                            │   │
│  │  • Conversations "synced"                               │   │
│  │                                                         │   │
│  │  🔒 PAS ACCESSIBLE DEPUIS LE MESH PUBLIC               │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  RÉSEAU PUBLIC (mesh)                                   │   │
│  │                                                         │   │
│  │  • Accès par Ed25519 + Web of Trust                     │   │
│  │  • Tracker public                                       │   │
│  │  • Routage de requêtes IA                              │   │
│  │  • Partage de modèles / CPU / RAM                       │   │
│  │  • Conversations "public" (opt-in EXPLICITE)            │   │
│  │                                                         │   │
│  │  🔒 PAS ACCESSIBLE DEPUIS LE RÉSEAU PRIVÉ              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ⛔ JAMAIS DE PONT ENTRE LES DEUX                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Ce que le mesh public PEUT voir

| Information | Visible par le mesh public | Raison |
|---|---|---|
| Nom du nœud | ✅ Oui | Pour la découverte |
| Clé publique Ed25519 | ✅ Oui | Pour la vérification des signatures |
| Modèles partagés | ✅ Oui | Pour le routage des requêtes |
| CPU/RAM/GPU partagés | ✅ Oui | Pour le sharding |
| Score de contribution | ✅ Oui | Pour les quotas |
| Uptime | ✅ Oui | Pour la fiabilité |

### Ce que le mesh public NE PEUT PAS voir

| Information | Visible par le mesh public | Raison |
|---|---|---|
| p2p_secret | ❌ JAMAIS | Clé du réseau privé |
| Clé privée Ed25519 | ❌ JAMAIS | Signature uniquement |
| Pairs du réseau privé | ❌ JAMAIS | Isolation complète |
| Mémoire P2P (CRDT) | ❌ JAMAIS | Données privées |
| Messagerie privée | ❌ JAMAIS | Communications privées |
| Conversations "private" | ❌ JAMAIS | Données utilisateur |
| Conversations "synced" | ❌ JAMAIS | Sync privé uniquement |
| Config complète | ❌ JAMAIS | Contient des secrets |
| IP des pairs privés | ❌ JAMAIS | Isolation réseau |
| Endpoints privés | ❌ JAMAIS | Isolation réseau |

### Ce que le mesh public NE PEUT PAS faire

1. **Accéder au réseau privé** — Le mesh n'a pas le p2p_secret, ne peut pas s'authentifier
2. **Découvrir les pairs privés** — Le tracker public ne connaît que les nœuds du mesh
3. **Consommer les ressources privées** — Le Resource Guard sépare les quotas
4. **Lire la mémoire privée** — Les endpoints mémoire nécessitent l'auth privée
5. **Envoyer des messages privés** — La messagerie est sur un port séparé avec auth privée
6. **Utiliser les modèles privés** — Seuls les modèles dans `models_share` sont visibles

### Isolation technique

```python
# Chaque requête passe par l'un de ces filtres :

async def handle_request(self, request):
    auth = self._verify_auth(request)  # Auth privée (p2p_secret)
    
    if auth and auth.get("method") in ("ed25519", "hmac"):
        # → RÉSEAU PRIVÉ
        # Accès complet à : mémoire, messagerie, pairs, config, etc.
        return await self.handle_private_request(request, auth)
    
    mesh_auth = self._verify_mesh_auth(request)  # Auth publique (Ed25519 Web of Trust)
    
    if mesh_auth:
        # → RÉSEAU PUBLIC
        # Accès LIMITÉ à : requêtes IA (models_share uniquement), status basique
        return await self.handle_mesh_request(request, mesh_auth)
    
    # → AUCUN ACCÈS
    return web.json_response({"error": "Unauthorized"}, status=401)
```

### Ports et interfaces

| Service | Port | Réseau | Auth |
|---|---|---|---|
| API privée | 8080/8081 | Privé (p2p_secret) | HMAC + Ed25519 |
| Messagerie | 8082/8083 | Privé (p2p_secret) | HMAC |
| Mémoire CRDT | 8084/8085 | Privé (p2p_secret) | HMAC |
| Mesh public | 8090 | Public | Ed25519 Web of Trust |
| Tracker | — | Public (HTTPS) | Clé Ed25519 signée |

**Le mesh public écoute sur un PORT SÉPARÉ (8090).** Il n'y a aucune connexion possible entre le port 8090 et les ports privés.

### Qu'est-ce qu'un nœud public NE PEUT PAS faire sur TON nœud ?

Même si quelqu'un découvre ton IP via le tracker public :

- ❌ Il ne peut PAS voir tes pairs privés
- ❌ Il ne peut PAS lire ta mémoire CRDT
- ❌ Il ne peut PAS accéder à ta messagerie
- ❌ Il ne peut PAS voir tes conversations
- ❌ Il ne peut PAS utiliser tes modèles privés (seulement ceux dans `models_share`)
- ❌ Il ne peut PAS consommer plus que tes limites (`max_cpu_percent`, `max_ram_share_mb`)
- ❌ Il ne peut PAS dépasser le quota de contribution (score-based)
- ❌ Il ne peut PAS contourner le Resource Guard

### Le seul pont possible : explicite et volontaire

Le seul moment où les deux réseaux interagissent, c'est quand l'utilisateur le décide **explicitement** :

1. **Partager un modèle** — L'utilisateur met un modèle dans `models_share` → le mesh peut l'utiliser
2. **Partager du CPU/RAM** — L'utilisateur configure `max_cpu_percent` et `max_ram_share_mb` → le mesh peut les utiliser, dans les limites
3. **Conversation "public"** — L'utilisateur change le privacy level d'une conversation à "public" → elle peut être partagée

**JAMAIS automatique. JAMAIS sans consentement.**

### Vérification au démarrage

```python
async def start(self):
    # Vérifier l'isolation au démarrage
    if self.public_mesh_enabled:
        # Le mesh public doit écouter sur un port DIFFÉRENT
        assert self.mesh_port != self.private_port, \
            "SECURITY: Public mesh must use a separate port!"
        
        # Le p2p_secret ne doit JAMAIS être envoyé au tracker
        assert "p2p_secret" not in self.tracker_announcement, \
            "SECURITY: p2p_secret must never appear in public announcements!"
        
        # Les modèles partagés doivent être explicitement listés
        if not self.config.get("models_share"):
            logger.warning("⚠️  Public mesh enabled but no models shared")
        
        logger.info(f"🔒 Network isolation verified:")
        logger.info(f"   Private: port {self.private_port} (p2p_secret)")
        logger.info(f"   Public:  port {self.mesh_port} (Ed25519 Web of Trust)")
```

---

## 📂 Dossier de Partage — La Frontière entre Privé et Public

### Le problème sans dossier de partage

Sans dossier de partage dédié, le mesh devrait scanner TOUT le système de fichiers pour trouver des modèles :
- ❌ Risque de fuiter des chemins privés
- ❌ Difficile de contrôler ce qui est partagé
- ❌ Un modèle supprimé pourrait encore être annoncé au mesh
- ❌ Impossible de séparer modèles privés et publics

### La solution : `shared_models/`

Un dossier dédié qui est la **seule interface** entre tes modèles et le mesh public.

```
~/.pinkybrain/
├── conversations/        → 🔒 Privé (jamais partagé)
├── memory/               → 🔒 Privé (jamais partagé)
├── config/               → 🔒 Privé (jamais partagé)
├── messenger/            → 🔒 Privé (jamais partagé)
│
├── shared_models/        → 🌐 Zone de partage (visible au mesh)
│   ├── glm-5.1/          → Symlink vers ~/.ollama/models/glm-5.1
│   ├── llama3/           → Copie ou symlink
│   └── mistral/          → Copie ou symlink
│
└── ollama/               → 🔒 Stockage Ollama (privé)
    └── models/           → Tous les modèles installés
```

### Comment ça marche

**L'utilisateur choisit exactement quoi partager :**

```bash
# Partager un modèle (crée un lien symbolique)
pinkybrain share glm-5.1

# Arrêter de partager un modèle (supprime le lien)
pinkybrain unshare glm-5.1

# Voir ce qui est partagé
pinkybrain shared
```

**Le mesh ne voit QUE ce qui est dans `shared_models/` :**

```python
class ModelShareManager:
    """Manages the shared_models directory — the ONLY bridge to the public mesh."""
    
    SHARED_DIR = os.path.expanduser("~/.pinkybrain/shared_models")
    
    def share_model(self, model_name: str) -> bool:
        """Share a model with the public mesh.
        
        Creates a symlink from the model's actual location to shared_models/.
        The mesh can ONLY see models in this directory.
        """
        # 1. Verify the model exists locally
        model_path = self._find_model(model_name)
        if not model_path:
            return False
        
        # 2. Create symlink in shared_models/
        link_path = os.path.join(self.SHARED_DIR, model_name)
        os.symlink(model_path, link_path)
        
        # 3. Announce to tracker
        self.tracker.announce_update()
        
        return True
    
    def unshare_model(self, model_name: str) -> bool:
        """Stop sharing a model. Removes from shared_models/ only.
        
        The original model stays in the private Ollama directory.
        The mesh immediately loses access to it.
        """
        link_path = os.path.join(self.SHARED_DIR, model_name)
        if os.path.islink(link_path):
            os.unlink(link_path)
            self.tracker.announce_update()
            return True
        return False
    
    def get_shared_models(self) -> list:
        """List models visible to the public mesh.
        
        ONLY returns models in shared_models/.
        NEVER scans the private Ollama directory.
        """
        models = []
        for name in os.listdir(self.SHARED_DIR):
            path = os.path.join(self.SHARED_DIR, name)
            if os.path.islink(path) or os.path.isdir(path):
                size = self._get_model_size(path)
                models.append({
                    "name": name,
                    "size_mb": size,
                    "shared_since": os.path.getctime(path)
                })
        return models
    
    def _find_model(self, model_name: str) -> Optional[str]:
        """Find a model in the private Ollama directory.
        
        This is PRIVATE — the mesh NEVER calls this function.
        Only the local user can share/unshare models.
        """
        # Check Ollama models directory
        ollama_path = os.path.expanduser(f"~/.ollama/models/{model_name}")
        if os.path.exists(ollama_path):
            return ollama_path
        return None
```

### Avantages du dossier de partage

| | Sans dossier de partage | Avec `shared_models/` |
|---|---|---|
| Contrôle | Le mesh voit tout | L'utilisateur choisit exactement quoi partager |
| Sécurité | Chemins privés exposés | Seuls les symlinks sont visibles |
| Arrêt immédiat | Must edit config + restart | `pinkybrain unshare glm-5.1` = instantané |
| Séparation | Privé et public mélangés | Frontière nette physique |
| Audit | Difficile de savoir quoi est partagé | `ls shared_models/` = tout est là |
| Isolation | Le mesh pourrait scanner le système | Le mesh ne voit QUE ce dossier |

### Règles d'or

1. **Le mesh ne lit JAMAIS en dehors de `shared_models/`** — Pas de scan du système de fichiers
2. **Les symlinks sont unidirectionnels** — Le mesh suit le lien pour lire le modèle, mais ne peut PAS écrire ou modifier le modèle original
3. **`unshare` = suppression instantanée** — Dès que le symlink est supprimé, le mesh ne voit plus le modèle
4. **Pas de copie par défaut** — Les symlinks économisent l'espace disque. L'utilisateur peut choisir de copier si nécessaire
5. **Les téléchargements du mesh vont DANS `shared_models/`** — Si un autre nœud partage un modèle et que tu le télécharges, il va dans `shared_models/`, pas dans ton Ollama privé
6. **`models_share` dans la config = liste de modèles dans `shared_models/`** — Les deux doivent correspondre

### Téléchargement de modèles depuis le mesh

Quand tu télécharges un modèle partagé par un autre nœud :

```
1. Tu découvres "mistral-7b" via le tracker
2. Tu télécharges les chunks depuis les pairs qui l'ont
3. Les chunks sont assemblés dans ~/.pinkybrain/shared_models/mistral-7b/
4. Tu peux ensuite le partager à ton tour (il est déjà dans shared_models/)
5. OU le déplacer dans ton Ollama privé avec: pinkybrain privatize mistral-7b
```

```bash
# Télécharger un modèle depuis le mesh
pinkybrain download mistral-7b

# Le modèle arrive dans shared_models/ (zone publique)
ls ~/.pinkybrain/shared_models/mistral-7b/

# Si tu veux le rendre privé (déplacer dans Ollama)
pinkybrain privatize mistral-7b

# Si tu veux le garder partagé + l'utiliser en privé aussi
pinkybrain share mistral-7b  # déjà partagé, ça crée un lien des deux côtés
```

### Le cycle de vie d'un modèle

```
INSTALLÉ (privé)
    ↓  pinkybrain share glm-5.1
PARTAGÉ (public, via symlink dans shared_models/)
    ↓  pinkybrain unshare glm-5.1  
INSTALLÉ (privé, symlink supprimé, modèle intact)

TÉLÉCHARGÉ DEPUIS LE MESH
    ↓  pinkybrain download mistral-7b
PARTAGÉ (dans shared_models/, visible au mesh)
    ↓  pinkybrain privatize mistral-7b
INSTALLÉ (déplacé dans Ollama privé, plus visible au mesh)
```

**Le dossier de partage est la porte. L'utilisateur a la clé.**

---

## 🖥️ Interface Utilisateur — PinkyBrain Desktop

### Philosophie

**Si tu as besoin d'un terminal pour l'utiliser, c'est pas fini.**

L'interface doit être aussi simple que uTorrent ou Spotify. Tu l'ouvres, tu comprends, tu l'utilises.

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    PinkyBrain Desktop                         │
│                    (Web UI — localhost:8080)                  │
│                                                              │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │
│  │ 💬 Chat  │ │ 📊 Share │ │ 🔒 Net   │ │ ⚙️ Config│           │
│  │         │ │         │ │         │ │         │           │
│  │ Requêtes│ │ Ressourc│ │ Privé/  │ │ Paramètr│           │
│  │ IA      │ │ es      │ │ Public  │ │ es      │           │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘           │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Barre latérale gauche                                │   │
│  │                                                      │   │
│  │ 🟢 Connecté — 12 pairs sur le mesh                  │   │
│  │ CPU: 23% utilisé | RAM: 1.2GB / 2GB partagés        │   │
│  │                                                      │   │
│  │ 💬 Conversations                                     │   │
│  │   ├─ 📝 Potager en ville (hier)                     │   │
│  │   ├─ 📝 Code Python (2h)                            │   │
│  │   └─ 📝 Recette crêpes (3 jours)                    │   │
│  │                                                      │   │
│  │ 🤖 Modèles disponibles                              │   │
│  │   ├─ 🟢 glm-5.1 (local)                             │   │
│  │   ├─ 🟡 llama3 (mesh — 45ms)                       │   │
│  │   └─ 🟡 mistral (mesh — 120ms)                     │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

### Onglet 1 : 💬 Chat (requêtes et réponses)

```
┌─────────────────────────────────────────────────────────┐
│  💬 Chat                                                 │
│                                                          │
│  ┌─────────────────────────────────────────────────────┐ │
│  │                                                     │ │
│  │  🧑 Denis: Comment faire un potager en ville?       │ │
│  │                                                     │ │
│  │  🤖 glm-5.1: Un potager en ville, c'est un acte     │ │
│  │  de résistance. Voici les étapes...                  │ │
│  │                                                     │ │
│  │  1. Choisir un balcon ou terrasse ensoleillé         │ │
│  │  2. Utiliser des bacs en bois ou en zinc...          │ │
│  │                                                     │ │
│  │  [Modèle: glm-5.1 | Local | 1.2s | 234 tokens]      │ │
│  │                                                     │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌─────────────────────────────────┐ ┌────────────────┐ │
│  │ Écris ton message...             │ │ ▶ Envoyer      │ │
│  └─────────────────────────────────┘ └────────────────┘ │
│                                                          │
│  Modèle: [glm-5.1 ▼]  Strategie: [auto ▼]              │
│  Confidentialité: [🔒 Privé ▼]                          │
└─────────────────────────────────────────────────────────┘
```

**Fonctionnalités :**
- Historique complet des conversations (jamais effacé)
- Recherche dans l'historique
- Choix du modèle (local + mesh)
- Indicateur de latence et provenance
- Niveau de confidentialité par conversation
- Export en Markdown/JSON

### Onglet 2 : 📊 Partage de Ressources

```
┌─────────────────────────────────────────────────────────┐
│  📊 Partage de Ressources                                │
│                                                          │
│  ┌─ Ressources Partagées ─────────────────────────────┐ │
│  │                                                     │ │
│  │  CPU ━━━━━━━━━━━━━━━━━━━━━━━━━━░░░░  30%           │ │
│  │       Maximum: 30%  ┃  Actuel: 12% utilisé          │ │
│  │       [━━━━━━━━━━━━━━━░░░░░░░░] slider              │ │
│  │                                                     │ │
│  │  RAM ━━━━━━━━━━━━━━━━━━━━━━━░░░░░░  2 GB           │ │
│  │       Maximum: 2GB  ┃  Actuel: 0.8GB utilisé       │ │
│  │       [━━━━━━━━━━━━━━━░░░░░░░░] slider              │ │
│  │                                                     │ │
│  │  GPU  [✗] Partager mon GPU                           │ │
│  │       ⚠️ Activer uniquement si vous ne jouez pas     │ │
│  │                                                     │ │
│  │  Bande passante ━━━━━━━━━━━░░░░░  5 Mbps           │ │
│  │       [━━━━━━━━━━━━━━━░░░░░░░░] slider              │ │
│  │                                                     │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌─ Modèles Partagés ─────────────────────────────────┐ │
│  │                                                     │ │
│  │  🟢 glm-5.1 (2.1GB)  [✓ Partagé] [✗ Arrêter]      │ │
│  │  🟡 llama3 (4.7GB)    [✗ Non partagé] [Partager]    │ │
│  │  ⚫ mistral (7.2GB)   [✗ Non partagé] [Partager]    │ │
│  │                                                     │ │
│  │  [+ Installer un modèle depuis le mesh]             │ │
│  │                                                     │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌─ Statistiques ─────────────────────────────────────┐ │
│  │                                                     │ │
│  │  Score de contribution: 42 🌟                      │ │
│  │  Requêtes servies: 128                              │ │
│  │  Quota public: 20 req/min                          │ │
│  │  Uptime: 3j 14h                                    │ │
│  │                                                     │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                          │
│  ⚠️ Votre PC est actuellement utilisé — partage en pause │
│  [Reprendre le partage]                                  │
└─────────────────────────────────────────────────────────┘
```

**Fonctionnalités :**
- Sliders pour ajuster CPU/RAM/GPU/bande passante
- Toggle par modèle pour partager/arrêter
- Statistiques en temps réel
- Auto-pause quand le PC est occupé
- Score de contribution et quota associé

### Onglet 3 : 🔒 Réseau

```
┌─────────────────────────────────────────────────────────┐
│  🔒 Réseau                                               │
│                                                          │
│  ┌─ Réseau Privé ─────────────────────────────────────┐ │
│  │                                                     │ │
│  │  🔒 Privé — p2p_secret                              │ │
│  │  ┌───────┐    ┌───────┐                            │ │
│  │  │ Bug   │◄──►│ Pinky │    2 pairs connectés       │ │
│  │  └───────┘    └───────┘                            │ │
│  │  192.168.1.100     192.168.1.101                  │ │
│  │  Status: 🟢 Connecté                               │ │
│  │                                                     │ │
│  │  [Ajouter un pair] [Générer invitation]             │ │
│  │                                                     │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌─ Réseau Public (Mesh) ─────────────────────────────┐ │
│  │                                                     │ │
│  │  🌐 Public — 12 pairs connectés                     │ │
│  │                                                     │ │
│  │  ┌──────────┐  CPU: 4 cores  RAM: 8GB              │ │
│  │  │ Node #42 │  🟢 glm-5.1, llama3                  │ │
│  │  └──────────┘  Score: 85 | Latence: 23ms            │ │
│  │                                                     │ │
│  │  ┌──────────┐  CPU: 2 cores  RAM: 4GB              │ │
│  │  │ Node #78 │  🟢 mistral                          │ │
│  │  └──────────┘  Score: 72 | Latence: 45ms           │ │
│  │                                                     │ │
│  │  ┌──────────┐  CPU: 8 cores  RAM: 16GB             │ │
│  │  │ Node #91 │  🟢 glm-5.1, mistral, phi3          │ │
│  │  └──────────┘  Score: 95 | Latence: 12ms           │ │
│  │                                                     │ │
│  │  [Rafraîchir] [Rejoindre le mesh] [Quitter]         │ │
│  │                                                     │ │
│  │  ⚠️ Mesh public désactivé — [Activer]               │ │
│  │                                                     │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌─ Isolation vérifiée ───────────────────────────────┐ │
│  │                                                     │ │
│  │  ✅ Réseau privé sur port 8081 (p2p_secret)        │ │
│  │  ✅ Mesh public sur port 8090 (Ed25519)            │ │
│  │  ✅ Aucune donnée privée visible publiquement       │ │
│  │  ✅ Resource Guard actif                            │ │
│  │                                                     │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### Onglet 4 : ⚙️ Configuration

```
┌─────────────────────────────────────────────────────────┐
│  ⚙️ Configuration                                        │
│                                                          │
│  ┌─ Général ──────────────────────────────────────────┐ │
│  │                                                     │ │
│  │  Nom du nœud: [Pinky                     ]         │ │
│  │  Langue: [Français ▼]                              │ │
│  │  Thème: [🌙 Sombre ▼]                             │ │
│  │                                                     │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌─ Réseau Privé ──────────────────────────────────────┐ │
│  │                                                     │ │
│  │  P2P Secret: [••••••••••••] [Changer]               │ │
│  │  Pairs: 2 connectés                                 │ │
│  │                                                     │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌─ Mesh Public ───────────────────────────────────────┐ │
│  │                                                     │ │
│  │  [✓] Activer le mesh public                         │ │
│  │  Tracker: [https://tracker.pinkybrain.ai    ]       │ │
│  │  Priorité: [Locale d'abord ▼]                       │ │
│  │  Mode furtif: [✗] (visible sur le tracker)          │ │
│  │                                                     │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌─ Stockage ─────────────────────────────────────────┐ │
│  │                                                     │ │
│  │  Modèles privés: ~/.ollama/models/ (8.2GB)         │ │
│  │  Modèles partagés: ~/.pinkybrain/shared_models/     │ │
│  │  Conversations: ~/.pinkybrain/conversations/         │ │
│  │  [Ouvrir le dossier] [Exporter tout]                │ │
│  │                                                     │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌─ Avancé ────────────────────────────────────────────┐ │
│  │                                                     │ │
│  │  [✓] Auto-pause le partage quand le PC est occupé   │ │
│  │  Seuil CPU: [70% ▼]                                 │ │
│  │  Seuil RAM: [85% ▼]                                 │ │
│  │  [✓] Chiffrer les conversations localement           │ │
│  │  [✗] Mode développeur                               │ │
│  │                                                     │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                          │
│  [Sauvegarder]  [Réinitialiser]                          │
└─────────────────────────────────────────────────────────┘
```

### Technologies

- **Frontend :** HTML/CSS/JS vanilla (pas de framework lourd)
- **Backend :** aiohttp existant (ajout d'endpoints API)
- **WebSocket :** pour les mises à jour en temps réel (statut, pairs, ressources)
- **Responsive :** fonctionne sur PC, tablette et téléphone
- **PWA :** installable comme app desktop/mobile

### Pourquoi une Web UI et pas une app native

1. **Pas de dépendances** — Un navigateur, c'est tout
2. **Cross-platform** — Linux, Mac, Windows, téléphone
3. **Légère** — Pas d'Electron (500MB de RAM pour rien)
4. **Mise à jour automatique** — Rafraîchir la page = dernière version
5. **Accessible à distance** — Depuis n'importe quel appareil sur le réseau
6. **PWA** — Installable comme une app native si voulu

### Endpoints API pour l'UI

```python
# Chat
POST   /api/chat                    # Envoyer un message, recevoir une réponse
GET    /api/conversations           # Lister les conversations
GET    /api/conversations/{id}      # Charger une conversation
DELETE /api/conversations/{id}      # Supprimer une conversation
POST   /api/conversations/{id}/export # Exporter une conversation

# Ressources
GET    /api/resources/status        # État actuel (CPU, RAM, GPU)
POST   /api/resources/config        # Modifier les limites
GET    /api/resources/history        # Historique d'utilisation

# Modèles
GET    /api/models                  # Modèles disponibles (local + mesh)
POST   /api/models/{name}/share     # Partager un modèle
POST   /api/models/{name}/unshare   # Arrêter de partager
POST   /api/models/{name}/download  # Télécharger depuis le mesh

# Réseau
GET    /api/network/private/peers   # Pairs privés
GET    /api/network/mesh/nodes      # Nœuds du mesh public
POST   /api/network/mesh/join       # Rejoindre le mesh
POST   /api/network/mesh/leave      # Quitter le mesh

# Config
GET    /api/config                  # Configuration actuelle
POST   /api/config                  # Modifier la configuration

# WebSocket
WS     /ws                          # Temps réel (statut, pairs, messages)
```

### Principes de design

1. **Simple d'abord** — Un nouveau utilisateur doit comprendre en 30 secondes
2. **Pas de jargon technique** — "Partager" pas "activer le endpoint", "Modèles IA" pas "LLM providers"
3. **Feedback immédiat** — Chaque action a une réponse visuelle
4. **Sûr par défaut** — Tout est privé, le mesh est opt-in
5. **Pas de page blanche** — Les conversations sont toujours là

---

## 🚀 Modes de Déploiement — Service, Application, Sidekick, Plugin

### Les 4 modes

PinkyBrain doit fonctionner dans 4 modes différents, pour 4 types d'utilisation :

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  🔧 SERVICE          → Tourne en fond, sans GUI                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  systemd / docker                                       │   │
│  │  Pour serveurs, VPS, machines sans écran                │   │
│  │  Auto-démarrage, auto-restart, logs                     │   │
│  │  API HTTP + WebSocket sur localhost                     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  🖥️ APPLICATION      → GUI complète, fenêtre principale       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Fenêtre native ou navigateur                           │   │
│  │  Chat, partage, réseau, config — tout est là            │   │
│  │  Pour l'utilisateur qui veut tout voir                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  📍 SIDEKICK         → Icône dans la barre système            │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Menu contextuel, notifications, mini-chat              │   │
│  │  Tourne en fond, GUI minimale                           │   │
│  │  Pour l'utilisation quotidienne sans encombrer l'écran  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  🔌 PLUGIN           → Intégré dans un autre logiciel         │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Extension navigateur, plugin VS Code, plugin Obsidian   │   │
│  │  API légère, pas de GUI propre                          │   │
│  │  Pour utiliser PinkyBrain dans son workflow              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Mode 1 : 🔧 Service (headless)

Pour les serveurs, VPS, machines sans écran.

```bash
# Installer en service systemd
sudo pinkybrain install-service

# Démarrer
sudo systemctl start pinkybrain

# Statut
sudo systemctl status pinkybrain

# Logs
journalctl -u pinkybrain -f

# Mode Docker
docker run -d \
  -p 8080:8080 \
  -p 8090:8090 \
  -v ~/.pinkybrain:/data \
  -e P2P_SECRET=your-secret \
  pinkybrain/server:latest
```

**Caractéristiques :**
- Pas de GUI, API HTTP uniquement
- Auto-démarrage au boot
- Auto-restart en cas de crash
- Logs dans journald
- Configuration via fichier ou variables d'environnement
- Port 8080 (privé) + 8090 (mesh public)
- Peut être exposé via reverse proxy (nginx)

**Fichier de service :**
```ini
# /etc/systemd/system/pinkybrain.service
[Unit]
Description=PinkyBrain P2P AI Network
After=network.target ollama.service
Wants=ollama.service

[Service]
Type=simple
User=pinkybrain
Group=pinkybrain
WorkingDirectory=/opt/pinkybrain
ExecStart=/usr/local/bin/pinkybrain serve --config /etc/pinkybrain/config.json
Restart=always
RestartSec=5
Environment=P2P_SECRET=%p
Environment=OLLAMA_HOST=127.0.0.1:11434

# Sécurité
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/var/lib/pinkybrain /var/log/pinkybrain
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
```

**Dockerfile :**
```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir pinkybrain

RUN useradd -m -d /data pinkybrain
USER pinkybrain

VOLUME /data
EXPOSE 8080 8090

HEALTHCHECK --interval=30s --timeout=5s \
    CMD curl -f http://localhost:8080/api/ping || exit 1

CMD ["pinkybrain", "serve", "--config", "/data/config.json"]
```

### Mode 2 : 🖥️ Application (GUI complète)

Pour l'utilisateur qui veut tout voir et tout contrôler.

```bash
# Lancer l'application
pinkybrain app

# Ou directement
pinkybrain  # (défaut = mode application)
```

**Caractéristiques :**
- Fenêtre principale avec les 4 onglets (Chat, Partage, Réseau, Config)
- Démarrage automatique du serveur en arrière-plan
- Notifications de bureau (nouveaux pairs, requêtes, etc.)
- Icône dans la barre des tâches
- Fermeture de la fenêtre = minimise en sidekick (ne quitte pas)
- Quitter complètement via menu contextuel

**Lancement :**
```bash
# L'application ouvre le navigateur sur localhost:8080
# Le serveur tourne en arrière-plan
# L'interface web est l'UI
pinkybrain app --open-browser

# Ou en mode natif (PyWebView)
pinkybrain app --native

# Ou en mode TUI (terminal)
pinkybrain app --tui
```

**Auto-start au démarrage (optionnel) :**
```bash
pinkybrain app --install-autostart
# Crée ~/.config/autostart/pinkybrain.desktop
```

### Mode 3 : 📍 Sidekick (barre système)

Pour l'utilisation quotidienne — discret mais toujours là.

```bash
# Lancer en sidekick
pinkybrain sidekick
```

**Caractéristiques :**
- Icône dans la barre système (tray icon)
- Menu contextuel par clic droit :
  ```
  🟢 PinkyBrain — 12 pairs
  ├─ 💬 Ouvrir le chat
  ├─ 📊 Partage: 2GB RAM, 30% CPU
  ├─ 🔄 Rejoindre/Quitter le mesh
  ├─ ⏸️ Mettre en pause
  ├─ ⚙️ Préférences
  └─ ❌ Quitter
  ```
- Notifications :
  - "Nouveau pair sur le mesh : Node #42"
  - "Partage en pause — votre PC est occupé"
  - "Requête reçue de Node #78"
- Mini-popup de chat (réponses rapides)
- Le serveur tourne en arrière-plan
- Double-clic = ouvrir l'application complète

**Technologie :**
- Linux : AppIndicator / ayatana-python
- macOS : rumps (Python)
- Windows : pystray
- Cross-platform : webview popup

**Installation :**
```bash
# Installer le sidekick en auto-start
pinkybrain sidekick --install

# Désinstaller
pinkybrain sidekick --uninstall
```

### Mode 4 : 🔌 Plugin (intégré)

Pour utiliser PinkyBrain dans son workflow.

```bash
# Extension navigateur
pinkybrain plugin --browser

# Plugin VS Code
pinkybrain plugin --vscode

# Plugin Obsidian
pinkybrain plugin --obsidian

# Plugin Terminal
pinkybrain plugin --terminal
```

**4a. Extension Navigateur (Chrome/Firefox)**

- Icône PinkyBrain dans la barre d'outils
- Popup de chat rapide
- Sélection de texte → clic droit → "Demander à PinkyBrain"
- Injection de l'IA dans les formulaires web
- Tourne en background script, communique avec localhost:8080

**4b. Plugin VS Code**

- Panel latéral "PinkyBrain"
- Chat intégré dans l'éditeur
- Sélection de code → clic droit → "Expliquer / Refactorer / Corriger"
- Complétion IA (optionnel)
- Conversations sauvegardées dans le workspace

**4c. Plugin Obsidian**

- Panel latéral PinkyBrain
- Chat dans Obsidian
- Insertion de réponses dans les notes
- Recherche dans les conversations passées
- Tags automatiques

**4d. Plugin Terminal**

```bash
# Mode terminal interactif
pinkybrain chat

# Une seule requête
pinkybrain ask "Comment faire un potager en ville?"

# Pipe
echo "Explique ce code" | pinkybrain ask

# Mode daemon (communique avec l'instance en cours)
pinkybrain chat --daemon
```

### Architecture commune

Les 4 modes partagent le même cœur :

```
                    ┌─────────────────────────┐
                    │    PinkyBrain Core       │
                    │    (pinkybrain_v5.py)    │
                    │                          │
                    │  ┌──────────────────┐    │
                    │  │ Resource Guard    │    │
                    │  │ Tracker Client    │    │
                    │  │ Adaptive Scheduler│   │
                    │  │ Conversation Store│    │
                    │  │ Model Share Mgr   │    │
                    │  │ Brain LLM         │    │
                    │  └──────────────────┘    │
                    └─────────────────────────┘
                              │
                    ┌─────────┴──────────┐
                    │    API Layer        │
                    │  (aiohttp + WS)     │
                    └─────────┬──────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
   ┌──────┴──────┐   ┌───────┴──────┐   ┌───────┴──────┐
   │  🔧 Service  │   │ 🖥️ App/Sidekick│   │ 🔌 Plugin   │
   │  (headless)  │   │  (Web UI)      │   │  (extension) │
   │              │   │                │   │              │
   │ CLI + API    │   │ GUI complète   │   │ Popup + API  │
   │ systemd      │   │ Tray icon      │   │ VS Code      │
   │ Docker       │   │ Notifications  │   │ Navigateur   │
   └──────────────┘   └────────────────┘   └──────────────┘
```

### Un seul binaire, 4 façons de l'utiliser

```bash
# Service (headless)
pinkybrain serve

# Application (GUI)
pinkybrain app

# Sidekick (tray icon)
pinkybrain sidekick

# Plugin (API only)
pinkybrain plugin --vscode

# Chat terminal
pinkybrain chat

# Une seule requête
pinkybrain ask "question"

# Statut
pinkybrain status

# Partager un modèle
pinkybrain share glm-5.1

# Arrêter de partager
pinkybrain unshare glm-5.1

# Rejoindre le mesh public
pinkybrain mesh join

# Quitter le mesh
pinkybrain mesh leave

# Voir les pairs
pinkybrain peers
```

### Distribution

```bash
# PyPI
pip install pinkybrain

# Docker
docker pull pinkybrain/server:latest

# AppImage (Linux)
chmod +x PinkyBrain-x86_64.AppImage
./PinkyBrain-x86_64.AppImage sidekick

# Homebrew (macOS)
brew install pinkybrain

# AUR (Arch Linux)
yay -S pinkybrain

# Snap
sudo snap install pinkybrain
```

---

## ⚡ Partage de CPU/RAM — Pas juste des modèles

### Le modèle Ollama est insuffisant

Ollama seul, c'est : "J'ai un modèle sur ma machine, tu peux m'envoyer des requêtes."

Mais si ton PC a seulement 2GB de RAM, tu ne peux PAS faire tourner un modèle de 8GB. Point final. Même si quelqu'un d'autre a le modèle, tu dois l'installer localement pour l'utiliser.

**Le partage de modèles sans partage de calcul = juste du routage.** Utile, mais pas révolutionnaire.

### Le vrai partage = CPU + RAM

Ce qui rend PinkyBrain différent, c'est que tu partages **la capacité de calcul**, pas juste l'accès aux modèles :

```
SCÉNARIO 1 : Partage de modèles uniquement (Ollama)

  Denis (2GB RAM) → Requête → Pair avec modèle 8GB → Réponse
  
  ✅ Denis peut utiliser le modèle
  ❌ La requête doit traverser le réseau
  ❌ Le pair doit charger TOUT le modèle dans SA RAM
  ❌ Si le pair se déconnecte → plus de modèle
  ❌ Latence = aller-retour réseau complet

SCÉNARIO 2 : Partage de CPU + RAM (PinkyBrain v5)

  Denis (2GB RAM) → Requête
  ├── Chunk 1 (2GB) sur Pair A → calcul couche 1-4
  ├── Chunk 2 (2GB) sur Pair B → calcul couche 5-8  
  ├── Chunk 3 (2GB) sur Pair C → calcul couche 9-12
  └── Chunk 4 (2GB) sur Pair D → calcul couche 13-16 → RÉPONSE
  
  ✅ Denis peut utiliser un modèle de 8GB
  ✅ Aucun pair n'a besoin de plus de 2GB de RAM
  ✅ Si un pair se déconnecte → réplica prend le relais
  ✅ Pipeline parallel = latence réduite
  ✅ C'EST ÇA LE VRAI PARTAGE
```

### Comment le partage CPU/RAM fonctionne

**1. Chaque pair annonce ses ressources disponibles**

```json
{
  "node_id": "ed25519_pubkey_hex",
  "capabilities": {
    "cpu_cores": 4,
    "cpu_share_percent": 30,
    "ram_total_mb": 16384,
    "ram_share_mb": 2048,
    "gpu": false,
    "models": ["glm-5.1:cloud"],
    "bandwidth_kbps": 10000
  }
}
```

**2. L'Adaptive Scheduler calcule la capacité totale du mesh**

```
12 pairs connectés:
  - Total CPU: 48 cores (partagés)
  - Total RAM partagée: 24.5 GB
  - GPU: 3 pairs avec GPU
  - Modèles: 8 modèles différents

→ Un modèle de 16GB peut tourner sur ce mesh
  car 24.5GB RAM disponible > 16GB nécessaire
→ Chaque pair ne charge qu'une fraction (1-2GB)
```

**3. Le scheduler place les chunks intelligemment**

```python
# Le scheduler décide où placer chaque chunk :
# - Pair avec le plus de RAM → chunks critiques (début du pipeline)
# - Pair avec GPU → chunks de calcul intensif (couches attention)
# - Pair fiable (high uptime) → chunks qui doivent rester stables
# - Pair rapide (low latency) → chunks fréquemment utilisés

# Équilibre : pas surcharger un pair, répartir équitablement
# Réplication : chaque chunk existe sur 2-3 pairs
```

**4. L'inference distribué (pipeline parallel)**

```
Token "Bonjour" entre dans le pipeline:

  [Pair A: Couches 1-4] → output_intermédiaire_1
         ↓ (envoi via réseau, ~5-20ms)
  [Pair B: Couches 5-8] → output_intermédiaire_2
         ↓ (envoi via réseau, ~5-20ms)
  [Pair C: Couches 9-12] → output_intermédiaire_3
         ↓ (envoi via réseau, ~5-20ms)
  [Pair D: Couches 13-16] → "Bonjour! Comment puis-je..."

  Latence totale: ~50-100ms par token (4 hops)
  Sur un mesh de 50+ pairs: ~30-50ms (pairs plus proches)
```

**5. Le Resource Guard protège chaque pair**

```python
# Pair A a configuré max_cpu=30%, max_ram=2GB
# Le mesh ne peut JAMAIS dépasser ces limites

resource_guard.can_accept_request()
# → Si CPU à 70% (utilisateur occupé): REFUSÉ
# → Si RAM disponible < 2GB: REFUSÉ  
# → Si CPU à 20% (utilisateur idle): ACCEPTÉ
# → Le chunk tourne dans les limites configurées
```

### Les 3 types de contribution

| Type | Ce que tu donnes | Ce que tu reçois |
|---|---|---|
| **Modèle** | Accès à un modèle IA que tu héberges | Score + accès aux modèles des autres |
| **CPU/RAM** | Puissance de calcul pour le sharding | Score + accès aux modèles lourds sans les installer |
| **Bande passante** | Relay de données entre pairs | Score + meilleure latence pour tes requêtes |

### Pourquoi c'est révolutionnaire

**Avant PinkyBrain :**
- Tu veux utiliser GPT-4 class → tu paies 20$/mois
- Ou tu achètes une RTX 4090 → 2000€
- Ou tu utilises un modèle 7B sur ton vieux PC → qualité médiocre

**Avec PinkyBrain :**
- Tu partages 2GB RAM + 30% CPU (que quand ton PC est libre)
- Le mesh combine ta contribution avec celle de 50 autres personnes
- Tu as accès à un modèle de 40GB qui tourne sur la RAM de tous
- Qualité GPT-4 class, gratuity, données chez toi

**Le CPU/RAM des autres C'est le data center.** Pas de serveur. Pas de cloud. Juste des humains qui partagent ce qu'ils ont.

### Barème de contribution CPU/RAM

| Contribution | Score/heure | Quota débloqué |
|---|---|---|
| 0 (rien) | 0 | 1 req/5min (lecture seule) |
| 1GB RAM | +5 | 5 req/min |
| 2GB RAM | +10 | 10 req/min |
| 4GB RAM | +20 | 20 req/min |
| 10% CPU | +3 | +2 req/min |
| 30% CPU | +8 | +5 req/min |
| 50% CPU | +12 | +10 req/min |
| GPU | +15 | +15 req/min |
| Modèle partagé | +10 | +5 req/min |
| 24h uptime | +5 | bonus fidélité |

**Le score s'accumule pendant que tu partages.** Plus tu partages longtemps, plus ton score est élevé, plus tu as accès au réseau. C'est de la symbiose, pas de la charité.

---

## 🔐 Données de Réponse Privées — Chiffrement de Bout en Bout

### Le problème

Sans chiffrement, quand tu fais une requête sur le mesh distribué :

```
Ta question: "Comment faire un potager en ville?"
    ↓
[Pair A: Couches 1-4]  → voit ta question en clair ❌
    ↓
[Pair B: Couches 5-8]  → voit le résultat intermédiaire ❌
    ↓
[Pair C: Couches 9-12] → voit le résultat intermédiaire ❌
    ↓
[Pair D: Couches 13-16] → voit la réponse finale en clair ❌
    ↓
Toi: tu reçois la réponse

Problème: 4 inconnus ont lu ta question et ta réponse.
```

**C'est inacceptable.** Tes données sont à toi. Les pairs du mesh sont des inconnus.

### La solution : E2E Encryption (End-to-End)

```
Ta question: "Comment faire un potager en ville?"
    ↓
[Chiffré avec la clé du pipeline]
    ↓
[Pair A: reçoit des données chiffrées, déchiffre localement, calcule, rechiffre] ✅
    ↓
[Pair B: reçoit des données chiffrées, déchiffre localement, calcule, rechiffre] ✅
    ↓
[Pair C: reçoit des données chiffrées, déchiffre localement, calcule, rechiffre] ✅
    ↓
[Pair D: reçoit des données chiffrées, déchiffre localement, calcule, rechiffre] ✅
    ↓
Toi: tu déchiffres la réponse finale avec TA clé

Résultat: personne d'autre que toi ne peut lire la question OU la réponse.
```

### Architecture du chiffrement

```
┌──────────────────────────────────────────────────────────────────┐
│                   Pipeline Chiffré                               │
│                                                                  │
│  Toi (demandeur)                                                 │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ 1. Génère une clé de session aléatoire (ECDH)            │    │
│  │ 2. Chiffre la question avec la clé de session            │    │
│  │ 3. Pour chaque pair du pipeline:                          │    │
│  │    a. Établit un canal ECDH avec le pair                  │    │
│  │    b. Dérive une clé de chunk partagée avec ce pair       │    │
│  │    c. Le pair peut déchiffrer SON chunk, pas les autres   │    │
│  │ 4. Envoie les données chiffrées dans le pipeline          │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Chaque pair dans le pipeline:                                   │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ 1. Reçoit des données chiffrées                           │    │
│  │ 2. Déchiffre avec SA clé de chunk (pas celle des autres) │    │
│  │ 3. Calcule SON chunk (couches du modèle)                  │    │
│  │ 4. Rechiffre le résultat avec la clé du chunk suivant     │    │
│  │ 5. Envoie au pair suivant                                │    │
│  │                                                           │    │
│  │ ⚠️ Le pair ne voit QUE:                                  │    │
│  │    - Les tenseurs d'entrée/sortie de SON chunk            │    │
│  │    - PAS la question originale                            │    │
│  │    - PAS la réponse finale                                │    │
│  │    - PAS les données des autres chunks                   │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Toi (récepteur)                                                 │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ 1. Reçoit la réponse chiffrée                            │    │
│  │ 2. Déchiffre avec TA clé de session                       │    │
│  │ 3. Seul toi peux lire la réponse finale                   │    │
│  └──────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

### Qu'est-ce que chaque pair peut voir ?

| Donnée | Visible par le pair ? | Pourquoi |
|---|---|---|
| Question originale | ❌ NON | Chiffrée par la clé du demandeur |
| Réponse finale | ❌ NON | Chiffrée par la clé du demandeur |
| Tenseurs d'entrée de SON chunk | ✅ Oui | Nécessaire pour le calcul |
| Tenseurs de sortie de SON chunk | ✅ Oui | Résultat du calcul |
| Tenseurs des autres chunks | ❌ NON | Chiffrés avec les clés des autres pairs |
| Identité du demandeur | ❌ NON | Anonyme via le tracker |
| Historique des requêtes | ❌ NON | Pas stocké par les pairs |

**Un pair voit des nombres aléatoires (tenseurs chiffrés) et son propre bout de calcul. C'est tout.**

### Niveaux de confidentialité

```json
{
  "conversation_privacy": "private",
  // "private"    → Chiffré E2E, stocké localement UNIQUEMENT
  // "synced"     → Chiffré E2E, sync via réseau privé UNIQUEMENT
  // "shared"     → Chiffré E2E, partage avec pairs spécifiques
  // "public"     → Non chiffré, contribution au mesh (OPT-IN EXPLICITE)
}
```

**Par défaut : PRIVATE.** Toujours. Les autres niveaux nécessitent une action explicite de l'utilisateur.

### En pratique pour l'utilisateur

```
Toi: "Comment faire un potager en ville?"

→ PinkyBrain:
  1. Chiffre ta question
  2. Trouve 4 pairs pour le pipeline
  3. Chaque pair calcule SON chunk (ne voit que des nombres)
  4. Rechiffre et passe au suivant
  5. Tu déchiffres la réponse

→ Personne d'autre que toi ne peut lire la question ou la réponse.
→ Même pas nous. Même pas les pairs qui ont calculé.
→ C'est mathématiquement impossible sans ta clé.
```

### Ce qui est stocké sur le mesh

**RIEN.**

Les pairs du mesh :
- ❌ Ne stockent PAS les requêtes
- ❌ Ne stockent PAS les réponses
- ❌ Ne loggent PAS les questions
- ❌ Ne peuvent PAS déchiffrer les données
- ❌ Ne peuvent PAS associer une requête à un utilisateur

**Seul le demandeur a la clé de session.** Le pair traite des tenseurs, pas du texte. Il ne sait même pas quelle langue parle le demandeur.

### Comparaison avec les services centralisés

| | OpenAI / Claude | PinkyBrain |
|---|---|---|
| Ta question | Stockée sur leurs serveurs | Chiffrée E2E |
| Ta réponse | Stockée sur leurs serveurs | Chiffrée E2E |
| Qui peut lire ? | OpenAI/Anthropic + gouvernements | Toi UNIQUEMENT |
| Utilisation des données | Entraînement, profilage | Aucune |
| Conservation | Indéfinie (leurs CGU) | Supprimée à la fin de la requête |
| Transparence | "On peut lire vos données" | "Mathématiquement impossible" |

### Implémentation technique

```python
class E2EEncryption:
    """End-to-End Encryption for distributed inference pipeline."""
    
    def __init__(self, node_identity):
        self.identity = node_identity  # Ed25519 keypair
    
    async def create_pipeline_session(self, peer_keys: list) -> PipelineSession:
        """Create an encrypted pipeline session with the given peers.
        
        Each peer gets a unique derived key. No peer can read
        another peer's data. Only the requester can read the final result.
        """
        # 1. Generate ephemeral session key (X25519)
        session_key = X25519PrivateKey.generate()
        
        # 2. For each peer in the pipeline:
        #    - ECDH key exchange → shared secret
        #    - Derive chunk-specific key from shared secret
        #    - Peer can only decrypt/encrypt its own chunk
        peer_sessions = []
        for i, peer_key in enumerate(peer_keys):
            shared = session_key.exchange(peer_key)
            chunk_key = HKDF(
                shared,
                info=f"pinkybrain-chunk-{i}".encode(),
                length=32
            )
            peer_sessions.append(PeerChunkSession(
                peer_index=i,
                chunk_key=chunk_key,
                peer_public_key=peer_key
            ))
        
        # 3. The requester keeps the session private key
        #    Only they can decrypt the final result
        return PipelineSession(
            session_private=session_key,
            peer_sessions=peer_sessions
        )
    
    def encrypt_for_chunk(self, data: bytes, chunk_key: bytes) -> bytes:
        """Encrypt data for a specific chunk in the pipeline."""
        # AES-256-GCM with chunk_key
        # Each chunk uses a different key
        # No chunk can read another chunk's data
        nonce = os.urandom(12)
        cipher = AESGCM(chunk_key)
        return nonce + cipher.encrypt(nonce, data, None)
    
    def decrypt_from_chunk(self, data: bytes, chunk_key: bytes) -> bytes:
        """Decrypt data from a specific chunk."""
        nonce = data[:12]
        cipher = AESGCM(chunk_key)
        return cipher.decrypt(nonce, data[12:], None)
```

### Ce que ça signifie

**Tes conversations avec l'IA sont à toi. Point final.**

- Pas de serveur central qui les lit
- Pas de pairs du mesh qui les voient
- Pas de journalisation
- Pas de profilage
- Pas d'entraînement sur tes données
- Pas de gouvernements qui peuvent les demander

**C'est pas une promesse. C'est de la cryptographie.** Même si tous les pairs du mesh étaient compromis, ils ne pourraient pas lire tes données sans ta clé de session. Et ta clé de session n'existe que sur ta machine, le temps de la requête.
