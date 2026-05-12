#!/usr/bin/env python3
"""Benchmark 3: P2P & RÉSEAU — latence, failover, discovery, circuit breaker"""
import hmac, hashlib, time, json, urllib.request, urllib.error

HOST = "localhost"
PORT = 8080
SECRET = "test-secret-change-me"
BASE = f"http://{HOST}:{PORT}"
PINKY = "http://localhost:8081"

def hmac_headers(path, secret):
    ts = str(time.time())
    msg = f"{path}:{ts}"
    sig = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return {'X-PinkyBrain-Auth': sig, 'X-PinkyBrain-TS': ts, 'Content-Type': 'application/json'}

def get(url, timeout=5):
    try:
        resp = urllib.request.urlopen(url, timeout=timeout)
        return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}

def post(url, data, headers=None, timeout=60):
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers=headers or {})
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}

print("=" * 60)
print("🌐 BENCHMARK 3: P2P & RÉSEAU")
print("=" * 60)

# 3a. Ping latence Bug↔Pinky (50 pings chaque direction)
print("\n📊 Latence P2P (50 pings)")
bug_to_pinky = []
pinky_to_bug = []

for i in range(50):
    t0 = time.time()
    get(f"{PINKY}/api/status", timeout=5)
    bug_to_pinky.append((time.time() - t0) * 1000)

for i in range(50):
    t0 = time.time()
    get(f"{BASE}/api/status", timeout=5)
    pinky_to_bug.append((time.time() - t0) * 1000)

def stats(l):
    l.sort()
    return f"Avg {sum(l)/len(l):.1f}ms | P50 {l[len(l)//2]:.1f}ms | P95 {l[int(len(l)*0.95)]:.1f}ms | Min {l[0]:.1f}ms | Max {l[-1]:.1f}ms"

print(f"  Bug → Pinky: {stats(bug_to_pinky)}")
print(f"  Pinky → Bug: {stats(pinky_to_bug)}")

# 3b. Discovery — vérifier les peers détectés
print("\n📊 Peer discovery")
s, data = get(f"{BASE}/api/peers")
if s == 200:
    peers = data if isinstance(data, list) else data.get("peers", [])
    for p in peers:
        print(f"  {p['name']}: {p['host']}:{p['port']} | {'✅' if p['available'] else '❌'} | Lat: {p['latency']:.1f}ms | CB: {p['circuit_breaker']['state']}")

s2, data2 = get(f"{PINKY}/api/peers")
if s2 == 200:
    peers2 = data2 if isinstance(data2, list) else data2.get("peers", [])
    for p in peers2:
        print(f"  {p['name']}: {p['host']}:{p['port']} | {'✅' if p['available'] else '❌'} | Lat: {p['latency']:.1f}ms | CB: {p['circuit_breaker']['state']}")

# 3c. Sync cross-node 50 fois — stabilité
print("\n📊 Sync cross-node stabilité (50 syncs)")
ok = 0
fail = 0
for i in range(50):
    h = hmac_headers("/api/sync", SECRET)
    s, _ = post(f"{BASE}/api/sync", {"memory": {f"cross_{i}": {"value": str(i), "expires": time.time()+60}}}, h)
    if s == 200: ok += 1
    else: fail += 1
print(f"  {ok} OK / {fail} FAIL")

# 3d. Requête simultanée aux 2 nodes
print("\n📊 Requêtes simultanées Bug + Pinky (20 chacune)")
import concurrent.futures
results = {"bug_ok": 0, "pinky_ok": 0, "bug_fail": 0, "pinky_fail": 0}

def hit(node, i):
    try:
        s, _ = get(f"{node}/api/status", timeout=5)
        return (node, s == 200)
    except:
        return (node, False)

with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
    futs = []
    for i in range(20):
        futs.append(pool.submit(hit, BASE, i))
        futs.append(pool.submit(hit, PINKY, i))
    bug_ok = 0; bug_fail = 0; pinky_ok = 0; pinky_fail = 0
    for f in concurrent.futures.as_completed(futs):
        node, ok = f.result()
        if node == BASE:
            if ok: bug_ok += 1
            else: bug_fail += 1
        else:
            if ok: pinky_ok += 1
            else: pinky_fail += 1

print(f"  Bug: {bug_ok} OK / {bug_fail} FAIL")
print(f"  Pinky: {pinky_ok} OK / {pinky_fail} FAIL")

# 3e. Connexion interrompue — recovery
print("\n📊 Connexion morte (port 9999)")
t0 = time.time()
try:
    urllib.request.urlopen("http://localhost:9999/api/status", timeout=3)
except:
    pass
dt = (time.time() - t0) * 1000
print(f"  Timeout en {dt:.0f}ms {'✅ rapide (< 3s)' if dt < 3000 else '⚠️ lent'}")

# 3f. Circuit breaker état final
print("\n📊 Circuit breaker final")
s, data = get(f"{BASE}/api/status")
for p in data.get("peers", {}).get("list", []):
    cb = p["circuit_breaker"]
    print(f"  {p['name']}: {cb['state']} | failures: {cb['failures']} | last: {cb.get('last_failure',0)}")

print("\n🌐 Benchmark 3 terminé ✅")