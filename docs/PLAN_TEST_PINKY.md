# 🧪 PLAN DE TEST UTILISATEUR - Pinky
## Pinky joue le rôle d'un utilisateur lambda n'ayant pas le code source

---

## 🎯 Objectif

Simuler un **utilisateur réel** qui:
- N'a PAS le code source
- N'a PAS l'environnement de développement
- Doit installer et utiliser PinkyBrainBug "from scratch"
- Donne un feedback utilisateur authentique

---

## 📋 Scénarios de Test

### SCÉNARIO 1: Installation Fraîche

**But:** Installer PinkyBrainBug sur une machine vierge

**Étapes:**
1. Cloner le repo depuis GitHub: `git clone https://github.com/PinkyBrain-ai/pinkybrain.git`
2. Entrer dans le répertoire: `cd PinkyBrain`
3. Installer les dépendances: `pip install -r requirements.txt --break-system-packages`
4. Installer les dépendances d'autonomie: `pip install -r requirements_autonomy.txt --break-system-packages`
5. Installer Ollama: `curl -fsSL https://ollama.ai/install.sh | sh`

**Questions à Pinky:**
- ❓ L'installation était-elle facile ?
- ❓ Y a-t-il eu des erreurs ?
- ❓ La documentation est-elle claire ?

---

### SCÉNARIO 2: Setup Interactif

**But:** Configurer PinkyBrainBug via le setup guidé

**Étapes:**
1. Lancer le setup: `python3 scripts/setup_interactive.py`
2. Répondre aux questions:
   - Nom de l'agent: "Pinky"
   - Emoji: "🐛"
   - Langue: "fr"
   - Configuration Ollama: 127.0.0.1:11434
   - Modèle principal: "phi3:mini"
   - Timeout par défaut: 60
   - Activer auto-support: "y"
3. Vérifier le fichier `config.json`

**Questions à Pinky:**
- ❓ Le setup était-il intuitif ?
- ❓ Les questions sont-elles claires ?
- ❓ La config a-t-elle été créée correctement ?

---

### SCÉNARIO 3: Auto-Support

**But:** Tester que PinkyBrainBug répond aux questions

**Étapes:**
1. Lancer l'auto-support: `python3 -m src.auto_support`
2. Poser des questions:
   - "Comment configurer Ollama ?"
   - "Qu'est-ce que le P2P ?"
   - "Comment faire un benchmark ?"
3. Observer les réponses
4. Vérifier les logs: `tail logs/auto_support.log`

**Questions à Pinky:**
- ❓ Les réponses sont-elles utiles ?
- ❓ La confiance est-elle correcte ?
- ❓ Y a-t-il eu des escalades vers l'humain ?

---

### SCÉNARIO 4: Auto-Monitoring

**But:** Tester la surveillance système

**Étapes:**
1. Lancer le monitoring: `python3 -m src.auto_monitoring check`
2. Observer les métriques
3. Attendre 1-2 minutes
4. Relancer: `python3 -m src.auto_monitoring check`
5. Vérifier les logs: `tail logs/metrics.json`

**Questions à Pinky:**
- ❓ Les métriques sont-elles claires ?
- ❓ Les alertes fonctionnent-elles ?
- ❓ L'interface est-elle lisible ?

---

### SCÉNARIO 5: Auto-Healing

**But:** Tester la réparation automatique

**Étapes:**
1. Lancer: `python3 -m src.auto_healing auto`
2. Observer les problèmes détectés
3. Voir si des réparations sont faites
4. Vérifier les logs: `tail logs/healing.log`

**Questions à Pinky:**
- ❓ Les problèmes sont-ils détectés ?
- ❓ Les réparations fonctionnent-elles ?
- ❓ Les logs sont-ils utiles ?

---

### SCÉNARIO 6: Auto-Optimization

**But:** Tester l'optimisation

**Étapes:**
1. Lancer: `python3 -m src.auto_optimization`
2. Observer l'analyse
3. Voir si des optimisations sont appliquées
4. Vérifier les logs: `tail logs/optimizations.log`

**Questions à Pinky:**
- ❓ L'analyse est-elle pertinente ?
- ❓ Les optimisations sont-elles effectives ?
- ❓ Les améliorations sont-elles visibles ?

---

### SCÉNARIO 7: Auto-Upgrade

**But:** Tester les mises à jour

**Étapes:**
1. Vérifier les mises à jour: `python3 -m src.auto_upgrade check`
2. Observer les versions
3. (NE PAS faire l'upgrade auto - juste vérifier)
4. Voir les sauvegardes: `ls -lh backups/`

**Questions à Pinky:**
- ❓ La vérification fonctionne-t-elle ?
- ❓ Les versions sont-elles claires ?
- ❓ Le système de sauvegarde est-il rassurant ?

---

### SCÉNARIO 8: Mode Autonome Complet

**But:** Tester l'orchestration complète

**Étapes:**
1. Lancer en mode autonome: `python3 -m src.pinkybrain_bug_autonomy`
2. Choisir "start"
3. Observer pendant 5 minutes:
   - Monitoring actif
   - Optimisation active
   - Cycles d'autonomie
4. Choisir "status"
5. Observer le status complet
6. Choisir "stop"

**Questions à Pinky:**
- ❓ Le mode autonome est-il stable ?
- ❓ Les cycles fonctionnent-ils ?
- ❓ Le status est-il complet ?

---

### SCÉNARIO 9: Benchmarks

**But:** Tester les performances sur Pinky

**Étapes:**
1. Lancer un benchmark rapide: `python3 tests/benchmark_quick.py`
2. Observer les résultats
3. Comparer avec les résultats de Bug
4. Vérifier les logs: `tail output/*.json`

**Questions à Pinky:**
- ❓ Le benchmark tourne-t-il ?
- ❓ Les résultats sont-ils cohérents ?
- ❓ Y a-t-il des différences avec Bug ?

---

### SCÉNARIO 10: Clé USB Bootable (Optionnel)

**But:** Tester la clé USB

**Étapes:**
1. Lire le guide: `cat docs/GUIDE_USB_BOOTABLE.md`
2. Créer une clé USB (si possible): `sudo ./scripts/create_pinkybrain_bug_usb.sh /dev/sdX`
3. Boot sur la clé USB
4. Observer le menu GRUB
5. Lancer PinkyBrainBug automatiquement

**Questions à Pinky:**
- ❓ Le guide est-il clair ?
- ❓ La clé USB boot-t-elle ?
- ❓ Le système démarre-t-il automatiquement ?

---

## 📊 FEEDBACK DEMANDÉ À PINKY

Pour chaque scénario, Pinky doit noter:

### 1. **Expérience Utilisateur** (1-5 étoiles)
- ⭐⭐⭐⭐⭐ Excellent
- ⭐⭐⭐⭐ Bien
- ⭐⭐⭐ Moyen
- ⭐⭐ Faible
- ⭐ Mauvais

### 2. **Problèmes Rencontrés**
- Erreurs d'installation ?
- Documentation incomplète ?
- Bugs fonctionnels ?
- Interface confuse ?

### 3. **Améliorations Suggérées**
- Quoi améliorer ?
- Quoi simplifier ?
- Quoi ajouter ?

### 4. **Impression Générale**
- PinkyBrainBug est-il facile à utiliser ?
- Est-il prêt pour la publication ?
- L'utiliserais-tu au quotidien ?

---

## 🎯 CRITÈRES DE VALIDATION

PinkyBrainBug v3.5 est **PRÊT POUR PUBLICATION** si:

- ✅ Pinky peut installer sans aide
- ✅ Le setup interactif fonctionne
- ✅ Auto-Support répond correctement
- ✅ Tous les modules d'autonomie fonctionnent
- ✅ Aucun bug bloquant
- ✅ Expérience utilisateur ≥ 4/5 étoiles
- ✅ Pinky recommanderait PinkyBrainBug

---

## 📝 RAPPORT FINAL DE PINKY

À la fin des tests, Pinky doit fournir:

```markdown
# 📊 RAPPORT DE TEST UTILISATEUR - Pinky

## 📋 Scénarios Testés

1. ✅/❌ Installation Fraîche
2. ✅/❌ Setup Interactif
3. ✅/❌ Auto-Support
4. ✅/❌ Auto-Monitoring
5. ✅/❌ Auto-Healing
6. ✅/❌ Auto-Optimization
7. ✅/❌ Auto-Upgrade
8. ✅/❌ Mode Autonome
9. ✅/❌ Benchmarks
10. ✅/❌ Clé USB Bootable

## 🎯 Expérience Globale
- Note: X/5 ⭐
- Prêt pour publication: OUI/NON
- Recommanderais-tu PinkyBrainBug: OUI/NON

## 💡 Améliorations Suggérées
...

## 🐛 Bugs Trouvés
...

## 🎉 Points Forts
...

## 📝 Conclusion
...
```

---

## ⏱️ TEMPS ESTIMÉ

- Scénario 1-2 (Installation + Setup): 15 min
- Scénario 3-7 (Modules autonomie): 20 min
- Scénario 8 (Mode autonome): 5 min
- Scénario 9 (Benchmarks): 10 min
- Scénario 10 (Clé USB): Optionnel

**Total:** ~50 minutes (sans clé USB)

---

## 🎯 OBJECTIF FINAL

Consolider PinkyBrainBug v3.5 avec un **feedback utilisateur authentique** et **s'assurer qu'il est vraiment prêt pour la publication** !

---

_Ce plan est prêt quand Pinky revient dans 20-30 minutes !_

_Généré par PinkyBrainBug 🐛 avec l'idée géniale de Denis !_