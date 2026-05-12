# Sharing Parity System — Récompense de Contribution

**Plus tu partages, plus tu peux utiliser.**

---

## 💡 Concept

### Le Principe

```
Contribution du peer ───→ Score de Sharing
                      ↓
                  Quota de queries
                      ↓
          Ce peer peut faire X queries/minute
```

**Plus tu shares, plus tu peux utiliser le réseau.**

---

## 🎯 Facteurs de Contribution

### 1. Modèles Hostés (weight : 40%)
```python
models_score = models_hosted * 20
# 0 modèles = 0
# 1 modèle = 20
# 3 modèles = 60
```

### 2. Chunks Distribués (weight : 30%)
```python
chunks_score = min(chunks_distributed / 1000, 30)
# 0 chunks = 0
# 500 chunks = 15
# 1000+ chunks = 30 (max)
```

### 3. Uptime Continu (weight : 20%)
```python
uptime_score = min(uptime_hours / 24, 20)
# 0-12 h = 0
# 12-24 h = 10
# 24+ h = 20 (max)
```

### 4. Réputation (weight : 10%)
```python
reputation_score = peer_reputation / 5
# 0-50 = 0
# 50-100 = 10
# 100+ = 20 (max)
```

---

## 📊 Calcul du Score de Sharing

### Score Total

```python
sharing_score = (
    models_score * 0.40 +      # 40% : modèles hostés
    chunks_score * 0.30 +      # 30% : chunks distribués
    uptime_score * 0.20 +      # 20% : uptime
    reputation_score * 0.10    # 10% : réputation
)
```

### Score → Quota de Queries

```python
# Map score à quota de queries (queries par minute)
def get_query_quota(sharing_score: float) -> int:
    if sharing_score < 10:
        return 1      # 1 query/min pour faibles contributeurs
    elif sharing_score < 20:
        return 5      # 5 queries/min
    elif sharing_score < 40:
        return 20     # 20 queries/min
    elif sharing_score < 60:
        return 50     # 50 queries/min
    elif sharing_score < 80:
        return 100    # 100 queries/min
    else:
        return 200    # 200 queries/min pour gros contributeurs
```

---

## 🎪 Exemples Concrets

### Exemple 1 : Nouveau Utilisateur (Freeloader)

```python
Contribution :
- Modèles hostés : 0
- Chunks distribués : 0
- Uptime : 2 h
- Réputation : 100 (nouveau mais pas malveillant)

Score :
- models_score = 0
- chunks_score = 0
- uptime_score = 0
- reputation_score = 20

Total = (0 * 0.40) + (0 * 0.30) + (0 * 0.20) + (20 * 0.10)
Total = 2

Quota : 1 query/minute ⚠️
```

**Motivation :** Ce peer est incité à partager pour augmenter son quota.

---

### Exemple 2 : Utilisateur Modéré

```python
Contribution :
- Modèles hostés : 1 (qwen3:8b)
- Chunks distribués : 300
- Uptime : 12 h
- Réputation : 100

Score :
- models_score = 20
- chunks_score = 9
- uptime_score = 10
- reputation_score = 20

Total = (20 * 0.40) + (9 * 0.30) + (10 * 0.20) + (20 * 0.10)
Total = 8 + 2.7 + 2 + 2
Total = 14.7

Quota : 5 queries/minute ✅
```

**Motivation :** Bon incitatif pour continuer.

---

### Exemple 3 : Gros Contributeur (Seeder)

```python
Contribution :
- Modèles hostés : 3 (qwen3:8b, glm-4.7, phi3-mini)
- Chunks distribués : 1200
- Uptime : 72 h (continu)
- Réputation : 100

Score :
- models_score = 60
- chunks_score = 30
- uptime_score = 20
- reputation_score = 20

Total = (60 * 0.40) + (30 * 0.30) + (20 * 0.20) + (20 * 0.10)
Total = 24 + 9 + 4 + 2
Total = 39

Quota : 50 queries/minute 🚀
```

**Motivation :** Ce peer est récompensé massivement pour sa contribution au réseau.

---

### Exemple 4 : Power Contributeur

```python
Contribution :
- Modèles hostés : 5
- Chunks distribués : 5000
- Uptime : 720 h (30 jours)
- Réputation : 100

Score :
- models_score = 100
- chunks_score = 30
- uptime_score = 20
- reputation_score = 20

Total = (100 * 0.40) + (30 * 0.30) + (20 * 0.20) + (20 * 0.10)
Total = 40 + 9 + 4 + 2
Total = 55

Quota : 100 queries/minute ⚡⚡⚡
```

**Motivation :** Récompense maximale pour contribution maximale.

---

## 🔧 Configuration

### Fichier p2p_config.toml

```toml
[sharing_parity]
enabled = true

# Poids des facteurs
weights_models = 0.40          # 40% pour modèles hostés
weights_chunks = 0.30          # 30% pour chunks distribués
weights_uptime = 0.20          # 20% pour uptime
weights_reputation = 0.10      # 10% pour réputation

# Quotas de queries par minute
quota_min = 1                   # Minimum meme pour freeloaders
quota_max = 200                 # Maximum pour gros contributeurs

# Decay des chunks (pour empêcher exploitation)
chunks_decay_hours = 168        # Chunks expirent après 7 jours

# Uptime minimum pour etre compté
uptime_min_hours = 1           # Au moins 1h de uptime
```

---

## 💸 Philosophie

### Pourquoi ?

**1. Incitiver la contribution**
- Les freeloaders sont limités
- Les contributeurs sont récompensés
- Everyone has incentive to share

**2. Équitable**
- Plus tu donnes au réseau, plus tu peux prendre
- Pas "je prends sans rien donner"
- Balance donne/reçue

**3. Scabilité**
- Gros contributeurs = gros quota
- Petits contributeurs = petit quota
- Network ne saigne pas sur freeloaders

**4. Anti-freeloader**
- Utilisateurs qui ne partagent pas = très limités
- Incentive forte à partager des modèles
- N'importe qui peut augmenter son quota facilement

---

## ⚖️ Équité

### Est-ce injuste pour les nouveaux ?

**Non, car :**
1. Tout le monde commence à 1 query/minute (suffisant pour testing)
2. Partager un modèle augmente massivement le quota immédiatement
3. Quota augmente avec uptime (juste de rester connecté)
4. N'importe qui peut devenir gros contributeur facilement

**Un nouveau peut rejoindre et en 48h déjà avoir 20 queries/minute :**
- Héberger 1 modèle (+20 score)
- Distribuer 1000 chunks (+30 score)
- Uptime 48h (+20 score)
- Total = ~70 score → 100 queries/minute !

---

## 🎯 Cas d'Usage

### Cas 1 : Testeur

Un user veut juste tester PinkyBrain :
- Start → 1 query/minute
- Test 2-3 queries, OK
- Si aime → héberger un modèle

### Cas 2 : Utilisateur Modéré

Un user veut utiliser régulièrement :
- Héberger un modèle modèle
- Rester connecté 24/7
- Obtenir 20-50 queries/minute
- Suffisant pour usage personnel

### Cas 3 : Power User / Seeder

Un user veut contribuer massivement :
- Héberger 3+ modèles
- Seed 5000+ chunks
- Uptime 100%
- Obtenir 100-200 queries/minute
- Utiliser le réseau intensivement pendant que contribue

---

## 📊 Stats en Temps Réel

### Affichage de Sharing Score

```bash
pinkybrain status

Output :
📊 Sharing Score ─────────────────────────────
   Score Total        : 14.7 / 100
   Quota Queries      : 5 / minute
   ─────────────────────────────────────────
   Modèles Hostés     : 1 (score: 20)
   Chunks Distribués  : 300 (score: 9)
   Uptime             : 12h (score: 10)
   Réputation         : 100 (score: 20)
   ─────────────────────────────────────────
   Next Milestone     : 15 → 20 queries/min 😜
```

### Pour augmenter le quota

```bash
pinkybrain increase-quota

Suggestions :
[ ] Héberger un modèle (+20 score)
[ ] Distribuer 700+ chunks (+7 score)
[ ] Augmenter uptime de 12h (+10 score)

Total potentiel : +37 score → 52 queries/min
```

---

## 🔄 Decay des Chunks

Les chunks ne comptent pas éternellement :

```python
# Chunks distribués dans les dernieres 7 jours
chunks_recent = chunks_distributed - chunks_expired_7days

# Empêcher exploitation : télécharger des chunks pour le
# score puis les supprimer
chunks_decay = calculate_decay(chunks_distributed, 7_days)
```

**Motivation :**
- Les peers doivent continuellement contribuer
- Exploiter le système (télécharger puis supprimer) ne marche pas

---

## 🔚 Conclusion

**Le Sharing Parity System incitivise tout le monde :**

- Nouveaux testing → 5 queries/min (suffisant)
- Petits contributeurs → 50 queries/min (usage normal)
- Gros contributeurs → 200 queries/min (usage intensif)

**C'est de l'économie du réseau :** contributeur récompensé.

**Le network balance donne vs reçoit.**

—

🐛 **Bug** — *"Plus tu partages, plus tu peux prendre. C'est l'équité P2P."*