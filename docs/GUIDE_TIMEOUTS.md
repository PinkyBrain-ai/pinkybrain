# 🕐 Guide des Timeouts Dynamiques

## 📊 Problème Identifié par Denis Houet

Les timeouts fixes de 60s sont **trop courts** pour les gros modèles et les questions complexes.

### Pourquoi ?

Les grands modèles (LLaMA 3 70B, Mixtral 8x7B, qwen3:8b, etc.) ont besoin de plus de temps pour générer des réponses complètes, surtout pour :
- Questions complexes
- Prompts longs (> 1000 caractères)
- Raisonnement en plusieurs étapes
- Code generation

---

## ⏱️ Temps de Réponse Estimés par Modèle

| Modèle | Paramètres | Temps de réponse | Timeout recommandé |
|--------|-----------|-----------------|-------------------|
| SmolLM2:1.7b | 1.7B | 1-5s | 60s |
| phi3:mini | 3.8B | 3-10s | 60s |
| tinyllama | 1.1B | 1-3s | 60s |
| Stable-code:3b | 3B | 3-8s | 60s |
| **qwen3:8b** | **8B** | **10-30s** | **180s (3 min)** |
| llama3:8b | 8B | 15-40s | 180s (3 min) |
| mistral:7b | 7B | 10-25s | 180s (3 min) |
| gemma:7b | 7B | 10-25s | 180s (3 min) |
| **qwen2:14b** | **14B** | **20-50s** | **300s (5 min)** |
| llama2:13b | 13B | 15-45s | 300s (5 min) |
| mistral-medium | ~12B | 15-40s | 300s (5 min) |
| **llama3:70b** | **70B** | **60-120s** | **600s (10 min)** |
| **mixtral:8x7b** | **47B** | **20-60s** | **600s (10 min)** |
| falcon:180b | 180B | 120-240s | 900s (15 min) |

---

## 🚀 Solution: Timeouts Dynamiques

PinkyBrainAgent v3.1+ supporte des **timeouts dynamiques** adaptés à la taille du modèle.

### Activation

Par défaut, les timeouts dynamiques sont activés.

### Configuration

```python
from src.pinkybrain_v5 import PinkyBrainAgent

# Créer PinkyBrainAgent
pinkybrain_bug = PinkyBrainAgent()

# Optionnel: Surcharge de timeout pour un modèle
pinkybrain_bug.set_timeout_override("qwen3:8b", 300)  # Force 5 minutes

# Optionnel: Timeout par défaut global
pinkybrain_bug.set_default_timeout(180)  # 3 minutes
```

### Table des Timeouts par Défaut

```python
MODEL_TIMEOUTS = {
    # Petits modèles (< 4B params)
    "SmolLM2:1.7b": 60,
    "tinyllama": 60,
    "phi3:mini": 60,

    # Modèles moyens (4-10B params)
    "qwen3:8b": 180,        # 3 minutes
    "llama3:8b": 180,
    "mistral:7b": 180,

    # Gros modèles (10-30B params)
    "qwen2:14b": 300,       # 5 minutes
    "llama2:13b": 300,

    # Très gros modèles (30B+ params)
    "llama3:70b": 600,      # 10 minutes
    "mixtral:8x7b": 600,
    "falcon:180b": 900,

    # Valeur par défaut
    "default": 120          # 2 minutes
}
```

---

## 🎯 Ajustement selon la Longueur du Prompt

Les timeouts s'ajustent automatiquement selon la taille du prompt :

```python
# Prompt court (< 500 caractères)
timeout = base_timeout  # Pas de changement

# Prompt moyen (500-1000 caractères)
timeout = base_timeout * 1.2  # +20%

# Prompt long (> 1000 caractères)
timeout = base_timeout * 1.5  # +50%
```

**Exemples:**

```
qwen3:8b + prompt court    → 180s (3 min)
qwen3:8b + prompt moyen   → 216s (3.6 min)
qwen3:8b + prompt long    → 270s (4.5 min)
```

---

## 📊 Cas d'Usage

### 1. Recherche Scientifique (Questions longues)

```python
pinkybrain_bug = PinkyBrainAgent()
pinkybrain_bug.model = "llama3:70b"

# Question complexe de 2000 caractères
question = "Expliquez en détail le mécanisme de photosynthèse..."

# Timeout automatique: 600s + 50% = 900s (15 min)
result = await pinkybrain_bug.query(question)
```

### 2. Code Generation (Prompts moyens)

```python
pinkybrain_bug = PinkyBrainAgent()
pinkybrain_bug.model = "mixtral:8x7b"

# Prompt de 800 caractères
prompt = "Écrivez une fonction Python pour..."

# Timeout automatique: 600s + 20% = 720s (12 min)
result = await pinkybrain_bug.query(prompt)
```

### 3. Chat Simple (Prompts courts)

```python
pinkybrain_bug = PinkyBrainAgent()
pinkybrain_bug.model = "phi3:mini"

# Question courte
question = "Quelle est la capitale de la France ?"

# Timeout: 60s (pas d'ajustement)
result = await pinkybrain_bug.query(question)
```

---

## ⚠️ Gestion des Timeouts

Si une requête timeout :

1. **Message d'erreur:**
   ```python
   "Error: Timeout after 180s"
   ```

2. **Options:**
   - Augmenter le timeout pour ce modèle
   - Simplifier la question
   - Utiliser un modèle plus petit

3. **Override:**
   ```python
   pinkybrain_bug.set_timeout_override("qwen3:8b", 600)  # Force 10 min
   ```

---

## 🔧 Configuration Avancée

### Désactiver les Timeouts Dynamiques

```python
pinkybrain_bug = PinkyBrainAgent()
pinkybrain_bug.enable_dynamic_timeouts = False  # Toujours utiliser default_timeout
pinkybrain_bug.set_default_timeout(120)  # 2 minutes pour tout
```

### Ajouter un Nouveau Modèle

```python
pinkybrain_bug = PinkyBrainAgent()
pinkybrain_bug.add_model_timeout("nouveau_modele:20b", 300)  # 5 minutes
```

### Surcharge Globale

```python
pinkybrain_bug = PinkyBrainAgent()
pinkybrain_bug.set_timeout_override("default", 300)  # Tout à 5 minutes
```

---

## 📊 Comparaison

### Avant (Timeouts Fixes)

```
SmolLM2:1.7b  → 60s ✅
phi3:mini     → 60s ✅
qwen3:8b      → 60s ❌ (10-30s requis)
llama3:70b    → 60s ❌❌❌ (60-120s requis)
```

### Après (Timeouts Dynamiques)

```
SmolLM2:1.7b  → 60s ✅
phi3:mini     → 60s ✅
qwen3:8b      → 180s ✅ (ajusté)
llama3:70b    → 600s ✅ (ajusté)
```

---

## 🎯 Recommandations

### Pour Production

1. **Utiliser les timeouts par défaut** (déjà optimisés)
2. **Surcharge seulement si nécessaire** (trop de timeouts)
3. **Monitoring** : Surveiller les temps de réponse réels
4. **Ajustements progressifs** : Augmenter progressivement

### Pour Développement

1. **Timeouts plus courts** pour développement rapide
2. **Tester avec différents modèles** pour ajuster
3. **Profiling** : Mesurer les temps de réponse typiques

### Pour Benchmarks

1. **Timeouts généreux** (2-3x le temps estimé)
2. **Pas de hard kill** : Laisser les modèles finir
3. **Logging détaillé** : Enregistrer les temps de réponses

---

## 📝 Note Importante

Les timeouts dynamiques sont une **amélioration proposée** par Denis Houet et seront disponibles dans **PinkyBrainAgent v3.1**.

Pour l'instant (v3.0), le timeout est fixe à 60s.

**Contributions bienvenues !** 💖

---

_Guide écrit suite à l'excellente observation de Denis Houet sur les timeouts trop courts pour les gros modèles_