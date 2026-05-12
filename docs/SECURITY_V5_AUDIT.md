# 🔍 Audit Complet v5.1.0 vs v4.2.1-security — État des Fixes

**Date:** 2026-05-12  
**Fichiers comparés:**
- `src/pinkybrain_v5.py` (4243 lignes) — version auditée + corrigée
- `src/pinkybrain_v5.py` (4800+ lignes) — **version en production**, non corrigée

## Résultat Global

| Catégorie | Fixes dans v4 | Présents dans v5 ? | Action requise |
|---|---|---|---|
| CRITICAL (3) | 3/3 ✅ | 2/3 ⚠️ | 1 à corriger |
| HIGH (6) | 6/6 ✅ | 5/6 ⚠️ | 1 à corriger |
| MEDIUM (7) | 7/7 ✅ | 2/7 ⚠️ | 5 à corriger |
| LOW (8) | 8/8 ✅ | 1/8 ⚠️ | 7 à corriger |
| NEW (6) | 6/6 ✅ | 0/6 ❌ | 6 à corriger |
| **TOTAL (30)** | **30/30 ✅** | **10/30 (33%)** | **20 à porter** |

## Détail Fix par Fix

### ✅ DÉJÀ PRÉSENTS dans v5 (10/30)

| ID | Description | Preuve dans v5 |
|---|---|---|
| CRIT-01 | P2P_SECRET env var + warning | `P2P_SECRET` env var, `WEAK_SECRETS` check, lignes 1784-1800 |
| CRIT-02 | Path in auth challenge | `challenge = f"{node_name}:{request.path}:{ts}"` lignes 2319-2320 |
| CRIT-03 | auto_heal logging only | Plus de subprocess kill, logging only, lignes 4308-4350 |
| HIGH-01 | Input validation | `MAX_PROMPT_LENGTH`, `ALLOWED_MODEL_PATTERN`, `ALLOWED_STRATEGIES`, lignes 132-134 |
| HIGH-02 | WS auth timeout | `AUTH_TIMEOUT_SECONDS = 10`, `ws_authenticated`, lignes 137, 2063 |
| HIGH-04 | Rate limiting | `RateLimiter` global + per-endpoint, lignes 863, 1848-1853 |
| HIGH-05 | HMAC fallback secure | `_fallback_secret` from P2P secret only, lignes 731-733, 761-764 |
| HIGH-06 | CORS middleware | `cors_middleware`, `CORS_ALLOWED_ORIGINS`, lignes 139, 2448-2468 |
| MED-06 | pip install verbose | setup.py: no `-q`, pinned versions, lignes 101-130 |
| LOW-06 | Auto-updater SHA256 | AutoUpdater class exists (line 587), sha256 used for identity |

### ❌ ABSENTS de v5 (20/30) — À PORTER

| ID | Description | Impact si non corrigé | Priorité |
|---|---|---|---|
| **MED-01** | mDNS beacons signés | Spoofing mDNS possible | MEDIUM |
| **MED-02** | Tailscale hostname whitelist | Injection hostname possible | MEDIUM |
| **MED-03** | Log sanitization (no sig/key frags) | Fuite de secrets dans les logs | MEDIUM |
| **MED-04** | CRDT validation (key/value/TTL limits) | DoS mémoire via entrées géantes | MEDIUM |
| **MED-05** | Nonce anti-replay dans `_verify_auth` | Replay attacks sur l'auth | HIGH |
| **MED-07** | TokenBlacklist | Pas de révocation de tokens | MEDIUM |
| **LOW-01** | Log file permissions 0o600/0o700 | Logs lisibles par tout le monde | LOW |
| **LOW-02** | PID file permissions 0o600 | PID lisible par tout le monde | LOW |
| **LOW-03** | TLS support (PINKYBRAIN_CERT/KEY) | Pas de HTTPS | LOW |
| **LOW-04** | CSP header on dashboard | XSS risque | LOW |
| **LOW-05** | XSS html_escape on dashboard | XSS via peer names | MEDIUM |
| **LOW-07** | WS max_msg_size limit | DoS par messages géants | LOW |
| **LOW-08** | CLI history permissions + truncation | Fuite via history | LOW |
| **NEW-01** | Nonce deque → set + threading.Lock | Race condition sur auth | HIGH |
| **NEW-02** | TokenBlacklist endpoint + cleanup | Blacklist jamais activée | MEDIUM |
| **NEW-03** | WS auth HMAC timestamp check | Replay WS auth éternel | HIGH |
| **NEW-04** | CRDT MAX_SYNC_ENTRIES=1000 | DoS par entrées massives | MEDIUM |
| **NEW-05** | CSP nonce instead of unsafe-inline | XSS persistant | LOW |
| **NEW-06** | NodeIdentity 'changeme' warning | Secret fallback silencieux | LOW |
| **Bug-02** | token_id sha256 au lieu de sig[:16] | Collision token | LOW |

### ⚠️ CRIT-01bis — Cas particulier

v5 ligne 732: `seed = secret_seed or os.environ.get("P2P_SECRET", "changeme")`
v4 ligne corrigée: warning logger.error() si "changeme"

**Statut:** Le fallback "changeme" existe toujours dans v5 SANS le warning ajouté dans v4. Le `load_config()` a un warning pour les secrets faibles (lignes 1791-1799) mais `NodeIdentity.__init__` n'a pas le warning explicite NEW-06.

## Recommandation

**Il faut porter les 20 fixes manquants de v4 vers v5.** C'est le fichier qui tourne en production. Les fixes sont majoritairement chirurgicaux (constantes, conditions, wrappers) et ne cassent pas les nouvelles fonctionnalités v5.

L'approche recommandée : appliquer les fixes un par un dans l'ordre de priorité (HIGH → MEDIUM → LOW), tester la compilation après chaque fix.