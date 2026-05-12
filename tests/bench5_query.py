#!/usr/bin/env python3
"""Benchmark 5: QUERY & MODÈLE — latence, failover, erreurs"""
import hmac, hashlib, time, json, urllib.request, urllib.error

HOST = "localhost"
PORT = 8080
SECRET = "test-secret-do-not-use-in-production"
BASE = f"http://{HOST}:{PORT}"

def hmac_headers(path, secret):
    ts = str(time.time())
    msg = f"{path}:{ts}"
    sig = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return {'X-PinkyBrain-Auth': sig, 'X-PinkyBrain-TS': ts, 'Content-Type': 'application/json'}

def post(url, data, headers=None, timeout=120):
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers=headers or {})
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}

def get(url, timeout=10):
    try:
        resp = urllib.request.urlopen(url, timeout=timeout)
        return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}

print("=" * 60)
print("🤖 BENCHMARK 5: QUERY & MODÈLE")
print("=" * 60)

# 5a. Query simple — 5 requêtes basiques
print("\n📊 Query simples (5 requêtes glm-5.1:cloud)")
prompts = [
    "Réponds juste: OK",
    "Donne un nombre entre 1 et 10",
    "Dis bonjour en français",
    "Quelle est la capitale de la Belgique?",
    "Combien font 2+2?",
]
latencies = []
for i, prompt in enumerate(prompts):
    h = hmac_headers("/api/query", SECRET)
    t0 = time.time()
    s, data = post(f"{BASE}/api/query", {"prompt": prompt, "model": "glm-5.1:cloud"}, h, timeout=120)
    dt = (time.time() - t0) * 1000
    if s == 200:
        latencies.append(dt)
        resp = data.get("response", "")[:60]
        routed = "local" if data.get("routed_locally") else "peer"
        print(f"  Q{i+1}: {dt:.0f}ms | {routed} | \"{resp}\"")
    else:
        print(f"  Q{i+1}: FAIL {s} {data}")

if latencies:
    latencies.sort()
    print(f"  Stats: Avg {sum(latencies)/len(latencies):.0f}ms | P50 {latencies[len(latencies)//2]:.0f}ms | Max {latencies[-1]:.0f}ms")

# 5b. Modèle inexistant — failover ou erreur
print("\n📊 Modèle inexistant (doit failover ou erreur propre)")
h = hmac_headers("/api/query", SECRET)
s, data = post(f"{BASE}/api/query", {"prompt": "test", "model": "modele-inexistant-12345"}, h, timeout=30)
print(f"  Status: {s}")
print(f"  Response: {json.dumps(data)[:200]}")

# 5c. Query sans prompt — erreur de validation
print("\n📊 Query sans prompt (erreur validation)")
h = hmac_headers("/api/query", SECRET)
s, data = post(f"{BASE}/api/query", {}, h, timeout=10)
print(f"  Status: {s} | Expected: 400 or error")

# 5d. Query très longue — stress le prompt
print("\n📊 Query prompt long (500 chars)")
long_prompt = "Réponds en un mot. " + "Ceci est du remplissage. " * 25
h = hmac_headers("/api/query", SECRET)
t0 = time.time()
s, data = post(f"{BASE}/api/query", {"prompt": long_prompt, "model": "glm-5.1:cloud"}, h, timeout=120)
dt = (time.time() - t0) * 1000
if s == 200:
    print(f"  Long prompt: {dt:.0f}ms | Réponse: {data.get('response', '')[:60]}")
else:
    print(f"  Long prompt: FAIL {s}")

# 5e. Load balancing — vérifier routing
print("\n📊 Load balancing (10 queries)")
local_count = 0
peer_count = 0
for i in range(10):
    h = hmac_headers("/api/query", SECRET)
    s, data = post(f"{BASE}/api/query", {"prompt": f"Dis juste: {i}", "model": "glm-5.1:cloud"}, h, timeout=120)
    if s == 200:
        if data.get("routed_locally"):
            local_count += 1
        else:
            peer_count += 1
print(f"  Routed local: {local_count} | Routed peer: {peer_count}")
if local_count > 0 and peer_count > 0:
    print(f"  ✅ Load balancing fonctionne (mix local/peer)")
elif local_count > 0:
    print(f"  ⚠️ Tout en local — peer pas utilisé pour ce modèle")

# 5f. Query rate tracking
print("\n📊 Query stats finales")
s, data = get(f"{BASE}/api/status")
q = data.get("queries", {})
print(f"  Total: {q.get('total', '?')} | Successful: {q.get('successful', '?')} | Rate: {q.get('rate', '?')}")

# 5g. Modèles disponibles
print("\n📊 Modèles disponibles")
local = data.get("local_models", [])
peers = data.get("peers", {}).get("list", [])
print(f"  Bug: {local}")
for p in peers:
    if p.get("available"):
        print(f"  {p['name']}: {p.get('models', [])}")

print("\n🤖 Benchmark 5 terminé ✅")