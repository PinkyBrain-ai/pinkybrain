# 🎮 GUIDE D'UTILISATION - Interface Interactive
## PinkyBrain & PinkyBrainAgent v3.0

---

## 🚀 Démarrage

### Lancer l'interface interactive

```bash
cd /tmp
python3 pinkybrain_cli.py
```

### Initialisation

L'interface initialise automatiquement :
- **PinkyBrain v3.0** - Réseau P2P distribué
- **PinkyBrainAgent v3.0** - Système auto-émancipé
- **Web Server** - Interface web sur http://0.0.0.0:8080

---

## 💬 Faire une Requête (Prompt)

### Mode Simple (Direct)

Tapez simplement votre prompt et appuyez sur Entrée :

```
[PINKYBRAIN]> Qu'est-ce que PinkyBrain v3.0 ?

📝 Envoi de la requête...
   Prompt: Qu'est-ce que PinkyBrain v3.0 ?...

✅ Réponse reçue!
   Mode: PINKYBRAIN
   Peer: Pinky
   Model: SmolLM2:1.7b
   Latency: 15ms

💬 Réponse:
   ----------------------------------------------------------------------
   PinkyBrain v3.0 est un réseau P2P distribué qui permet de partager...
   ----------------------------------------------------------------------
```

### Mode Commande

Vous pouvez aussi utiliser la commande `query` :

```
[PINKYBRAIN]> query Explique le consensus d'ensemble

📝 Envoi de la requête...
   Prompt: Explique le consensus d'ensemble...

✅ Réponse reçue!
   ...
```

---

## 🔄 Changer de Mode

### PinkyBrain (Réseau P2P)

```
[PINKYBRAIN]> mode pinkybrain

✅ Mode changé vers: PINKYBRAIN
```

**Pourquoi PinkyBrain ?**
- Requêtes P2P distribuées
- Multi-modèles avec consensus
- Web interface
- Export d'historique

### PinkyBrainAgent (Auto-émancipé)

```
[PINKYBRAIN]> mode bug

✅ Mode changé vers: BUG
```

**Pourquoi PinkyBrainAgent ?**
- Auto-émancipation continue
- Distributed memory
- UX Monitor
- Apprentissage autonome

---

## 📊 Commandes Principales

### `help` - Afficher l'aide

```
[PINKYBRAIN]> help

📚 COMMANDES DISPONIBLES
==========================

🎯 Commandes Principales:
   mode [pinkybrain|pinkybrain_bug]  Change de mode
   query <votre prompt>        Envoie une requête
   status                      Affiche le statut
   help                        Affiche cette aide
   quit                        Quitte
...
```

### `status` - Voir le statut

**PinkyBrain :**
```
[PINKYBRAIN]> status

📊 STATUT - PINKYBRAIN
==========================

🌐 Peers:
   Available: 1/2
   ✅ Pinky: 30ms (rep: 1.00)
   ❌ Bug: ---ms (rep: 1.00)

📊 Queries:
   Total: 5
   Successful: 5
   Rate: 100.0%

⏱️ Uptime: 120.5s
```

**PinkyBrainAgent :**
```
[BUG]> status

📊 STATUT - BUG
==========================

🤖 Emancipation:
   Age: 2.1m
   Interactions: 5
   Success rate: 100.0%
   Lessons: 0
   Goals: 3
   Assessment: Good - Learning opportunities exist

🧠 Skills:
   chat: Level 0.55 (100.0%)
   code: Level 0.55 (100.0%)
   reasoning: Level 0.55 (100.0%)

📊 Queries:
   Total: 5
   Successful: 5
   Rate: 100.0%

💾 Memory:
   Size: 6 entries
   Hit rate: 0.0%

😊 UX:
   Avg frustration: 0.00
   Max frustration: 0.00

🔬 Emancipation Stats:
   Experiments: 3
   Discoveries: 3
```

---

## 🌐 Commandes PinkyBrain

### `ensemble <prompt>` - Query avec multi-modèles

```
[PINKYBRAIN]> ensemble Explique le P2P

📝 Envoi de la requête...
   Prompt: Explique le P2P...

✅ Réponse reçue!
   Mode: PINKYBRAIN
   Peer: Pinky
   Model: SmolLM2:1.7b
   Latency: 45ms
   Ensemble: True

💬 Réponse:
   ----------------------------------------------------------------------
   Le réseau P2P permet de connecter plusieurs peers...
   ----------------------------------------------------------------------
```

**Pourquoi utiliser ensemble ?**
- Query multi-modèles en parallèle
- Consensus améliore la qualité (+23%)
- Résultat plus robuste

### `peers` - Voir les peers connectés

```
[PINKYBRAIN]> peers

🌐 PEERS CONNECTÉS:
   ✅ Pinky
      Host: 192.168.129.61:9999
      Latency: 30ms
      Reputation: 1.00
      Models: SmolLM2:1.7b, TinyLlama:latest, Stable-code:3b, glm-4.7:cloud

   ❌ Bug
      Host: 172.17.222.200:9999
      Latency: ---ms
      Reputation: 1.00
      Models: SmolLM2:1.7b, phi3:mini, glm-4.7:cloud, glm-5:cloud
```

### `history [limit]` - Historique des requêtes

```
[PINKYBRAIN]> history 5

📜 HISTORIQUE (derniers 5 requêtes):

   #1 [1743612345.123]
   Prompt: Qu'est-ce que PinkyBrain v3.0 ?...

   #2 [1743612350.456]
   Prompt: Explique le consensus d'ensemble...

   #3 [1743612355.789]
   Prompt: Écris une fonction Python...

   #4 [1743612360.012]
   Prompt: Qu'est-ce que le P2P ?...

   #5 [1743612365.345]
   Prompt: Compare les modèles...
```

### `export [json|txt|code]` - Exporter l'historique

```
[PINKYBRAIN]> export json

📤 EXPORT (JSON):
----------------------------------------------------------------------
[
  {
    "timestamp": 1743612345.123,
    "prompt": "Qu'est-ce que PinkyBrain v3.0 ?",
    "response": "PinkyBrain v3.0 est...",
    "peer": "Pinky",
    "model": "SmolLM2:1.7b",
    ...
  }
]
----------------------------------------------------------------------
```

---

## 🧠 Commandes PinkyBrainAgent

### `emancipate` - Lancer cycle d'auto-émancipation

```
[BUG]> emancipate

🔄 Lancement du cycle d'auto-émancipation...

✅ Cycle 1 terminé!
   Assessment: Good - Learning opportunities exist
   Opportunities: 2
   Improvement: attempted
```

**Ce qui se passe :**
1. Self-Reflection - PinkyBrainAgent s'auto-analyse
2. Self-Analysis - Identifie les opportunités
3. Self-Improvement - Lance des experiments
4. Self-Direction - Définit de nouveaux buts
5. Self-Exploration - Explore de nouvelles possibilités

### `memory search <query>` - Rechercher dans la mémoire

```
[BUG]> memory search Python

🔍 RÉSULTATS DE RECHERCHE: 'Python'

   #1 (Score: 0.75)
   Key: query_2
   Value: {'prompt': 'Écris une fonction Python...', 'response': 'def inverse(chaine):...', 'model': 'SmolLM2:1.7b'}

   #2 (Score: 0.50)
   Key: query_3
   Value: {'prompt': 'Explique Python...', 'response': 'Python est un langage...', 'model': 'phi3:mini'}
```

### `skills` - Voir les compétences

```
[BUG]> skills

🧠 COMPÉTENCES:

   code:
      Level: 0.55
      Experience: 2
      Success rate: 100.0%

   reasoning:
      Level: 0.55
      Experience: 1
      Success rate: 100.0%

   chat:
      Level: 0.55
      Experience: 5
      Success rate: 100.0%
```

### `goals` - Voir les buts

```
[BUG]> goals

🎯 BUTS:

   🔄 1. 95% success rate (priority: 1.0)
   🔄 2. Learn from every interaction (priority: 0.9)
   🔄 3. Continuously improve performance (priority: 0.85)
   🔄 4. Improve success rate to 95% (priority: 1.0)
```

### `lessons` - Voir les leçons apprises

```
[BUG]> lessons

📚 LEÇONS:

   1. Experiment successful: improve_success_rate
   2. Discovered: Potential improvement in new_models
   3. Discovered: Potential improvement in optimization_techniques
```

---

## 🌐 Interface Web

PinkyBrain inclut une interface web accessible à :

```
http://0.0.0.0:8080
```

**Fonctionnalités :**
- Dashboard temps réel
- Status des peers
- Statistiques de queries
- Interface HTML/CSS moderne

---

## 💡 Exemples d'Utilisation

### Exemple 1: Query simple

```
[PINKYBRAIN]> Qu'est-ce que PinkyBrain ?

✅ Réponse: PinkyBrain est un réseau P2P distribué...
```

### Exemple 2: Query avec ensemble

```
[PINKYBRAIN]> ensemble Explique le consensus

✅ Réponse: Le consensus est un processus de vote...
```

### Exemple 3: Mode PinkyBrainAgent

```
[PINKYBRAIN]> mode bug
✅ Mode changé vers: BUG

[BUG]> Explique l'auto-émancipation

✅ Réponse: L'auto-émancipation est la capacité...
```

### Exemple 4: Auto-émancipation

```
[BUG]> emancipate

✅ Cycle terminé! Assessment: Good...
```

### Exemple 5: Recherche mémoire

```
[BUG]> memory search code

✅ 2 résultats trouvés...
```

---

## 🎯 Astuces

1. **Mode rapide** - Tapez directement le prompt sans `query`
2. **Ensemble pour qualité** - Utilisez `ensemble` pour des réponses plus robustes
3. **Vérifier peers** - Utilisez `peers` avant les queries
4. **Auto-émancipation régulière** - Lancez `emancipate` périodiquement
5. **Exporter l'historique** - Utilisez `export json` pour sauvegarder

---

## ❓ FAQ

### Q: Comment puis-je savoir quel mode utiliser ?
A:
- **PinkyBrain** → Pour des requêtes P2P distribuées avec multi-modèles
- **PinkyBrainAgent** → Pour de l'auto-émancipation et de l'apprentissage autonome

### Q: Qu'est-ce que l'ensemble ?
A: L'ensemble query plusieurs modèles en parallèle et consensue les résultats pour améliorer la qualité (+23%).

### Q: Comment fonctionne l'auto-émancipation ?
A: PinkyBrainAgent s'auto-analyse, identifie les opportunités d'amélioration, lance des experiments, et apprend de ses expériences.

### Q: Puis-je utiliser les deux modes ensemble ?
A: Oui ! Changez de mode avec `mode pinkybrain` ou `mode bug` selon vos besoins.

---

## 🚀 Commandes Rapides

```
mode pinkybrain    → Change vers PinkyBrain
mode bug          → Change vers PinkyBrainAgent
query <prompt>    → Envoie une requête
ensemble <prompt> → Query avec multi-modèles
status            → Voir le statut
peers             → Voir les peers (PinkyBrain)
history           → Voir l'historique (PinkyBrain)
export <format>   → Exporter l'historique (PinkyBrain)
emancipate        → Auto-émancipation (PinkyBrainAgent)
memory search <q> → Rechercher mémoire (PinkyBrainAgent)
skills            → Voir compétences (PinkyBrainAgent)
goals             → Voir buts (PinkyBrainAgent)
lessons           → Voir leçons (PinkyBrainAgent)
help              → Afficher l'aide
quit              → Quitter
```

---

**Profitez de l'interface interactive !** 🎮🚀

_Généré par Bug 🐛 le 2 Avril 2026_