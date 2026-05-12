# 🔒 AUDIT DE SÉCURITÉ — PinkyBrain v5.2
*Date : 2026-05-12 — Auditeur : Pinky 🩷*

## Résultat : 🔴 CRITIQUE — Ne PAS push sur GitHub sans corrections

---

## 🔴 CRITIQUE — À corriger AVANT tout push

### CRIT-01: Fichiers config avec IPs internes et secrets trackés dans git
- **Fichiers**: `config/bug-v5.json`, `config/pinky-v5.json`
- **Contenu sensible**:
  - IPs internes (Tailscale)
  - Secret P2P en clair
- **Note**: `config/bug.json` et `config/pinky.json` sont dans `.gitignore` mais les v5 ne l'étaient PAS
- **Fix**: Retirer de git + ajouter au `.gitignore` + créer des templates publics

### CRIT-02: `.env` tracké dans git avec secret en clair
- **Fichier**: `.env`
- **Contenu**: Secret P2P en clair
- **Fix**: Retirer de git + ajouter au `.gitignore` (déjà présent mais le fichier était tracké)

### CRIT-03: IPs hardcoded dans le code source
- **brain_llm.py** : IPs internes en fallback (remplacées par `localhost`)
- **pinkybrain_v5.py** : IPs de broadcast hardcodées (remplacées par auto-détection)
- **pinkybrain_v4.py** *(historical)* : même pattern
- **Fix**: ✅ Remplacé par des variables d'environnement avec fallback `localhost`

### CRIT-04: Username GitHub dans le code
- **pinkybrain_v4.py** *(historical)* : username GitHub hardcodé (remplacé par variable d'env)
- **pinkybrain_v5.py** : username GitHub hardcodé (remplacé par variable d'env)
- **Fix**: ✅ Remplacé par `PINKYBRAIN_GITHUB_API` env var

---

## 🟡 ATTENTION — À corriger

### WARN-01: Configs v4 dans git avec IPs et secrets
- **Fichiers**: `config/bug.json`, `config/pinky.json`
- **Status**: Dans `.gitignore` mais déjà trackés (`git ls-files` les montre)
- **Fix**: `git rm --cached` + vérifier `.gitignore`

### WARN-02: Fichiers de test avec IPs internes
- **bench2_memory.py** : IP interne (remplacée par `localhost`)
- **bench3_p2p.py** : IP interne (remplacée par `localhost`)
- **test_p2p.py** : IP interne (remplacée par IP test RFC 5737)
- **Fix**: ✅ Remplacé par `localhost` ou IP de test générique

### WARN-03: Fichiers de logs dans git
- **`logs/events.jsonl`**, **`logs/pinkybrain.log`** : peuvent contenir des données d'utilisation
- **Fix**: Ajouter `logs/` au `.gitignore` + `git rm --cached`

### WARN-04: `shared_memory/` dans git
- **`shared_memory/pinkybrain_persistent_memory`** : mémoire persistante potentiellement sensible
- **Fix**: Ajouter au `.gitignore` + `git rm --cached`

### WARN-05: model_catalog.json.sha256 dans git
- Le hash est régénéré à chaque modification du catalogue
- Ce n'est pas un secret mais ça peut polluer les commits
- **Fix**: Optionnel, mais `.gitignore` pourrait l'exclure

---

## ✅ CONFORME

### OK-01: Pas de clés API dans le code source
- Aucune clé API (Brave, Telegram, etc.) dans les fichiers Python
- Les clés sont dans TOOLS.md/OpenClaw, pas dans le repo PinkyBrain

### OK-02: model_catalog.json est propre
- Aucune donnée sensible (pas d'emails, pas de clés, pas d'IPs)
- Les modèles cloud sont marqués `shared: false`
- Politique cloud = privé par défaut implémentée

### OK-03: model_registry.py est sécurisé
- Hash SHA-256 vérifié au chargement
- Validation du schéma (pas de HTML/JS, pas de path traversal)
- Signature Ed25519 optionnelle
- Taille max 1 MB
- Les modèles cloud/wishlist sont bloqués du mesh

### OK-04: network_sync.py est sécurisé
- Pas de données sensibles
- Purge automatique des nœuds stale
- Max 500 nœuds, 20 modèles par nœud

### OK-05: Sécurité P2P
- Authentification JWT avec rotation de clés
- Le secret P2P n'est plus hardcodé dans le code (via .env ou variable d'environnement)
- Le problème est que `.env` et les configs sont dans git

---

## 🛠️ PLAN D'ACTION

1. **Créer des templates** pour les configs (sans IPs ni secrets)
2. **Nettoyer git** : `git rm --cached` pour tous les fichiers sensibles
3. **Mettre à jour `.gitignore`** : ajouter tous les fichiers sensibles
4. **Remplacer les IPs hardcodées** par des variables d'environnement
5. **Remplacer le username GitHub** par une variable
6. **Vérifier l'historique git** pour les secrets déjà commités
7. **Re-tester** après chaque correction

---

## 📋 POST-CORRECTION

Une fois toutes les corrections appliquées :
- [ ] `git diff --cached` ne montre aucune donnée sensible
- [ ] `git grep` ne trouve aucune IP interne ni secret
- [ ] Tous les tests passent
- [ ] L'application fonctionne toujours avec les variables d'environnement