#!/usr/bin/env python3
"""Benchmark 4: CHARGE & CONCURRENCE — stress test, flood, stabilité"""
import hmac, hashlib, time, json, urllib.request, urllib.error, threading, concurrent.futures

HOST = "localhost"
PORT = 8080
SECRET = "test-secret-do-not-use-in-production"
BASE = f"http://{HOST}:{PORT}"

def hmac_headers(path, secret):
    ts = str(time.time())
    msg = f"{path}:{ts}"
    sig = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return {'X-PinkyBrain-Auth': sig, 'X-PinkyBrain-TS': ts, 'Content-Type': 'application/json'}

def get(url, timeout=10):
    try:
        resp = urllib.request.urlopen(url, timeout=timeout)
        return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}

def post(url, data, headers=None, timeout=30):
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
print("⚡ BENCHMARK 4: CHARGE & CONCURRENCE")
print("=" * 60)

# 4a. GET flood — 1000 requêtes status
print("\n📊 GET /api/status x 1000 (séquentiel)")
t0 = time.time()
ok = 0
for i in range(1000):
    s, _ = get(f"{BASE}/api/status")
    if s == 200: ok += 1
dt = time.time() - t0
print(f"  {ok}/1000 OK | {dt:.2f}s | {ok/dt:.0f} req/sec")

# 4b. POST flood — 500 syncs authentifiés
print("\n📊 POST /api/sync x 500 (séquentiel)")
t0 = time.time()
ok = 0
for i in range(500):
    h = hmac_headers("/api/sync", SECRET)
    s, _ = post(f"{BASE}/api/sync", {"memory": {f"flood_{i}": {"value": str(i), "expires": time.time()+60}}}, h)
    if s == 200: ok += 1
dt = time.time() - t0
print(f"  {ok}/500 OK | {dt:.2f}s | {ok/dt:.0f} req/sec")

# 4c. Concurrence progressive — 10, 25, 50, 100 workers
for workers in [10, 25, 50, 100]:
    print(f"\n📊 Concurrence {workers} workers (200 GET chacun)")
    results = {"ok": 0, "fail": 0, "times": []}
    lock = threading.Lock()

    def hit(i):
        t0 = time.time()
        s, _ = get(f"{BASE}/api/status", timeout=10)
        dt = (time.time() - t0) * 1000
        with lock:
            if s == 200:
                results["ok"] += 1
                results["times"].append(dt)
            else:
                results["fail"] += 1

    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(hit, i) for i in range(200)]
        concurrent.futures.wait(futs)
    dt = time.time() - t0

    times = sorted(results["times"]) if results["times"] else [0]
    print(f"  {results['ok']}/200 OK | {dt:.2f}s | {results['ok']/dt:.0f} req/sec | P95: {times[int(len(times)*0.95)]:.1f}ms")

# 4d. Mix lecture/écriture concurrent
print(f"\n📊 Mix lecture/écriture (100 workers, 200 opérations mixtes)")
results = {"reads": 0, "writes": 0, "read_fail": 0, "write_fail": 0, "times": []}
lock = threading.Lock()

def mix_hit(i):
    t0 = time.time()
    if i % 3 == 0:  # 33% writes
        h = hmac_headers("/api/sync", SECRET)
        s, _ = post(f"{BASE}/api/sync", {"memory": {f"mix_{i}": {"value": str(i), "expires": time.time()+60}}}, h)
        with lock:
            if s == 200: results["writes"] += 1
            else: results["write_fail"] += 1
    else:  # 67% reads
        s, _ = get(f"{BASE}/api/status")
        with lock:
            if s == 200: results["reads"] += 1
            else: results["read_fail"] += 1
    with lock:
        results["times"].append((time.time() - t0) * 1000)

t0 = time.time()
with concurrent.futures.ThreadPoolExecutor(max_workers=100) as pool:
    futs = [pool.submit(mix_hit, i) for i in range(200)]
    concurrent.futures.wait(futs)
dt = time.time() - t0
print(f"  Reads: {results['reads']} OK / {results['read_fail']} FAIL")
print(f"  Writes: {results['writes']} OK / {results['write_fail']} FAIL")
print(f"  Total: {dt:.2f}s | {(results['reads']+results['writes'])//dt:.0f} req/sec")

# 4e. Memory après charge — vérifier intégrité
print("\n📊 Intégrité mémoire après charge")
s, data = get(f"{BASE}/api/status")
mem_keys = data.get("memory", {}).get("keys", "?")
queries = data.get("queries", {})
print(f"  Clés en mémoire: {mem_keys}")
print(f"  Queries totales: {queries.get('total', '?')} | Réussies: {queries.get('successful', '?')}")
if queries.get('total', 0) > 0:
    rate = queries.get('successful', 0) / queries['total'] * 100
    print(f"  Taux de succès: {rate:.1f}%")

# 4f. Uptime check
uptime = data.get("uptime", 0)
print(f"  Uptime: {uptime:.0f}s ({uptime/3600:.1f}h)")
print(f"  Pas de crash pendant le benchmark ✅" if uptime > 100 else f"  ⚠️ Uptime bas: {uptime:.0f}s")

print("\n⚡ Benchmark 4 terminé ✅")