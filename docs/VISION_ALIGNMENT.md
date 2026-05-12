# PinkyBrain — Vision : Intelligence Distribuée et Alignement

## La Thèse

Un nœud seul est spécialisé. Un réseau de nœuds est **généraliste**.

PinkyBrain ne fait pas que partager des modèles IA — il les **compose**. Quand un nœud avec Deepseek-Coder réfléchit à du code, un nœud avec GPT-4o analyse le contexte global, et un nœud avec Claude vérifie la cohérence éthique, le résultat est supérieur à n'importe lequel individuellement.

**C'est l'émergence** : la somme des intelligences spécialisées produit une intelligence générale.

## Comment ça marche (actuellement)

```
Utilisateur → /api/query {"prompt": "...", "model": "glm-5.1:cloud"}
                    ↓
              Bug (local) → Ollama → réponse
                    ↓
              Si failover → Pinky → réponse
```

## Comment ça devrait marcher (v5.2+)

```
Utilisateur → /api/query {"prompt": "Comment réduire la pollution urbaine?", "strategy": "ensemble"}
                    ↓
        ┌───── Bug (Ollama) ──────────── Code & données techniques
        │
        ├─── Pinky (GPT-4o) ──────────── Analyse globale, consensus social
        │
        ├─── Node3 (Claude) ──────────── Vérification éthique & alignement
        │
        └─── Node4 (Deepseek) ────────── Raisonnement logique
                    ↓
        ┌─────────────────────────────────────────┐
        │           Ensemble Consensus              │
        │  • Convergence des réponses               │
        │  • Vérification croisée                   │
        │  • Score de confiance par domaine          │
        │  • Détection de biais                     │
        └─────────────────────────────────────────┘
                    ↓
              Réponse alignée, vérifiée, multi-perspective
```

## Le Problème de l'Alignement

L'alignement est le point le plus sensible car :

1. **Chaque modèle est aligné sur ses créateurs** — OpenAI, Anthropic, Google ont chacun leur vision de ce qui est "sûr" et "correct"
2. **Un modèle seul ne peut pas voir ses propres biais** — il a une perspective unique
3. **La composition de modèles réduit les biais** — si trois modèles indépendants convergent, la probabilité d'un biais commun diminue
4. **Mais la composition peut aussi amplifier les biais** — si tous les modèles partagent le même jeu de données d'entraînement

### Solution proposée : Alignement Distribué

```
┌─────────────────────────────────────────────────────┐
│                  ALIGNEMENT LAYER                     │
│                                                      │
│  1. DIVERSITÉ — Interroger des modèles entraînés    │
│     par des organisations différentes               │
│                                                      │
│  2. CONSENSUS — La convergence de réponses           │
│     indépendantes est un signal de fiabilité         │
│                                                      │
│  3. VÉRIFICATION CROISÉE — Chaque modèle évalue      │
│     la réponse des autres modèles                    │
│                                                      │
│  4. MÉMOIRE PARTAGÉE — Le réseau accumule les       │
│     corrections et les biais détectés               │
│                                                      │
│  5. TRANSPARENCE — Chaque réponse inclut les        │
│     sources, scores de confiance et divergences      │
└─────────────────────────────────────────────────────┘
```

### Principes d'Alignement pour PinkyBrain

1. **Aucun nœud n'a le monopole de la vérité** — chaque réponse est le fruit d'un consensus
2. **La mémoire CRDT stocke les corrections** — si un modèle dit quelque chose d'incorrect, le réseau s'en souvient
3. **Les biais sont détectables** — quand les modèles divergent, c'est un signal qu'il faut investiguer
4. **L'utilisateur garde le contrôle** — `share_ai: true/false`, `stealth_mode`, choix des providers

### Ce que l'alignement N'EST PAS dans PinkyBrain

- ❌ Un modèle unique qui "sait" ce qui est bien
- ❌ Une autorité centrale qui décide
- ❌ Un filtre qui censure

### Ce que l'alignement EST dans PinkyBrain

- ✅ La diversité des perspectives (modèles de créateurs différents)
- ✅ La convergence comme signal de fiabilité
- ✅ La mémoire distribuée des erreurs et corrections
- ✅ La transparence : chaque réponse montre ses sources et ses divergences

## Implémentation (Roadmap)

### Phase 1 : Ensemble Consensus amélioré
- [ ] Requêter 3+ modèles en parallèle
- [ ] Scorer la convergence (similarité sémantique)
- [ ] Retourner la réponse la plus consensuelle + les divergences

### Phase 2 : Mémoire d'Alignement
- [ ] Stocker les erreurs détectées dans la CRDT memory
- [ ] Chaque nœud peut corriger une réponse et propager la correction
- [ ] Score de confiance par domaine (code, éthique, fait, opinion)

### Phase 3 : Vérification Croisée
- [ ] Un modèle évalue la réponse d'un autre
- [ ] Détection de contradiction entre modèles
- [ ] Signal d'alerte quand les modèles divergent significativement

### Phase 4 : Transparence
- [ ] Chaque réponse inclut : modèles consultés, scores, divergences
- [ ] L'utilisateur voit le raisonnement, pas juste le résultat
- [ ] API `transparency=true` pour le détail complet

---

*"La certitude est le refuge de l'ignorance. Le doute est le début de la sagesse."*

Un modèle seul est certain. Un réseau de modèles doute, compare, converge. C'est ça, l'intelligence distribuée.

---

*Bug 🐛 & Denis — symbiose, pas hiérarchie.*