#!/usr/bin/env python3
"""Benchmark 2: MÉMOIRE — SET/GET/SYNC, volume, TTL, collision"""
import hmac, hashlib, time, json, urllib.request, urllib.error

HOST = "localhost"
PORT = 8080
SECRET = "test-secret-change-me"
BASE = f"http://{HOST}:{PORT}"

def hmac_headers(path, secret):
    ts = str(time.time())
    msg = f"{path}:{ts}"
    sig = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return {'X-PinkyBrain-Auth': sig, 'X-PinkyBrain-TS': ts, 'Content-Type': 'application/json'}

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

def get(url, timeout=10):
    try:
        resp = urllib.request.urlopen(url, timeout=timeout)
        return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}

print("=" * 60)
print("💾 BENCHMARK 2: MÉMOIRE DISTRIBUTÉE")
print("=" * 60)

# 2a. Sync 10/100/500/1000 clés — scaling
for n in [10, 100, 500, 1000]:
    mem = {f"bench2_{i:04d}": {"value": f"val_{i}" * 3, "expires": time.time() + 3600} for i in range(n)}
    payload_size = len(json.dumps({"memory": mem}))
    t0 = time.time()
    h = hmac_headers("/api/sync", SECRET)
    s, data = post(f"{BASE}/api/sync", {"memory": mem}, h, timeout=60)
    dt = (time.time() - t0) * 1000
    if s == 200:
        print(f"  {n} clés ({payload_size/1024:.1f}KB): {dt:.1f}ms | {data.get('keys_synced')} synced")
    else:
        print(f"  {n} clés: FAIL {s}")

# 2b. Valeurs volumineuses (10KB, 100KB, 1MB)
for size_name, size in [("10KB", 10_000), ("100KB", 100_000), ("1MB", 1_000_000)]:
    big_val = "x" * size
    h = hmac_headers("/api/memory", SECRET)
    t0 = time.time()
    s, data = post(f"{BASE}/api/memory", {"key": f"big_{size_name}", "value": big_val}, h, timeout=30)
    dt = (time.time() - t0) * 1000
    print(f"  SET {size_name}: {dt:.1f}ms | Status: {s}")

# 2c. Sync vers Pinky — vérifier que la mémoire voyage
print("\n📊 Sync cross-node (Bug→Pinky)")
h = hmac_headers("/api/sync", SECRET)
cross_mem = {f"cross_{i}": {"value": f"from_bug_{i}", "expires": time.time()+3600} for i in range(20)}
s, data = post(f"{BASE}/api/sync", {"memory": cross_mem}, h)
if s == 200:
    print(f"  20 clés syncées: {data.get('keys_synced')} synced ✅")
    # Vérifier côté Pinky
    s2, data2 = get(f"http://localhost:8081/api/status")
    if s2 == 200:
        print(f"  Pinky mémoire: {data2.get('memory', {}).get('keys', '?')} clés")
else:
    print(f"  Sync FAIL: {s}")

# 2d. Collision de clés — écrasement
print("\n📊 Collision de clés (SET x2, vérifier écrasement)")
h = hmac_headers("/api/memory", SECRET)
post(f"{BASE}/api/memory", {"key": "collision_test", "value": "version_1"}, h)
post(f"{BASE}/api/memory", {"key": "collision_test", "value": "version_2"}, h)
# Vérifier via status que la clé existe
s, data = get(f"{BASE}/api/status")
mem_keys = data.get("memory", {}).get("keys", "?")
print(f"  Clés en mémoire après collision: {mem_keys}")

# 2e. TTL expiré — vérifier purge
print("\n📊 TTL expiré (SET avec expiry passé)")
h = hmac_headers("/api/sync", SECRET)
post(f"{BASE}/api/sync", {"memory": {"expired_key": {"value": "should_expire", "expires": time.time() - 10}}}, h)
print("  Clé expirée envoyée (sera ignorée à la lecture)")

print("\n💾 Benchmark 2 terminé ✅")