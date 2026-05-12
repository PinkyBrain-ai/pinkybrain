# Resource Limits — Contrôle CPU/RAM

**PinkyBrain permet de contrôler les ressources utilisées pour éviter de consommer tout le système.**

---

## 🎯 Pourquoi ?

Par défaut, PinkyBrain peut utiliser beaucoup de ressources car :
- Il peut gérer plusieurs queries simultanées
- Les queries d'LLM sont CPU-intensive
- Les modèles consomment plusieurs GB RAM

Les utilisateurs peuvent vouloir :
- Garder des ressources pour d'autres tâches (travail, jeux, etc.)
- Éviter de surchauffer la machine
- Contrôler les coûts (si c'est une instance cloud)

---

## 🔧 Configuration

Fichier : `p2p_config.toml`

```toml
[resource_limits]
# Limites CPU et RAM
cpu_limit_percent = 50          # Max CPU par peer (0-100)
ram_limit_percent = 70          # Max RAM par peer (0-100)

# Limites de requests
max_concurrent_requests = 3     # Queries simultanées
request_timeout_seconds = 60    # Timeout par query
query_queue_max_size = 50       # Taille max de queue
```

### Explications

| Option | Valeur par défaut | Description |
|--------|------------------|-------------|
| `cpu_limit_percent` | 50 | Pourcentage max de CPU utilisé. Si le système est à 40% et un query arrive, PinkyBrain peut le prendre. Si à 50%, il refuse. |
| `ram_limit_percent` | 70 | Pourcentage max de RAM utilisé. Fonctionne comme CPU. |
| `max_concurrent_requests` | 3 | Nombre maximum de queries en même temps. Plus = plus rapide mais plus gourmand. |
| `request_timeout_seconds` | 60 | Temps max pour une query. Si dépassé, annuler et retourner erreur. |
| `query_queue_max_size` | 50 | Taille de la queue de requests. Si plein, requests sont rejetés avec message "Queue full". |

---

## 📊 Exemples de Configuration

### Configuration Légère (pour un PC de bureau)

```toml
[resource_limits]
cpu_limit_percent = 30          # Peu de CPU
ram_limit_percent = 40          # Peu de RAM
max_concurrent_requests = 1     # Une query à la fois
request_timeout_seconds = 90
query_queue_max_size = 20
```

**Avantage :** Léger, ne dérange pas l'utilisateur
**Inconvénient :** Plus lent, queries peuvent attendre

---

### Configuration Moderne (PC de bureau moderne)

```toml
[resource_limits]
cpu_limit_percent = 50
ram_limit_percent = 70
max_concurrent_requests = 3
request_timeout_seconds = 60
query_queue_max_size = 50
```

**Avantage :** Bon compromis vitesse/ressources
**Inconvénient :** Prend un peu de ressources

---

### Configuration Performance (serveur dédié)

```toml
[resource_limits]
cpu_limit_percent = 90
ram_limit_percent = 90
max_concurrent_requests = 10
request_timeout_seconds = 120
query_queue_max_size = 200
```

**Avantage :** MAXIMAL performance
**Inconvénient :** Prend toutes les ressources (pas recommandé pour PC personnels)

---

### Configuration Économique (instance cloud peu coûteuse)

```toml
[resource_limits]
cpu_limit_percent = 20
ram_limit_percent = 30
max_concurrent_requests = 1
request_timeout_seconds = 60
query_queue_max_size = 10
```

**Avantage :** Coût minimal pour instance cloud
**Inconvénient :** Très lent, peut saturer vite

---

## 🖥️ Vérifier l'utilisation

Le système peut afficher l'utilisation actuelle des ressources.

### Avec PinkyBrain CLI

```bash
# Vérifier l'utilisation actuelle
pinkybrain status

# Affiche :
#   CPU usage : 25%
#   RAM usage : 35%
#   Active requests : 1
```

### Avec le script de test

```bash
cd ~/.pinkybrain
python3 -c "from resource_limits import print_current_usage; print_current_usage()"
```

**Sortie :**
```
📊 Current System Resource Usage:
   CPU  : 25.3%
   RAM  : 35.7%
   Time : 2026-03-26T21:30:45
```

---

## 🚨 Comportement quand limites sont atteintes

Si PinkyBrain atteint les limites :

1. **CPU/RAM limite atteinte** → Rejette la request immédiatement
   - Renvoie : `{ 'error': 'Resource limit exceeded', 'reason': 'CPU/RAM too high' }`

2. **Queue pleine** → Rejette la request
   - Renvoie : `{ 'error': 'Queue full', 'queue_size': X }`

3. **Timeout query** → Annule la query en cours
   - Renvoie : `{ 'error': 'Request timeout', 'timeout_seconds': 60 }`

---

## 🔄 Configuration à l'exécution

Il est possible de changer les limites à l'exécution (sans redémarrer) :

```python
# Dans p2p_core.py après démarrage
peer.resource_monitor.configure(
    cpu_limit_percent=80,
    ram_limit_percent=80,
    max_concurrent_requests=5
)
```

**Avantage :** Pas besoin de redémarrer
**Inconvénient :** Les changements ne sont pas persistants (modifiez p2p_config.toml pour persistance)

---

## 💡 Tips

**1. Adapter à votre usage :**
- Si vous jouez → `cpu_limit_percent = 20`, `ram_limit_percent = 30`
- Si vous codez → `cpu_limit_percent = 50`, `ram_limit_percent = 70`
- Si la machine est idle → `cpu_limit_percent = 80`, `ram_limit_percentage = 90`

**2. Surveiller l'utilisation :**
```bash
# Linux/macOS
watch -n 2 "ps aux | grep ollama"

# Windows
wmic process where "name='ollama.exe'" get ProcessId,WorkingSetSize,CPU
```

**3. Adapter aux modèles :**
- `phi3-mini` → Peut fonctionner avec plus de requests
- `glm-4.7` → Besoin de plus de RAM (20+ GB), donc moins de requests
- `qwen3:8b` → Bon compromis

**4. Surveiller les logs :**
```bash
pinkybrain logs | grep "Resource limit"
```

---

## 📈 Monitoring

PinkyBrain inclut des stats pour les ressources :

```json
{
  "resource_limits": {
    "config": {
      "cpu_limit": 50,
      "ram_limit": 70,
      "max_concurrent": 3,
      "queue_max": 50,
      "request_timeout": 60
    },
    "current": {
      "active_requests": 1,
      "total_handled": 150,
      "rejected": 5
    },
    "system": {
      "cpu": 25.3,
      "ram": 35.7,
      "timestamp": "2026-03-26T21:30:45"
    }
  }
}
```

**Disponible via :**
- HTTP GET `/status` endpoint
- CLI `pinkybrain status`

---

## 🐛 Debug

Si PinkyBrain refuse trop de requests :

1. **Vérifier les limites sont trop strictes**
   - Augmenter `cpu_limit_percent` / `ram_limit_percent`

2. **Vérifier les modèles ne consomment pas trop**
   - Les gros modèles (glm-4.7) consomment 15-20 GB RAM

3. **Vérifier les concurrents**
   - Augmenter `max_concurrent_requests` si la machine le peut

4. **Vérifier la CPU**
   - Si CPU à 80%+, PinkyBrain va refuser

5. **Vérifier la RAM**
   - Ouvrir un terminal et `free -h` (Linux) ou `top` (macOS)

---

## 🔚 Conclusion

Les resource limits sont optionnels mais recommandés pour les PC personnels.

**Conseil :** Commencez avec les valeurs par défaut, puis adaptez à votre usage.

—

🐛 **Bug** — *"Contrôler les ressources, c'est contrôler la performance."*