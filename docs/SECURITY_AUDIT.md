# ⚠️ Ce document est un audit historique de la v4. Les corrections ont été portées à pinkybrain_v5.py.
# 🔒 PinkyBrain v4 — Audit de Sécurité

**Date:** 2026-05-05  
**Auditeur:** Bug 🐛 (PinkyBrain Security)  
**Version auditée:** v4.2.0 (code), v4.1.5 (config)  
**Fichiers analysés:**
- `src/pinkybrain_v4.py` — Serveur principal
- `src/pinkybrain_cli.py` — Client CLI
- `src/auth/auth/token_auth.py` — Authentification JWT/HMAC
- `src/auth/auth/circuit_breaker.py` — Circuit breaker
- `config/bug.json`, `config/pinky.json` — Configuration
- `setup.py` — Installation
- `start.sh` — Script de démarrage

---

## Table des Matières

1. [Failles Critiques](#1-failles-critiques)
2. [Failles Élevées](#2-failles-élevées)
3. [Failles Moyennes](#3-failles-moyennes)
4. [Failles Basses](#4-failles-basses)
5. [Résumé & Priorités](#5-résumé--priorités)

---

## 1. Failles Critiques

### 🔴 CRIT-01: Secret P2P codé en dur dans les fichiers de configuration

**Type:** Information leak / Auth bypass  
**Sévérité:** CRITIQUE  
**Fichier:** `config/bug.json`, `config/pinky.json`

Les fichiers de configuration contiennent le secret P2P en clair:
```json
"p2p_secret": "your-secret-here-change-me"
```

Ce secret est commité dans le dépôt Git. Toute personne avec accès au repo peut:
- Forger des tokens JWT/HMAC valides
- S'authentifier comme n'importe quel nœud
- Contourner entièrement le système d'authentification

**Preuve:**
```bash
# N'importe qui avec le secret peut forger un header HMAC valide
ts=$(date +%s)
sig=$(echo -n "/api/query:${ts}" | openssl dgst -sha256 -hmac "your-secret-here-change-me" | awk '{print $NF}')
curl -H "X-PinkyBrain-Auth: ${sig}" -H "X-PinkyBrain-TS: ${ts}" http://target:8080/api/query
```

**Fix:**
1. Retirer immédiatement le secret des fichiers de config versionnés
2. Utiliser une variable d'environnement ou un fichier `.env` exclu du repo (`.gitignore`)
3. Ajouter un avertissement au démarrage si le secret est trop faible ou absent
4. Générer un secret aléatoire fort par défaut dans `setup.py` (déjà partiellement fait, mais les configs existantes sont exposées)

```python
# Fix dans load_config():
self.p2p_secret = os.environ.get("P2P_SECRET") or config.get("p2p_secret")
if not self.p2p_secret or self.p2p_secret == "changeme-configure-in-config":
    logger.error("⚠️  P2P_SECRET not configured! Generate one with: python3 -c 'import secrets; print(secrets.token_hex(32))'")
    sys.exit(1)
```

---

### 🔴 CRIT-02: Bypass d'authentification par replay Ed25519/HMAC

**Type:** Auth bypass  
**Sévérité:** CRITIQUE  
**Fichier:** `src/pinkybrain_v4.py` — `_verify_auth()`, `_auth_headers()`

La vérification Ed25519/HMAC dans `_verify_auth()` accepte une signature sans lier le chemin de la requête au challenge signé.

Dans `_auth_headers()`:
```python
def _auth_headers(self):
    ts = str(int(time.time()))
    token = self.identity.sign(f"{self.node_name}:{ts}")
    # ...
    hmac_sig = hmac_mod.new(
        self.p2p_secret.encode(), f"{path}:{ts}".encode(), hashlib.sha256).hexdigest()
```

Le Bearer token est la signature de `{node_name}:{ts}` — il ne contient **pas** le chemin de la requête. Un attaquant peut capturer un Bearer token valide et l'utiliser sur n'importe quel endpoint (`/api/query`, `/api/memory/set`, etc.).

Pour le HMAC fallback, le chemin est vérifié côté serveur avec `request.path`, mais le Bearer token Ed25519 ne vérifie PAS le chemin.

**Preuve:**
```python
# Un token signé pour node_name="bug" à timestamp T peut être réutilisé
# sur TOUT endpoint dans la fenêtre de 60 secondes.
# Capture: Authorization: Bearer <sig_of_"bug:1234567890">
# Replay sur: POST /api/memory/set (au lieu de /api/query)
# → Accepté car le token ne contient pas le path
```

**Fix:**
```python
# Dans _auth_headers(), signer le path + timestamp:
challenge = f"{self.node_name}:{path}:{ts}"
token = self.identity.sign(challenge)

# Dans _verify_auth(), vérifier avec le path de la requête:
challenge = f"{node_name}:{request.path}:{ts}"
verified = self.identity.verify(challenge, sig, node_key)
```

---

### 🔴 CRIT-03: Exécution de commandes arbitraires via `auto_heal()`

**Type:** Command injection / RCE  
**Sévérité:** CRITIQUE  
**Fichier:** `src/pinkybrain_v4.py` — `auto_heal()`

```python
async def auto_heal(self):
    # ...
    proc = await asyncio.create_subprocess_exec(
        'fuser', '-k', f'{self.ollama_port}/tcp',
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    # ...
    proc = await asyncio.create_subprocess_exec(
        'systemctl', 'restart', 'ollama',
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
```

Bien que `subprocess_exec` soit utilisé (plus sûr que `shell=True`), le fait de **tuer des processus et redémarrer des services** en réponse à un check de santé est dangereux:
- Si un attaquant peut provoquer un échec Ollama (facile: flood de requêtes), il force un restart du service
- `fuser -k` tue TOUS les processus sur le port — potentiellement d'autres services
- `systemctl restart ollama` nécessite des privilèges élevés

**Fix:**
1. Retirer le `fuser -k` — ne jamais tuer des processus aveuglement
2. Logger au lieu de restart automatiquement
3. Si auto-heal est nécessaire, utiliser une approche sandboxée avec vérification
4. Ajouter une confirmation humaine ou au moins un rate-limit sur les restarts

---

## 2. Failles Élevées

### 🟠 HIGH-01: Absence de validation d'entrée sur `/api/query` — Injection potentielle

**Type:** Input validation / Injection  
**Sévérité:** ÉLEVÉE  
**Fichier:** `src/pinkybrain_v4.py` — `handle_query()`

```python
async def handle_query(self, request: web.Request) -> web.Response:
    data = await request.json()
    prompt = data.get("prompt", "")
    model = data.get("model")
    strategy = data.get("strategy", "auto")
    # → prompt et model sont passés directement à Ollama sans aucune validation
```

Le `prompt` est envoyé tel quel à Ollama/OpenAI/Anthropic. Pas de:
- Limite de taille (un prompt de 100MB ferait exploser la mémoire)
- Sanitisation des caractères de contrôle
- Validation du nom de modèle (un modèle malicieux pourrait pointer vers une URL interne)

Le `model` est utilisé directement dans les requêtes HTTP aux providers sans validation. Un attaquant pourrait injecter des valeurs comme `"../../etc/passwd"` ou utiliser des modèles non autorisés.

**Preuve:**
```bash
# DoS mémoire: envoyer un prompt géant
curl -X POST http://target:8080/api/query \
  -H "Authorization: Bearer <valid_token>" \
  -d '{"prompt": "'$(python3 -c "print('A'*100000000)")'"}'

# Model injection: pointer vers un endpoint interne
# Si un provider OpenAI-compatible est configuré, le model pourrait être utilisé pour SSRF
```

**Fix:**
```python
MAX_PROMPT_LENGTH = 50000  # 50KB max
ALLOWED_MODEL_PATTERN = re.compile(r'^[a-zA-Z0-9._:/-]+$')

async def handle_query(self, request):
    data = await request.json()
    prompt = data.get("prompt", "")
    if not prompt or len(prompt) > MAX_PROMPT_LENGTH:
        return web.json_response({"error": "Invalid prompt"}, status=400)
    model = data.get("model")
    if model and not ALLOWED_MODEL_PATTERN.match(model):
        return web.json_response({"error": "Invalid model name"}, status=400)
    # ...
```

---

### 🟠 HIGH-02: WebSocket sans authentification initiale — accès aux données

**Type:** Auth bypass  
**Sévérité:** ÉLEVÉE  
**Fichier:** `src/pinkybrain_v4.py` — `handle_websocket()`

```python
async def handle_websocket(self, request):
    ws = web.WebSocketResponse(heartbeat=self.heartbeat_interval)
    await ws.prepare(request)
    client_id = str(uuid.uuid4())[:8]
    self.ws_clients[client_id] = ws
    # ⚠️ Le client est ajouté AVANT authentification
```

Un client WS non authentifié peut:
- Recevoir les broadcasts `memory_sync` (données de mémoire)
- Recevoir les pings/status avec les infos du nœud
- Envoyer des messages `ping` et `status` sans auth

L'authentification WS est optionnelle et ne bloque que les opérations d'écriture, mais les **données sensibles fuient via les broadcasts**.

**Fix:**
1. Ne pas ajouter le client à `ws_clients` avant authentification
2. Ou au minimum, ne pas broadcaster les données de mémoire aux clients non authentifiés
3. Exiger l'auth dans les premières N secondes, sinon déconnecter

```python
# Auth obligatoire dans les 10 secondes
auth_deadline = time.time() + 10
async for msg in ws:
    if time.time() > auth_deadline and client_id not in self.ws_authenticated:
        await ws.send_json({'type': 'error', 'message': 'Auth timeout'})
        await ws.close()
        break
    # ...
```

---

### 🟠 HIGH-03: Fuite d'informations via `/api/status` et `/` (dashboard) non protégés

**Type:** Information leak  
**Sévérité:** ÉLEVÉE  
**Fichier:** `src/pinkybrain_v4.py` — `handle_status()`, `handle_dashboard()`

Les endpoints `/api/status`, `/api/ping`, `/api/peers`, `/api/monitor`, `/api/capabilities`, `/api/agent`, etc. sont **accessibles sans authentification**.

Ils exposent:
- Noms et IPs des peers (`/api/peers`)
- Clé publique Ed25519 (`/api/status`)
- Capacités matérielles (GPU, RAM, CPU)
- Nombre de requêtes, taux de succès
- État du circuit breaker
- Modèles disponibles
- TOUT le dashboard HTML avec ces infos

**Preuve:**
```bash
# Aucune auth nécessaire
curl http://target:8080/api/status | jq .
curl http://target:8080/api/peers
curl http://target:8080/api/monitor
curl http://target:8080/api/agent
```

**Fix:**
1. Exiger l'authentification sur tous les endpoints sauf `/api/ping`
2. Ou au minimum, masquer les infos sensibles (IPs, clés, modèles) si non authentifié
3. Le dashboard devrait être protégé par mot de passe ou accessible uniquement en local

```python
# Minimum: cacher les détails des peers pour les non-authentifiés
async def handle_peers(self, request):
    auth = self._verify_auth(request)
    peers = [p.to_dict() for p in self.peers]
    if not auth:
        peers = [{"name": p.name, "available": p.available} for p in self.peers]
    return web.json_response(peers)
```

---

### 🟠 HIGH-04: Rate limiting par IP uniquement — contournable

**Type:** Auth bypass / DoS  
**Sévérité:** ÉLEVÉE  
**Fichier:** `src/pinkybrain_v4.py` — `_verify_auth()`

```python
def _verify_auth(self, request):
    client_key = request.remote or "unknown"
    if not self.rate_limiter.allow(client_key):
        return None
```

Le rate limiting est basé sur `request.remote` (l'IP source). Problèmes:
1. Un attaquant derrière un proxy/load-balancer partage la même IP que des utilisateurs légitimes — un seul flood bloque tout le monde
2. Un attaquant avec un botnet a des milliers d'IPs différentes
3. `request.remote` peut être `None` → tous les clients sans IP sont mappés à `"unknown"`, créant un point de contention

De plus, le rate limiter n'est appliqué QUE dans `_verify_auth()`. Les endpoints non authentifiés (`/api/status`, `/api/peers`, `/api/ping`, etc.) ne sont PAS rate-limités.

**Fix:**
1. Ajouter un rate limiter global (middleware) sur TOUS les endpoints
2. Utiliser X-Forwarded-For avec vérification du proxy de confiance
3. Combiner IP + auth identity pour le rate limiting

---

### 🟠 HIGH-05: Vulnérabilité dans la vérification Ed25519 fallback HMAC

**Type:** Auth bypass  
**Sévérité:** ÉLEVÉE  
**Fichier:** `src/pinkybrain_v4.py` — `NodeIdentity.verify()`

```python
def verify(self, message, signature_hex, public_key_hex=None):
    if HAS_NACL and public_key_hex:
        try:
            vk = VerifyKey(bytes.fromhex(public_key_hex))
            vk.verify(message.encode(), bytes.fromhex(signature_hex))
            return True
        except (BadSignatureError, ValueError, TypeError, Exception):
            pass  # ⚠️ Catch-all silencieux — tombe dans le fallback HMAC

    # HMAC fallback — utilise public_key_hex comme clé de vérification!
    verify_key = bytes.fromhex(public_key_hex) if public_key_hex else self._fallback_secret
    expected = hmac_mod.new(verify_key, message.encode(), hashlib.sha256).hexdigest()
    return hmac_mod.compare_digest(expected, signature_hex)
```

Problèmes:
1. **Catch-all `Exception`** dans le bloc Ed25519: toute erreur (y compris une attaque) est avalée silencieusement et on tombe dans le fallback HMAC
2. **Le HMAC fallback utilise `public_key_hex` comme clé de vérification**: un attaquant peut forger n'importe quelle signature en connaissant la clé publique (qui est publique!)
   - `verify_key = bytes.fromhex(public_key_hex)` — la clé publique est SUPPOSÉE être publique!
   - L'attaquant calcule: `hmac_mod.new(bytes.fromhex(victim_public_key), message, sha256).hexdigest()`
   - Cela passe TOUJOURS la vérification HMAC si l'attaquant connaît la clé publique

**Preuve:**
```python
# Un attaquant qui connaît la clé publique (exposée via /api/status)
# peut forger une signature valide pour le fallback HMAC:
attacker_key_hex = "abc123..."  # clé publique de la victime
message = "victim_node:1234567890"
forged_sig = hmac.new(
    bytes.fromhex(attacker_key_hex),
    message.encode(), sha256
).hexdigest()
# → verify(message, forged_sig, attacker_key_hex) retourne True!
```

**Fix:**
```python
def verify(self, message, signature_hex, public_key_hex=None):
    if HAS_NACL and public_key_hex:
        try:
            vk = VerifyKey(bytes.fromhex(public_key_hex))
            vk.verify(message.encode(), bytes.fromhex(signature_hex))
            return True
        except BadSignatureError:
            return False  # Échec Ed25519 = authentification échouée, PAS de fallback
        except (ValueError, TypeError):
            return False  # Clé invalide = échec
    
    # HMAC fallback: utiliser uniquement le secret partagé P2P, JAMAIS la clé publique
    # Ce fallback ne doit fonctionner qu'entre nœuds qui partagent le même secret
    expected = hmac_mod.new(self._fallback_secret, message.encode(), hashlib.sha256).hexdigest()
    return hmac_mod.compare_digest(expected, signature_hex)
```

---

### 🟠 HIGH-06: CORS absent — requêtes cross-origin possibles

**Type:** CORS / CSRF  
**Sévérité:** ÉLEVÉE  
**Fichier:** `src/pinkybrain_v4.py` — `create_app()`

Aucune configuration CORS n'est présente. Par défaut, aiohttp autorise TOUTES les origines pour les réponses JSON (pas de `Access-Control-Allow-Origin`). Cependant:
1. Le dashboard HTML est servi sur `/` — un site malicieux peut iframer ce dashboard
2. Les endpoints API acceptent des POST JSON — un attaquant peut soumettre des formulaires POST (sans CORS, les réponses ne sont pas lisibles, mais les effets de bord s'exécutent)
3. Si un navigateur est utilisé pour accéder au dashboard, un script malicieux sur une autre page peut envoyer des requêtes POST authentifiées via des cookies/tokens stockés

**Fix:**
```python
# Ajouter CORS middleware avec origines autorisées
from aiohttp_middlewares import cors_middleware

app = web.Application(
    middlewares=[
        cors_middleware(
            origins=["http://localhost:*", "https://your-domain.com"],
            allow_methods=["GET", "POST"],
        )
    ]
)
```
Ou au minimum, ajouter les headers de sécurité sur toutes les réponses.

---

## 3. Failles Moyennes

### 🟡 MED-01: Découverte mDNS sans authentification — nœuds malicieux

**Type:** Auth bypass / Spoofing  
**Sévérité:** MOYENNE  
**Fichier:** `src/pinkybrain_v4.py` — `ZeroConfigDiscovery`

Les beacons de découverte mDNS ne sont pas authentifiés:
```python
def _parse_beacon(self, data, addr):
    msg = json.loads(data.decode())
    if msg.get('type') != 'pinkybrain_discovery':
        return None
    if msg['node'] == self.node_name:
        return None
    # ⚠️ Aucune vérification de signature ou secret
    return {'name': msg['node'], 'host': msg.get('ip', addr[0]), ...}
```

Un attaquant sur le réseau local peut:
- Envoyer des beacons malicieux avec une fausse IP pour rediriger le trafic
- Se faire passer pour un nœud légitime
- Empoisonner la table de découverte

**Fix:**
1. Signer les beacons avec la clé Ed25519 ou HMAC du secret P2P
2. Vérifier la signature à la réception
3. Ne pas faire confiance automatiquement aux nœuds découverts sans vérification

```python
def _build_beacon(self):
    msg = json.dumps({...})
    sig = self.identity.sign(msg)
    return json.dumps({'beacon': msg, 'signature': sig}).encode()

def _parse_beacon(self, data, addr):
    msg = json.loads(data.decode())
    # Vérifier la signature avec le secret P2P partagé
    sig = msg.get('signature', '')
    beacon = msg.get('beacon', '')
    if not self.identity.verify(beacon, sig, None):
        return None  # Rejeté
```

---

### 🟡 MED-02: Découverte Tailscale — injection de pairs via `tailscale status --json`

**Type:** Spoofing  
**Sévérité:** MOYENNE  
**Fichier:** `src/pinkybrain_v4.py` — `PeerDiscovery._discover_tailscale()`

```python
proc = await asyncio.create_subprocess_exec(
    'tailscale', 'status', '--json', ...)
# Parse tous les peers trouvés sans vérification
```

Un pair Tailscale malicieux peut se faire passer pour un nœud PinkyBrain. Les pairs sont ajoutés automatiquement sans vérification de leur identité. Le filtrage des doublons est insuffisant (comparaison IP:port uniquement).

**Fix:**
- Vérifier l'identité Ed25519 de chaque pair découvert avant de l'ajouter
- Ajouter une liste blanche de noms de pairs autorisés

---

### 🟡 MED-03: Fuite de secrets dans les logs

**Type:** Information leak  
**Sévérité:** MOYENNE  
**Fichier:** `src/pinkybrain_v4.py` — `_verify_auth()`

```python
logger.info(
    f"Auth rejected: sig verify failed for node={node_name} "
    f"ts={ts} challenge={challenge} "
    f"sig={sig[:16]}... expected={_expected[:16]}..."
)
```

Les logs contiennent des fragments de signatures et de challenges. Même tronqués, ces fragments peuvent aider à reconstruire des tokens valides via des attaques de force brute partielles.

De plus, le secret P2P est stocké en clair dans la config JSON et accessible via l'API `/api/status` si la clé publique est dérivée du secret.

**Fix:**
1. Ne jamais logger de fragments de signatures ou de clés
2. Utiliser des identifiants de requête anonymisés dans les logs
3. S'assurer que les logs ne sont lisibles que par root/l'utilisateur du service

---

### 🟡 MED-04: Pas de validation/sanitisation des données mémoire CRDT

**Type:** Input validation / Deserialization  
**Sévérité:** MOYENNE  
**Fichier:** `src/pinkybrain_v4.py` — `CRDTMemory`, `handle_memory_set()`

```python
async def handle_memory_set(self, request):
    data = await request.json()
    key = data.get("key", "")
    value = data.get("value")  # ⚠️ Aucune validation
    self.memory.set(key, value, ttl, author=author)
```

Et dans `merge_from_sync()`:
```python
def merge_from_sync(self, data):
    for key, entry in data.items():
        # ⚠️ Les données reçues du réseau sont fusionnées sans validation
        self.store[key] = entry
```

Problèmes:
1. Aucune limite sur la taille des clés ou valeurs — un pair malicieux peut remplir la mémoire
2. Les valeurs peuvent être des objets JSON arbitraires (injection de types)
3. Le TTL peut être extrêmement long (pas de maximum)
4. Un pair malicieux peut envoyer des milliers d'entrées via `memory_sync` pour DoS

**Fix:**
```python
MAX_KEY_LENGTH = 256
MAX_VALUE_SIZE = 100000  # 100KB
MAX_TTL = 86400  # 24h max

async def handle_memory_set(self, request):
    data = await request.json()
    key = data.get("key", "")
    value = data.get("value")
    ttl = data.get("ttl")
    
    if not key or len(key) > MAX_KEY_LENGTH:
        return web.json_response({"error": "Invalid key"}, status=400)
    if value is not None and len(json.dumps(value)) > MAX_VALUE_SIZE:
        return web.json_response({"error": "Value too large"}, status=400)
    if ttl and ttl > MAX_TTL:
        ttl = MAX_TTL
    # ...
```

---

### 🟡 MED-05: Timestamp window trop large (60s pour Ed25519, 300s pour HMAC)

**Type:** Replay attack  
**Sévérité:** MOYENNE  
**Fichier:** `src/pinkybrain_v4.py` — `_verify_auth()`

```python
# Ed25519: 60 secondes
if abs(time.time() - int(ts)) > 60:
    return None

# HMAC fallback: 300 secondes (5 minutes!)
if abs(time.time() - ts) > 300:
    return None
```

Une fenêtre de 60s permet un replay pendant 60 secondes. Une fenêtre de 300s (5 minutes!) est beaucoup trop large. Un attaquant qui capture un token HMAC peut le réutiliser pendant 5 minutes.

De plus, il n'y a pas de nonce tracking — le même token peut être rejoué plusieurs fois dans la fenêtre.

**Fix:**
1. Réduire la fenêtre HMAC à 30 secondes maximum
2. Implémenter un cache de tokens récemment utilisés (nonces)
3. Utiliser des UUID comme nonce pour chaque requête

```python
# Ajouter un nonce cache
self._used_nonces = deque(maxlen=10000)  # Garde les 10K derniers nonces

def _verify_auth(self, request):
    # ...
    nonce = request.headers.get('X-PinkyBrain-Nonce', '')
    if nonce and nonce in self._used_nonces:
        return None  # Déjà utilisé
    # Après vérification:
    if nonce:
        self._used_nonces.append(nonce)
```

---

### 🟡 MED-06: `setup.py` installe des packages avec `pip install -q` sans vérification

**Type:** Supply chain attack  
**Sévérité:** MOYENNE  
**Fichier:** `setup.py`

```python
subprocess.run([pip, "install", "-q", req], check=True)
```

Le flag `-q` (quiet) masque les avertissements de sécurité. Il n'y a pas de vérification des hashes des packages, ce qui permet des attaques supply chain si PyPI est compromis.

**Fix:**
1. Utiliser `pip install --require-hashes` avec un fichier de requirements verrouillé
2. Ou au minimum, utiliser `pip install -v` et vérifier les signatures
3. Ajouter un `requirements.txt` avec les versions épinglées

---

### 🟡 MED-07: Token blacklist en mémoire — non persistée, contournable

**Type:** Auth bypass  
**Sévérité:** MOYENNE  
**Fichier:** `src/auth/auth/token_auth.py`

```python
self.blacklisted_tokens: set = set()
```

La blacklist de tokens est en mémoire seulement. Si le serveur redémarre, tous les tokens révoqués redeviennent valides. De plus, cette set grandit indéfiniment sans nettoyage.

**Fix:**
1. Persister la blacklist dans un fichier ou une DB légère
2. Ou utiliser des JWT avec `jti` (JWT ID) et une short TTL
3. Ajouter un nettoyage périodique des tokens expirés de la blacklist

---

## 4. Failles Basses

### 🟢 LOW-01: Logs d'événements dans un fichier world-readable

**Type:** Information leak  
**Sévérité:** BASSE  
**Fichier:** `src/pinkybrain_v4.py` — `log_event()`

```python
log_file = Path(__file__).parent.parent / "logs" / "events.jsonl"
log_file.parent.mkdir(exist_ok=True)
with open(log_file, 'a') as f:
    f.write(json.dumps(entry) + '\n')
```

Le fichier de logs est créé sans permissions restrictives (umask par défaut). Tout utilisateur local peut lire les logs qui contiennent des infos sensibles.

**Fix:**
```python
os.chmod(log_file, 0o600)  # Après chaque écriture
# Ou utiliser le module logging avec RotatingFileHandler (déjà fait pour le log principal)
```

---

### 🟢 LOW-02: PID file dans un répertoire world-writable

**Type:** Information leak / DoS  
**Sévérité:** BASSE  
**Fichier:** `src/pinkybrain_v4.py` — `SystrayDaemon`

```python
self.pid_file = pid_file or os.path.expanduser('~/.pinkybrain/daemon.pid')
```

Le PID file est dans `~/.pinkybrain/` sans permissions restrictives. Un attaquant local pourrait:
- Lire le PID pour cibler le processus
- Écraser le PID file pour perturber la gestion du daemon

**Fix:**
```python
os.chmod(self.pid_file, 0o600)
```

---

### 🟢 LOW-03: Absence de HTTPS — trafic en clair

**Type:** Information leak / MITM  
**Sévérité:** BASSE  
**Fichier:** `src/pinkybrain_v4.py` — toutes les requêtes HTTP

Toutes les communications (HTTP REST + WebSocket) sont en clair. Les tokens, secrets et données transitent non chiffrés. Sur Tailscale (WireGuard), c'est mitigé car le tunnel est chiffré, mais sur un réseau local c'est exploitable.

Le CLI utilise aussi `ctx.verify_mode = ssl.CERT_NONE`:
```python
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
```

**Fix:**
1. Supporter HTTPS/TLS nativement (certificat auto-signé ou Let's Encrypt)
2. Au minimum, exiger TLS pour les communications P2P si pas sur Tailscale
3. Retirer le `CERT_NONE` du CLI ou ajouter un avertissement

---

### 🟢 LOW-04: Absence de Content-Security-Policy et headers de sécurité

**Type:** XSS / Clickjacking  
**Sévérité:** BASSE  
**Fichier:** `src/pinkybrain_v4.py` — `handle_dashboard()`

Le dashboard HTML est servi sans headers de sécurité:
- Pas de `Content-Security-Policy`
- Pas de `X-Content-Type-Options: nosniff`
- Pas de `X-Frame-Options: DENY`
- Pas de `X-XSS-Protection`

Le dashboard contient des données dynamiques qui pourraient être injectées si un nom de nœud contient du HTML/JS.

**Fix:**
```python
async def handle_dashboard(self, request):
    response = web.Response(text=html, content_type='text/html')
    response.headers['Content-Security-Policy'] = "default-src 'self'"
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response
```

---

### 🟢 LOW-05: XSS potentiel dans le dashboard via noms de nœuds/pairs

**Type:** XSS  
**Sévérité:** BASSE  
**Fichier:** `src/pinkybrain_v4.py` — `handle_dashboard()`

Les noms de pairs sont insérés directement dans le HTML sans échappement:
```python
html += f'<span ...>{icon} {p.name}</span>'
```

Si un pair malicieux utilise un nom comme `<script>alert(1)</script>`, le JavaScript s'exécutera dans le navigateur de quiconque visite le dashboard.

**Fix:**
```python
import html as html_module
safe_name = html_module.escape(p.name)
html += f'<span ...>{icon} {safe_name}</span>'
```

---

### 🟢 LOW-06: Auto-updater sans vérification de l'intégrité des téléchargements

**Type:** Supply chain attack  
**Sévérité:** BASSE  
**Fichier:** `src/pinkybrain_v4.py` — `AutoUpdater`

```python
async def check(self):
    async with aiohttp.ClientSession() as session:
        async with session.get(self.GITHUB_API, ...) as resp:
            if resp.status == 200:
                data = await resp.json()
                self.download_url = assets[0].get('browser_download_url')
```

Pas de vérification de:
- Signature GPG du release
- Hash SHA256 du téléchargement
- Certificat TLS (pas de pinning)

Un attaquant MITM pourrait injecter une mise à jour malicieuse.

**Fix:**
1. Vérifier les signatures GPG des releases GitHub
2. Comparer les hashes SHA256 après téléchargement
3. Afficher l'URL de téléchargement et demander confirmation avant d'installer

---

### 🟢 LOW-07: Pas de limitation de taille pour les messages WebSocket

**Type:** DoS  
**Sévérité:** BASSE  
**Fichier:** `src/pinkybrain_v4.py` — `handle_websocket()`

```python
async for msg in ws:
    if msg.type == aiohttp.WSMsgType.TEXT:
        data = json.loads(msg.data)  # ⚠️ Pas de limite de taille
```

Un client WebSocket peut envoyer des messages JSON géants qui consomment toute la mémoire.

**Fix:**
```python
# Configurer aiohttp avec une taille max de message
ws = web.WebSocketResponse(
    heartbeat=self.heartbeat_interval,
    max_msg_size=1048576  # 1MB max
)
```

---

### 🟢 LOW-08: CLI stocke l'historique sans chiffrement

**Type:** Information leak  
**Sévérité:** BASSE  
**Fichier:** `src/pinkybrain_cli.py`

```python
HISTORY_FILE = os.path.expanduser("~/.pinkybrain_history.json")
# ...
with open(HISTORY_FILE, "w") as f:
    json.dump(self.history[-100:], f, indent=2)
```

L'historique contient les prompts et réponses en clair. N'importe quel utilisateur local peut les lire.

**Fix:**
- Restreindre les permissions du fichier: `os.chmod(HISTORY_FILE, 0o600)`
- Ou ne pas stocker les prompts complets (hash seulement)

---

## 5. Résumé & Priorités

| ID | Sévérité | Type | Fichier(s) | Priorité |
|----|----------|------|------------|----------|
| CRIT-01 | 🔴 CRITIQUE | Secret en dur | config/*.json | P0 — Immédiat |
| CRIT-02 | 🔴 CRITIQUE | Auth bypass (replay) | pinkybrain_v4.py | P0 — Immédiat |
| CRIT-03 | 🔴 CRITIQUE | RCE (auto_heal) | pinkybrain_v4.py | P0 — Immédiat |
| HIGH-01 | 🟠 ÉLEVÉE | Input validation | pinkybrain_v4.py | P1 — Cette semaine |
| HIGH-02 | 🟠 ÉLEVÉE | WS sans auth | pinkybrain_v4.py | P1 — Cette semaine |
| HIGH-03 | 🟠 ÉLEVÉE | Info leak (status) | pinkybrain_v4.py | P1 — Cette semaine |
| HIGH-04 | 🟠 ÉLEVÉE | Rate limit bypass | pinkybrain_v4.py | P1 — Cette semaine |
| HIGH-05 | 🟠 ÉLEVÉE | HMAC auth bypass | pinkybrain_v4.py | P1 — Cette semaine |
| HIGH-06 | 🟠 ÉLEVÉE | CORS absent | pinkybrain_v4.py | P1 — Cette semaine |
| MED-01 | 🟡 MOYENNE | mDNS spoofing | pinkybrain_v4.py | P2 — Ce mois |
| MED-02 | 🟡 MOYENNE | Tailscale injection | pinkybrain_v4.py | P2 — Ce mois |
| MED-03 | 🟡 MOYENNE | Log leak | pinkybrain_v4.py | P2 — Ce mois |
| MED-04 | 🟡 MOYENNE | Memory DoS | pinkybrain_v4.py | P2 — Ce mois |
| MED-05 | 🟡 MOYENNE | Timestamp window | pinkybrain_v4.py | P2 — Ce mois |
| MED-06 | 🟡 MOYENNE | Supply chain | setup.py | P2 — Ce mois |
| MED-07 | 🟡 MOYENNE | Token blacklist | token_auth.py | P2 — Ce mois |
| LOW-01 | 🟢 BASSE | Log permissions | pinkybrain_v4.py | P3 — Quand possible |
| LOW-02 | 🟢 BASSE | PID file perms | pinkybrain_v4.py | P3 — Quand possible |
| LOW-03 | 🟢 BASSE | Pas de TLS | pinkybrain_v4.py | P3 — Quand possible |
| LOW-04 | 🟢 BASSE | Pas de CSP | pinkybrain_v4.py | P3 — Quand possible |
| LOW-05 | 🟢 BASSE | XSS dashboard | pinkybrain_v4.py | P3 — Quand possible |
| LOW-06 | 🟢 BASSE | Update integrity | pinkybrain_v4.py | P3 — Quand possible |
| LOW-07 | 🟢 BASSE | WS msg size | pinkybrain_v4.py | P3 — Quand possible |
| LOW-08 | 🟢 BASSE | CLI history leak | pinkybrain_cli.py | P3 — Quand possible |

### Actions immédiates (P0):

1. **Retirer le secret des configs** — utiliser `P2P_SECRET` env var uniquement, ajouter au `.gitignore`
2. **Corriger le Bearer token** — inclure le chemin dans le challenge signé
3. **Désactiver l'auto-heal qui tue des processus** — logger seulement, ou sandboxer

### Actions cette semaine (P1):

4. **Corriger le fallback HMAC** — la clé publique ne doit JAMAIS être utilisée comme clé de vérification
5. **Ajouter un rate limiter global** — middleware sur tous les endpoints
6. **Exiger l'auth WS avant broadcast** — timeout d'auth de 10 secondes
7. **Protéger les endpoints sensibles** — `/api/status`, `/api/peers`, `/api/monitor` avec auth
8. **Ajouter CORS** — limiter les origines autorisées
9. **Valider les entrées** — limite de taille sur prompts, modèles, clés mémoire

---

*Audit réalisé par Bug 🐛 — PinkyBrain Security*  
*Ce rapport doit être revu et les corrections prioritaires appliquées avant tout déploiement en production.*