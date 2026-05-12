#!/usr/bin/env python3
"""Benchmark 1: AUTH & SECURITÉ — HMAC, JWT, rejet, timing attacks"""
import hmac, hashlib, time, json, urllib.request, urllib.error

HOST = "localhost"
PORT = 8080
SECRET = "test-secret-do-not-use-in-production"
BASE = f"http://{HOST}:{PORT}"

def hmac_headers(path, secret, ts_offset=0):
    ts = str(time.time() + ts_offset)
    msg = f"{path}:{ts}"
    sig = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return {'X-PinkyBrain-Auth': sig, 'X-PinkyBrain-TS': ts, 'Content-Type': 'application/json'}

def post(url, data, headers=None, timeout=10):
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
print("🔒 BENCHMARK 1: AUTH & SÉCURITÉ")
print("=" * 60)

# 1a. HMAC valide — 500 requêtes, mesurer throughput
print("\n📊 HMAC valide (500 requêtes)")
t0 = time.time()
ok = 0
for i in range(500):
    h = hmac_headers("/api/sync", SECRET)
    s, _ = post(f"{BASE}/api/sync", {"memory": {f"k{i}": {"value": str(i), "expires": time.time()+60}}}, h)
    if s == 200: ok += 1
dt = time.time() - t0
print(f"  {ok}/500 OK | {dt:.2f}s | {ok/dt:.0f} req/sec")

# 1b. Rejet timestamps expirés
print("\n📊 Rejet timestamps expirés (100 requêtes)")
ok_reject = 0
for offset in [-400, -500, -600, -1000, -3600]:
    for i in range(20):
        h = hmac_headers("/api/sync", SECRET, ts_offset=offset)
        s, _ = post(f"{BASE}/api/sync", {"memory": {}}, h)
        if s == 401: ok_reject += 1
print(f"  {ok_reject}/100 rejetés correctement (401)")

# 1c. Rejet mauvais secret
print("\n📊 Rejet mauvais secret (50 requêtes)")
ok_reject = 0
for i in range(50):
    h = hmac_headers("/api/sync", "mauvais-secret-1234")
    s, _ = post(f"{BASE}/api/sync", {"memory": {}}, h)
    if s == 401: ok_reject += 1
print(f"  {ok_reject}/50 rejetés correctement (401)")

# 1d. Rejet path mismatch
print("\n📊 Rejet path mismatch (50 requêtes)")
ok_reject = 0
for i in range(50):
    h = hmac_headers("/api/ping", SECRET)  # Signé pour /api/ping
    s, _ = post(f"{BASE}/api/sync", {"memory": {}}, h)  # Envoyé à /api/sync
    if s == 401: ok_reject += 1
print(f"  {ok_reject}/50 rejetés correctement (401)")

# 1e. Rejet sans aucun header auth
print("\n📊 Rejet sans auth (50 requêtes)")
ok_reject = 0
for i in range(50):
    s, _ = post(f"{BASE}/api/sync", {"memory": {}}, {'Content-Type': 'application/json'})
    if s == 401: ok_reject += 1
print(f"  {ok_reject}/50 rejetés correctement (401)")

# 1f. Timing attack — comparer temps de rejet secret mauvais vs timestamp expiré
print("\n📊 Timing attack (mesure si les rejets sont constants)")
times_wrong_secret = []
times_expired_ts = []
for i in range(100):
    t0 = time.time()
    h = hmac_headers("/api/sync", "wrong-secret")
    post(f"{BASE}/api/sync", {"memory": {}}, h)
    times_wrong_secret.append((time.time() - t0) * 1000)

    t0 = time.time()
    h = hmac_headers("/api/sync", SECRET, ts_offset=-500)
    post(f"{BASE}/api/sync", {"memory": {}}, h)
    times_expired_ts.append((time.time() - t0) * 1000)

avg_ws = sum(times_wrong_secret) / len(times_wrong_secret)
avg_et = sum(times_expired_ts) / len(times_expired_ts)
print(f"  Mauvais secret: {avg_ws:.2f}ms avg")
print(f"  TS expiré: {avg_et:.2f}ms avg")
print(f"  Différence: {abs(avg_ws - avg_et):.2f}ms {'✅ constante' if abs(avg_ws - avg_et) < 1 else '⚠️ possible fuite'}")

print("\n🔒 Benchmark 1 terminé ✅")