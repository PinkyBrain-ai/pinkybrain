# PinkyBrain Security Audit Report

**Date:** 2026-07-07
**Auditor:** Hermes Agent (automated)
**Repo:** `/tmp/pinkybrain-audit`
**Scope:** Full source tree — 14 Python modules in `src/`, config, deploy, docs, scripts

## Methodology

Read all key files (`pinkybrain_v5.py`, `brain_llm.py`, `model_specialist.py`, `conversation_store.py`, `tracker_client.py`, `network_sync.py`, `config/*.json`, `start.sh`, `deploy/*.yml`). Grepped for: `eval`/`exec`/`pickle`/`subprocess`/`shell=True`/`os.system`/`yaml.load`; secrets/keys/tokens in code and docs; all route registrations and auth decorators; CSP/CORS headers; SSL/TLS handling; gossip protocol; deserialization sinks. Cross-referenced against the prior v5.2.0 audit in `references/v52-security-audit.md`.

## Summary

- **Critical:** 1
- **High:** 3
- **Medium:** 5
- **Low:** 4
- **Info:** 3

Prior v5.2.0 audit fixes are verified present (CRIT-01/02, HIGH-01–04, MED-01–05). This audit found **new** issues not covered by the prior audit, plus confirmed the 3 previously-deferred LOW items remain.

---

## Critical

### CRIT-A — P2P secret sent as raw header value to Node Messenger

- **File:** `src/brain_llm.py:462`
- **Severity:** CRIT
- **Issue:** `get_context()` sends the raw `p2p_secret` as the value of the `X-Node-Secret` HTTP header to the Node Messenger search endpoint (`/search` on port 8084):
  ```python
  headers = {"X-Node-Secret": self.p2p_secret or os.environ.get("P2P_SECRET", "")}
  ```
  The shared `p2p_secret` is an HMAC **key** — it must never be transmitted in cleartext over the wire. Any node on the path (or a MITM on the unencrypted HTTP connection) can harvest the secret and forge HMAC auth to every node in the mesh. This also violates the design rule "never use p2p_secret to derive encryption keys / never expose it" — here it is exposed directly.
- **Impact:** Full mesh compromise. Attacker who sniffs one `get_context` call can impersonate any node.
- **Fix:** Replace raw-secret header with an HMAC-signed header (same pattern as `_auth_headers()` at line 103):
  ```python
  def _node_messenger_headers(self, path="/search"):
      ts = str(int(time.time()))
      sig = hmac_mod.new(self.p2p_secret.encode(), f"{path}:{ts}".encode(), hashlib.sha256).hexdigest()
      return {"X-Node-Messenger-Auth": sig, "X-PinkyBrain-TS": ts, "X-PinkyBrain-Node": self.node_name}
  ```
  Node Messenger must verify the HMAC, not compare the raw secret.

---

## High

### HIGH-A — `_persist_config()` writes `p2p_secret` in cleartext to config JSON

- **File:** `src/pinkybrain_v5.py:4499-4507`
- **Severity:** HIGH
- **Issue:** `handle_config_set` (line 4491) calls `_persist_config()` which does `json.dump(self.config, f)` — and `self.config` contains `p2p_secret` in cleartext. The config file at `~/.pinkybrain/config/{node}.json` is written with default umask permissions (likely 0o644, world-readable). The skill explicitly states "Never put p2p_secret in config JSON" — but `_persist_config` re-introduces it. Any config change via the API re-leaks the secret to disk.
- **Impact:** Secret at rest in plaintext, potentially world-readable. Violates the .env-only secret policy.
- **Fix:** Strip `p2p_secret` (and all `SECRET_KEYS`) before writing:
  ```python
  def _persist_config(self):
      safe = {k: v for k, v in self.config.items() if k not in self.SECRET_KEYS}
      # or mask and write placeholder
      safe["p2p_secret"] = "CHANGE_ME_use_env_var_P2P_SECRET"
      json.dump(safe, f, ...)
      os.chmod(config_path, 0o600)
  ```
  Also set file permissions to 0o600 explicitly.

### HIGH-B — Config schema mismatch in `deploy/install.sh` — secret silently ignored

- **File:** `deploy/install.sh:158-193`
- **Severity:** HIGH
- **Issue:** The installer generates a config JSON with `p2p_secret` nested under a `"private"` key:
  ```json
  { "private": { "p2p_secret": "...", "peers": [], "share_ai": true }, ... }
  ```
  But `load_config()` (line 1973) reads `config.get("p2p_secret")` at the **top level**. The auto-generated secret is never read. The server then falls back to env var; if `P2P_SECRET` is not set in `/etc/pinkybrain/env` (it's commented out by default at line 239), the node fails to start with a RuntimeError. If the user "fixes" it by putting the secret at top level, it lives in the config file on disk — defeating the .env policy.
- **Impact:** Node fails to start silently after install; or user is forced to put secret in JSON.
- **Fix:** Either (a) flatten the config schema in install.sh to put `p2p_secret`/`peers`/`share_ai` at top level, matching `load_config()`; or (b) update `load_config()` to read from `config["private"]["p2p_secret"]`. Recommended: write secret to `/etc/pinkybrain/env` (chmod 600) and use a placeholder in the JSON.

### HIGH-C — P2P gossip over plain HTTP with no integrity/auth on the payload

- **File:** `src/pinkybrain_v5.py:4965-4967`
- **Severity:** HIGH
- **Issue:** Gossip push to peers uses `http://` (hardcoded at line 4965) with HMAC auth headers — but the payload itself (memory entries, trust signatures) is sent in cleartext over an unencrypted channel. An attacker on the network can:
  1. Read all memory entries (potential data leak)
  2. Tamper with trust_sign gossip messages (the receiver at `_gossip_propagate` line 4989 blindly calls `self.web_of_trust.add_trust(signer, target)` from the payload — no signature verification on the propagated message)
- The prior audit (HIGH-03) added a warn-once, but the trust propagation path is new: a MITM can inject `{"type":"trust_sign","signer":"evil","target":"victim"}` and the receiving node will add trust without verifying the signer actually signed it.
- **Impact:** Trust graph poisoning; memory data exposure on the wire.
- **Fix:**
  1. For trust_sign gossip: verify the original Ed25519 signature before `add_trust`. Carry the signature in the gossip payload and check it.
  2. For memory_update: the CRDT merge is eventually-consistent (low data-integrity risk), but consider signing gossip payloads.
  3. Support `https://` peer URLs (TLS) — currently hardcoded to `http://`.

---

## Medium

### MED-A — CSP `connect-src` allows `ws:` / `wss:` to any host

- **File:** `src/pinkybrain_v5.py:166`
- **Severity:** MED
- **Issue:** CSP template: `connect-src 'self' ws: wss:` — allows WebSocket connections to any host. A malicious script (if XSS is achieved despite nonce-based script-src) can exfiltrate data via WebSocket to an attacker-controlled server.
- **Impact:** Data exfiltration channel if XSS is achieved.
- **Fix:** Restrict to specific origins: `connect-src 'self' ws://127.0.0.1:* wss://127.0.0.1:*` or derive allowed WS hosts from configured peers.
- **Note:** This was previously identified as LOW-03 and deferred. Upgraded to MED because the trust-sign gossip issue (HIGH-C) increases the likelihood of trust-graph abuse enabling rogue peers.

### MED-B — Auto-updater fetches release info without integrity verification

- **File:** `src/pinkybrain_v5.py:638-657` (`AutoUpdater.check`)
- **Severity:** MED
- **Issue:** The auto-updater fetches `https://api.github.com/.../releases/latest` and returns `download_url` to the user/API caller. There is no signature verification of the release assets, no pinning of the expected publisher. If the GitHub account is compromised (or DNS/TLS is MITM'd despite HTTPS), a malicious update URL is served. The `auto_install` flag (config `auto_update`) could silently install it.
- **Impact:** Supply-chain compromise → arbitrary code execution on update.
- **Fix:** Verify release asset SHA-256 against a known-good hash, or verify a release GPG signature. Disable `auto_install` by default (currently defaults to `config.get('auto_update', False)` — acceptable, but should be documented as dangerous).
- **Note:** Previously LOW-02. Upgraded to MED given auto_install path exists.

### MED-C — `/api/update` endpoint unauthenticated — info disclosure

- **File:** `src/pinkybrain_v5.py:2785, 4639-4644`
- **Severity:** MED
- **Issue:** `handle_update_check` is registered without `_auth_required()`. Any unauthenticated caller can trigger a GitHub API call and learn the current version + whether an update is available. This reveals the running version to attackers (useful for targeting known CVEs in old versions) and causes outbound HTTP calls from the server (minor SSRF-ish amplification).
- **Impact:** Version enumeration; outbound request amplification.
- **Fix:** Wrap with `self._auth_required(...)` or return only `{"update_available": bool}` without version details to unauthenticated callers.

### MED-D — Tracker-discovered node `address` not validated before use

- **File:** `src/tracker_client.py:566-586`
- **Severity:** MED
- **Issue:** `_update_known_node()` accepts `address` from tracker responses and stores it in `known_nodes`. If the tracker is compromised or a malicious node announces a crafted address (e.g., `169.254.169.254`, `127.0.0.1:8080`, or an internal IP), any code that later connects to `node.address` is vulnerable to SSRF. The validator (`validate_discover_response`) only checks that `node_id` or `address` exists — it does not validate the address format or block internal ranges.
- **Impact:** SSRF via crafted tracker responses.
- **Fix:** Validate `address` is a public IP/hostname (reject RFC1918, loopback, link-local) before storing; or only connect to tracker-discovered addresses over a restricted connector that blocks internal ranges.

### MED-E — Conversation encryption key stored as plaintext on disk

- **File:** `src/pinkybrain_v5.py:2099-2106`
- **Severity:** MED
- **Issue:** The per-node conversation encryption key is generated with `secrets.token_urlsafe(32)` and written to `~/.pinkybrain/{node}_conv.key` as **plaintext text** (`write_text`). Anyone who reads this file can decrypt all conversations. File permissions are set to 0o600 (good), but the key is not itself encrypted — any backup, copy, or accidental read exposes it.
- **Impact:** Conversation decryption if key file is accessed.
- **Fix:** Consider storing the key in the OS keyring (e.g., `keyring` library) or encrypting it with a user passphrase. At minimum, document that this file must be protected and excluded from backups.

---

## Low

### LOW-A — No CSRF protection on POST endpoints

- **File:** `src/pinkybrain_v5.py` (all POST routes)
- **Severity:** LOW
- **Issue:** POST endpoints rely on HMAC auth headers (not cookies), so CSRF is largely mitigated — a cross-origin form POST cannot set custom `X-PinkyBrain-Auth` headers. However, the CORS middleware (line 2722) reflects the `Origin` header if it matches an allowed origin, and allowed origins include `http://localhost` and `http://127.0.0.1`. A malicious page on `localhost:other-port` could be an allowed origin and issue credentialed requests.
- **Impact:** Low — header-based auth is not CSRF-bypassable in practice, but the broad localhost CORS is a defense-in-depth gap.
- **Fix:** Narrow CORS to specific ports, not all `localhost` origins.
- **Note:** Previously LOW-01.

### LOW-B — `X-Forwarded-For` trusted from any localhost — rate limit bypass

- **File:** `src/pinkybrain_v5.py:2697-2706`
- **Severity:** LOW
- **Issue:** The rate-limit middleware trusts `X-Forwarded-For` if `request.remote` is `127.0.0.1`/`::1`/`localhost`. Any process on the same machine (or any peer that appears as localhost via a reverse proxy) can spoof its IP via `X-Forwarded-For` to bypass per-IP rate limiting. If a reverse proxy is not in use, this is low impact; if one is, it should set XFF correctly.
- **Impact:** Rate-limit bypass from localhost.
- **Fix:** Only trust XFF from explicitly configured proxy IPs, not all localhost.

### LOW-C — `model_specialist.py` / `model_registry.py` keyword lists match "exec"/"execute" — false positive risk

- **File:** `src/model_specialist.py:124`, `src/model_registry.py:553`
- **Severity:** LOW (info)
- **Issue:** `model_registry.py:553` rejects catalog entries containing the string `exec` (case-insensitive). This is an XSS/injection filter for catalog text fields, but "exec" is a substring of "execute", "execution", "executive" — legitimate model descriptions may be rejected. Not a security hole, but a robustness/availability issue that could cause catalog load failures.
- **Fix:** Use word-boundary regex: `r'\bexec\b'` or match the full dangerous pattern `eval(` / `exec(` rather than the bare word.

### LOW-D — `start.sh` uses `source .env` without quoting — word-splitting on secrets with spaces

- **File:** `start.sh:10`
- **Severity:** LOW
- **Issue:** `source "$ENV_FILE"` — if `.env` contains `P2P_SECRET=my secret with spaces`, the secret is truncated/mangled. Not a direct vulnerability, but can cause auth failures that users debug by putting the secret in config JSON (regression to HIGH-A).
- **Fix:** Document that secrets must not contain spaces, or use a more robust `.env` parser.

---

## Info (positive findings — security controls verified working)

1. **No `eval`/`exec`/`pickle`/`marshal`/`yaml.load` usage** — confirmed across all 14 source modules. No unsafe deserialization.
2. **All POST/PUT/DELETE endpoints wrapped with `_auth_required()`** — verified all 40+ mutating routes at lines 2766-2872. No auth bypass found (prior CRIT-02 fix on `/api/brain/consensus` confirmed).
3. **HMAC anti-replay** — nonce cache (`_check_and_add_nonce`), 30s timestamp window, path-in-challenge to prevent cross-endpoint replay (lines 2609-2661).
4. **Path traversal protection** — `_sanitize_filename` (conversation_store.py:70) rejects `/`, `\`, `:`, `.`; `_validate_path_safety` (line 107) validates resolved path stays within base dir.
5. **Per-node conversation encryption** — key not derived from `p2p_secret` (MED-01 fix confirmed at line 2098).
6. **Ed25519 identity keys** — random, persistent, backed up (MED-02 fix confirmed at lines 761-807).
7. **Tracker client** — HTTPS-only (line 300), TLS cert verification on (line 342), announcement sanitization strips secrets (line 133), response size capped (line 667).
8. **Config masking** — `_mask_config` (line 4447) masks SECRET_KEYS in API responses; `handle_config_set` refuses to modify secret keys (line 4477).
9. **Docker hardening** — `no-new-privileges`, `read_only`, non-root user, `tmpfs noexec`, internal network, Ollama uses `expose` not `ports`.
10. **Systemd hardening** — `ProtectSystem=strict`, `PrivateDevices`, `MemoryDenyWriteExecute`, `SystemCallFilter=@system-service`.
11. **Input validation** — `MAX_PROMPT_LENGTH`, `ALLOWED_MODEL_PATTERN`, `ALLOWED_STRATEGIES` enforced on all query endpoints.
12. **No hardcoded API keys** in source — `sk-...` in docs are placeholder examples (confirmed: `docs/README_RU.md:48`, `docs/README_DE.md:49`, `docs/DESIGN_MODEL_SHARING.md:30` use `"sk-..."` as example, not a real key).

---

## Recommendations (priority order)

1. **Fix CRIT-A immediately** — `brain_llm.py:462` raw secret in header. This is a live mesh-compromise vector.
2. **Fix HIGH-A** — strip secrets from `_persist_config` before writing to disk.
3. **Fix HIGH-C** — verify Ed25519 signatures on propagated `trust_sign` gossip; support HTTPS peers.
4. **Fix HIGH-B** — align install.sh config schema with `load_config()`.
5. **Fix MED-C/MED-D** — auth on `/api/update`; validate tracker node addresses.
6. **Address MED-A/MED-B** — tighten CSP connect-src; add release integrity verification.
7. **Fix LOW-C** — false-positive regex in catalog validation.