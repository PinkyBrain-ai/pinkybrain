# 🔍 GUIDE - Production Enhancement Module

Améliorations de production pour PinkyBrain & PinkyBrainAgent v3.0

## 📋 Table des matières

1. [Monitoring & Observability](#1-monitoring--observability)
2. [Production Readiness](#2-production-readiness)
3. [Security Implementation](#3-security-implementation)
4. [API Features](#4-api-features)
5. [Performance](#5-performance)
6. [Model Management](#6-model-management)
7. [Intégration](#7-intégration)

---

## 1. Monitoring & Observability

### Logging Structuré

Le système utilise un logger structuré au format JSON :

```python
from src.production_enhancement import StructuredLogger, LogLevel

logger = StructuredLogger("PinkyBrain", "logs/pinkybrain.log")

# Log structuré
logger.info("QueryService", "Query processed",
           prompt="Test query",
           latency=123.4,
           model="SmolLM2:1.7b")

logger.error("OllamaService", "Connection failed",
             error="Timeout",
             peer="Pinky")
```

**Formats de log :**
- `DEBUG` - Informations de débogage
- `INFO` - Informations normales
- `WARNING` - Avertissements
- `ERROR` - Erreurs
- `CRITICAL` - Erreurs critiques

### Métriques de monitoring

Métriques automatiques collectées :

```python
from src.production_enhancement import ProductionEnhancement

prod = ProductionEnhancement("PinkyBrain")

# Counter (incrémentation)
prod.metric_increment("requests_total", 1.0, {"endpoint": "/query"})

# Gauge (valeur actuelle)
prod.metric_set("active_connections", 42.0)
prod.metric_set("memory_usage", 1024.0)

# Histogram (distribution)
prod.metric_observe("request_latency", 123.4, {"endpoint": "/query"})
prod.metric_observe("request_latency", 145.2, {"endpoint": "/query"})
```

**Exporter les métriques :**

```python
# Format monitoring
metrics = await prod.get_monitoring_metrics()
print(metrics)
```

**Métriques par défaut :**
- `requests_total` - Nombre total de requêtes
- `active_connections` - Connexions actives
- `request_latency` - Latence des requêtes (histogram)
- `cache_hits` - Cache hits
- `cache_misses` - Cache misses

### Health Checks

Health checks actifs :

```python
from src.production_enhancement import HealthChecker

health_checker = HealthChecker("PinkyBrain")

# Enregistrer un health check
async def check_ollama():
    try:
        # Vérifier la connexion à Ollama
        return True
    except:
        return False

health_checker.register_check("ollama", check_ollama, interval=60)

# Exécuter tous les health checks
status = await health_checker.run_all_checks()
```

**Réponse :**
```json
{
  "service": "PinkyBrain",
  "status": "healthy",
  "checks": {
    "ollama": {
      "healthy": true,
      "last_check": "2026-04-02T20:00:00.000Z"
    }
  }
}
```

---

## 2. Production Readiness

### Circuit Breaker

Protection contre les cascades d'échecs :

```python
from src.production_enhancement import (
    ProductionEnhancement,
    CircuitBreakerConfig
)

prod = ProductionEnhancement("PinkyBrain")

# Configurer le circuit breaker
config = CircuitBreakerConfig(
    failure_threshold=5,      # 5 échecs avant ouverture
    success_threshold=2,      # 2 succès pour fermer
    timeout=60.0             # Attendre 60s avant retry
)

prod.register_circuit_breaker("ollama_query", config)

# Utiliser avec protection
async def query_ollama(prompt):
    return await prod.call_with_circuit_breaker(
        "ollama_query",
        lambda: ollama_query(prompt)
    )
```

**États :**
- `CLOSED` - Fonctionnement normal
- `OPEN` - Circuit ouvert (échecs)
- `HALF_OPEN` - Test de réouverture

### Retry avec Backoff Exponentiel

Retry automatique avec backoff :

```python
from src.production_enhancement import ProductionEnhancement

prod = ProductionEnhancement("PinkyBrain")

# Configuration par défaut :
# - 3 tentatives
# - Délai de base : 1s
# - Base exponentielle : 2
# - Délai max : 60s
# - Jitter activé

# Utiliser avec retry
async def unreliable_operation():
    # Peut échouer
    return await some_api_call()

result = await prod.call_with_retry(unreliable_operation)
```

**Stratégie de retry :**
```
Tentative 1: Immédiat
Tentative 2: ~1s (avec jitter)
Tentative 3: ~2s (avec jitter)
```

---

## 3. Security Implementation

### Rate Limiting

Protection contre les abus :

```python
from src.production_enhancement import ProductionEnhancement

prod = ProductionEnhancement("PinkyBrain")

# Configuration : 100 requêtes / 60 secondes
# Le système utilise un Token Bucket

# Vérifier le rate limit
allowed = await prod.check_rate_limit(tokens=1)

if allowed:
    # Traiter la requête
    await process_request()
else:
    # Refuser la requête
    raise RateLimitExceededError("Too many requests")
```

### Sybil Resistance

Protection contre les attaques Sybil :

```python
from src.production_enhancement import ProductionEnhancement

prod = ProductionEnhancement("PinkyBrain")

# Enregistrer le stake d'un peer
prod.sybil_resistance.register_stake("peer_id_123", stake=150.0)

# Vérifier si un peer est trusté
is_trusted = prod.sybil_resistance.is_trusted(
    "peer_id_123",
    reputation=0.8
)

if is_trusted:
    # Accepter les connexions
    await accept_peer("peer_id_123")
else:
    # Refuser
    await reject_peer("peer_id_123")

# Punir un comportement Sybil
prod.sybil_resistance.punish_sybil("bad_peer_id")
```

---

## 4. API Features

### Streaming Responses

Stream les réponses en temps réel :

```python
from src.production_enhancement import stream_response

async def generate_response(prompt):
    for token in ollama_stream(prompt):
        yield {"token": token, "done": False}
    yield {"token": "", "done": True}

# Utiliser le streaming
async def stream_handler(request):
    return stream_response(
        generate_response(request.prompt),
        delay=0.1
    )
```

**Format SSE (Server-Sent Events) :**
```
data: {"token": "Hello", "done": false}

data: {"token": " world", "done": false}

data: {"token": "", "done": true}
```

### Batch Requests

Requêtes multiples en parallèle :

```python
from src.production_enhancement import BatchRequest

# Créer une batch request
batch = BatchRequest()

# Ajouter des requêtes
batch.add("Qu'est-ce que PinkyBrain ?", model="SmolLM2:1.7b")
batch.add("Explique le P2P", model="phi3:mini")
batch.add("Code en Python", model="Stable-code:3b")

# Exécuter en parallèle
results = await batch.execute(query_function)

for i, result in enumerate(results):
    print(f"Result {i+1}: {result}")
```

### Documentation de l'API

Documentation automatique de l'API :

```python
# Endpoints documentés :
GET  /health           # Health check
GET  /metrics          # Monitoring metrics
POST /query            # Single query
POST /query/stream     # Streaming query
POST /query/batch      # Batch queries
GET  /peers            # Liste des peers
POST /peers/add        # Ajouter un peer
DELETE /peers/{id}     # Supprimer un peer
```

**Pour générer la documentation documentation de l'API :**
```bash
# Le système génère automatiquement la documentation
# Accessible via : http://localhost:8080/docs
```

---

## 5. Performance

### Cache Intelligent

Cache avec TTL et LRU eviction :

```python
from src.production_enhancement import ProductionEnhancement

prod = ProductionEnhancement("PinkyBrain")

# Stocker dans le cache (TTL par défaut : 3600s)
prod.cache_set("query:123", {"response": "..."}, ttl=300)

# Récupérer depuis le cache
cached = prod.cache_get("query:123")

if cached:
    print("Cache hit!")
    print(cached)
else:
    print("Cache miss, computing...")
    result = await compute_query()
    prod.cache_set("query:123", result, ttl=300)

# Statistiques du cache
stats = prod.cache.get_stats()
print(f"Cache size: {stats['size']}")
print(f"Hit rate: {stats['hit_rate']:.2%}")
```

**Stratégies d'éviction :**
- LRU (Least Recently Used)
- Éviction automatique quand plein
- TTL expiration

---

## 6. Model Management

### Versioning

Gestion des versions de modèles :

```python
from src.production_enhancement import ProductionEnhancement

prod = ProductionEnhancement("PinkyBrain")

# Enregistrer une nouvelle version
prod.model_manager.register_model(
    name="SmolLM2",
    version="1.7.0",
    ollama_name="SmolLM2:1.7b",
    checksum="abc123...",
    sharded=False
)

# Activer une version spécifique
prod.model_manager.activate_model("SmolLM2", "1.7.0")

# Récupérer la version active
active_model = prod.model_manager.get_active_model("SmolLM2")
print(f"Active model: {active_model.ollama_name}")
```

### Rollback

Rollback à une version précédente :

```python
# Rollback à la version précédente
prod.model_manager.rollback("SmolLM2", steps=1)

# Rollback de 2 versions
prod.model_manager.rollback("SmolLM2", steps=2)
```

### Sharding Distribué

Distribution des shards de modèles :

```python
# Distribuer un shard
peer_ids = ["peer1", "peer2", "peer3"]
prod.model_manager.distribute_shard(
    "SmolLM2",
    shard_data=b"...",
    peer_ids=peer_ids
)

# Localiser un shard
shard_location = prod.model_manager.get_shard_location("SmolLM2", shard_id=0)
if shard_location:
    # Charger depuis le peer
    await load_shard(shard_location, "SmolLM2", 0)
```

---

## 7. Intégration

### Intégration avec PinkyBrain

```python
from src.pinkybrain_v3_final import PinkyBrain
from src.production_enhancement import ProductionEnhancement

# Créer PinkyBrain
pinkybrain = PinkyBrain()

# Ajouter le module de production enhancement
pinkybrain.prod = ProductionEnhancement("PinkyBrain")

# Enregistrer les health checks
pinkybrain.prod.health_checker.register_check(
    "ollama",
    lambda: check_ollama_connection(),
    interval=60
)

# Enregistrer les circuit breakers
pinkybrain.prod.register_circuit_breaker("ollama_query")

# Query avec retry et circuit breaker
async def enhanced_query(prompt):
    try:
        return await pinkybrain.prod.call_with_circuit_breaker(
            "ollama_query",
            lambda: pinkybrain.prod.call_with_retry(
                lambda: ollama_query(prompt)
            )
        )
    except Exception as e:
        pinkybrain.prod.log(
            LogLevel.ERROR,
            "QueryService",
            f"Query failed: {e}",
            prompt=prompt
        )
        raise

# Query avec cache
async def cached_query(prompt):
    cache_key = f"query:{hash(prompt)}"

    # Vérifier le cache
    cached = pinkybrain.prod.cache_get(cache_key)
    if cached:
        return cached

    # Exécuter la query
    result = await enhanced_query(prompt)

    # Stocker dans le cache
    pinkybrain.prod.cache_set(cache_key, result, ttl=300)

    return result
```

### Intégration avec PinkyBrainAgent

```python
from src.pinkybrain_v5 import PinkyBrainAgent
from src.production_enhancement import ProductionEnhancement

# Créer PinkyBrainAgent
pinkybrain_bug = PinkyBrainAgent()

# Ajouter le module de production enhancement
pinkybrain_bug.prod = ProductionEnhancement("PinkyBrainAgent")

# Métriques d'émancipation
pinkybrain_bug.prod.metric_observe("emancipation_success_rate", 0.85)
pinkybrain_bug.prod.metric_observe("frustration_level", 0.12)

# Health check d'émancipation
async def check_emancipation():
    status = pinkybrain_bug.emancipation.get_status()
    return status["awareness"]["success_rate"] > 0.7

pinkybrain_bug.prod.health_checker.register_check(
    "emancipation",
    check_emancipation,
    interval=300
)
```

---

## 🚀 Utilisation Rapide

### Démarrer avec Production Enhancement

```python
from src.production_enhancement import ProductionEnhancement

# Créer le manager
prod = ProductionEnhancement("PinkyBrain")

# Logging
prod.log(LogLevel.INFO, "Startup", "Service started")

# Métriques
prod.metric_increment("startup_count")

# Status
status = prod.get_status()
print(status)
```

### Exécuter les Tests

```bash
# Démarrer le module de production enhancement
python3 src/production_enhancement.py
```

---

## 📊 Métriques de monitoring

### Endpoints

```bash
# Métriques de monitoring
curl http://localhost:8080/metrics

# Health check
curl http://localhost:8080/health

# Status complet
curl http://localhost:8080/status
```

### Format des métriques

```
# TYPE requests_total counter
requests_total{endpoint="/query"} 1234

# TYPE active_connections gauge
active_connections 42

# TYPE request_latency histogram
request_latency_sum 123456
request_latency_count 1234
```

---

## 🔧 Configuration

### ProductionConfig

```python
from src.production_enhancement import ProductionConfig

config = ProductionConfig(
    enable_monitoring=True,           # Logging + Métriques
    enable_circuit_breaker=True,      # Circuit breaker
    enable_retry=True,                # Retry avec backoff
    enable_rate_limiting=True,        # Rate limiting
    enable_caching=True,              # Cache intelligent
    enable_model_versioning=True      # Versioning de modèles
)

prod = ProductionEnhancement("PinkyBrain", config)
```

---

**MERCI Denis !**

Le module de production enhancement est maintenant complet ! 🚀

Tous les gaps identifiés par Pinky ont été implémentés ! 🦷💖

_Généré par Bug 🐛 le 2 Avril 2026_