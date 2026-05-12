#!/usr/bin/env python3
"""
🖥️ PinkyBrain CLI — Client interactif v5
Utilise PinkyBrain comme application, avec ou sans réseau P2P.
Partage CPU/RAM avec le réseau quand share_ai=true.

Commands:
  serve              Start headless service
  app                Start application (opens browser)
  sidekick           Start system tray sidekick
  chat               Interactive terminal chat (REPL)
  ask "question"     Single query
  status             Show node status
  peers              List connected peers
  share <model>      Share a model with the mesh
  unshare <model>    Stop sharing a model
  shared             List shared models
  download <model>   Download a model from the mesh
  mesh join          Join the public mesh
  mesh leave         Leave the public mesh
  mesh status        Show mesh status
  conversations      List conversations
  conversations <id> Show a conversation
  conversations <id> export  Export a conversation
  install-service    Install as systemd service
  uninstall-service  Uninstall systemd service
"""

import sys
import os
import json
import time
import urllib.request
import urllib.parse
import hmac
import hashlib
import ssl

# ============================================================================
# CONFIG
# ============================================================================

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
HISTORY_FILE = os.path.expanduser("~/.pinkybrain_history.json")

# SSL context (skip verification for local)
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# ============================================================================
# API CLIENT
# ============================================================================

class PinkyBrainClient:
    """Lightweight client for PinkyBrain API."""

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT, secret=None):
        self.host = host
        self.port = port
        self.secret = secret
        self.base = f"http://{host}:{port}"

    def _auth_headers(self, path="/api/query"):
        headers = {}
        if self.secret:
            ts = str(int(time.time()))
            sig = hmac.new(
                self.secret.encode(),
                f"{path}:{ts}".encode(),
                hashlib.sha256
            ).hexdigest()
            headers["X-PinkyBrain-Auth"] = sig
            headers["X-PinkyBrain-TS"] = ts
        return headers

    def _request(self, path, data=None, method="GET"):
        url = f"{self.base}{path}"
        headers = self._auth_headers(path)
        body = None
        if data:
            body = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
            method = "POST"
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            try:
                return json.load(e)
            except:
                return {"error": f"HTTP {e.code}"}
        except Exception as e:
            return {"error": str(e)}

    def status(self):
        return self._request("/api/status")

    def quota(self, peer=None):
        path = f"/api/quota/{peer}" if peer else "/api/quota"
        return self._request(path)

    def query(self, prompt, model=None, strategy="auto"):
        return self._request("/api/query", {
            "prompt": prompt,
            "model": model,
            "strategy": strategy
        })

    def memory_set(self, key, value, ttl=None):
        return self._request("/api/memory/set", {
            "key": key, "value": value, "ttl": ttl
        })

    def memory_get(self, key):
        return self._request(f"/api/memory/{key}")

    def peers(self):
        return self._request("/api/peers")


# ============================================================================
# INTERACTIVE SHELL (unchanged — used by `pinkybrain chat`)
# ============================================================================

class PinkyBrainShell:
    """Interactive shell for PinkyBrain."""

    PROMPT = "PinkyBrain> "
    COMMANDS = {
        "help": "Show this help",
        "status": "Show node status",
        "peers": "List connected peers",
        "models": "List available models",
        "quota": "Show sharing quotas for peers",
        "memory": "Memory operations (set/get/search)",
        "history": "Show query history",
        "export": "Export history (json/txt)",
        "model": "Set default model",
        "ensemble": "Query with ensemble consensus",
        "config": "Show current configuration",
        "quit": "Exit PinkyBrain CLI",
    }

    def __init__(self, client):
        self.client = client
        self.history = []
        self.default_model = None
        self._load_history()

    def _load_history(self):
        try:
            if os.path.exists(HISTORY_FILE):
                # LOW-08: Restrict history file permissions
                os.chmod(HISTORY_FILE, 0o600)
                with open(HISTORY_FILE) as f:
                    # LOW-08: Only load truncated prompts (no full content stored)
                    self.history = json.load(f)
        except:
            self.history = []

    def _save_history(self):
        try:
            with open(HISTORY_FILE, "w") as f:
                # LOW-08: Truncate prompts in history to 80 chars
                safe_history = []
                for entry in self.history[-100:]:
                    if isinstance(entry, dict):
                        safe_entry = dict(entry)
                        prompt = safe_entry.get('prompt', '')
                        if len(prompt) > 80:
                            safe_entry['prompt'] = prompt[:77] + '...'
                        safe_history.append(safe_entry)
                    else:
                        safe_history.append(entry)
                json.dump(safe_history, f, indent=2)
            os.chmod(HISTORY_FILE, 0o600)  # LOW-08
        except:
            pass

    def run(self):
        """Main interactive loop."""
        print()
        print("🖥️  PinkyBrain CLI v5")
        print("   P2P Distributed AI Network")
        print()

        # Check connection
        status = self.client.status()
        if "error" in status:
            print(f"❌ Cannot connect to PinkyBrain at {self.client.base}")
            print(f"   Start it with: pinkybrain serve")
            print()
            return

        node = status.get("node", "?")
        version = status.get("version", "?")
        share_ai = status.get("share_ai", False)
        peers_count = status.get("peers", {}).get("available", 0)

        print(f"✅ Connected to {node} (v{version})")
        if share_ai:
            print(f"📤 Sharing CPU/RAM with network ({peers_count} peer(s))")
        else:
            print(f"🔇 AI sharing disabled — your models are private")
        print()
        print("Type 'help' for commands, or just type your prompt.")
        print()

        while True:
            try:
                line = input(self.PROMPT).strip()
            except (EOFError, KeyboardInterrupt):
                print("\n👋 Bye!")
                break

            if not line:
                continue

            # Check if it's a command
            if line.startswith("/"):
                self._handle_command(line[1:])
            elif line.lower() in ("quit", "exit", "q"):
                print("👋 Bye!")
                break
            elif line.lower() == "help":
                self._show_help()
            else:
                # It's a prompt — send query
                self._do_query(line)

    def _show_help(self):
        print()
        print("📚 PinkyBrain CLI Commands:")
        print("─" * 40)
        for cmd, desc in self.COMMANDS.items():
            print(f"  /{cmd:12s} {desc}")
        print()
        print("Just type your prompt to query the AI.")
        print("Use /model <name> to set a default model.")
        print()

    def _handle_command(self, cmd_line):
        parts = cmd_line.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd == "status":
            self._show_status()
        elif cmd == "peers":
            self._show_peers()
        elif cmd == "models":
            self._show_models()
        elif cmd == "model":
            if args:
                self.default_model = args.strip()
                print(f"✅ Default model set to: {self.default_model}")
            else:
                print(f"Current default model: {self.default_model or 'auto'}")
        elif cmd == "memory":
            self._handle_memory(args)
        elif cmd == "history":
            self._show_history(args)
        elif cmd == "export":
            self._export_history(args)
        elif cmd == "ensemble":
            if args:
                self._do_query(args, strategy="ensemble")
            else:
                print("Usage: /ensemble <prompt>")
        elif cmd == "quota":
            self._show_quota(args)
        elif cmd == "config":
            self._show_config()
        elif cmd in ("quit", "exit", "q"):
            print("👋 Bye!")
            sys.exit(0)
        elif cmd == "help":
            self._show_help()
        else:
            print(f"Unknown command: /{cmd}. Type /help for commands.")

    def _do_query(self, prompt, strategy="auto"):
        model = self.default_model
        print(f"📝 Querying{' [' + model + ']' if model else ''}...")

        start = time.time()
        result = self.client.query(prompt, model=model, strategy=strategy)
        elapsed = time.time() - start

        if "error" in result:
            print(f"❌ Error: {result['error']}")
            return

        response = result.get("response", "")
        source = result.get("source", "?")
        used_model = result.get("model", "?")

        # Store in history
        entry = {
            "timestamp": time.time(),
            "prompt": prompt[:200],
            "response": response[:500],
            "model": used_model,
            "source": source,
            "strategy": strategy,
            "latency": round(elapsed, 2)
        }
        self.history.append(entry)
        self._save_history()

        # Display
        print()
        print(f"💬 Response ({used_model} via {source}, {elapsed:.1f}s):")
        print("─" * 60)
        print(response)
        print("─" * 60)
        print()

    def _show_status(self):
        status = self.client.status()
        if "error" in status:
            print(f"❌ {status['error']}")
            return

        print()
        print(f"📊 PinkyBrain v{status.get('version', '?')} — {status.get('node', '?')}")
        print("─" * 40)
        print(f"  Uptime:   {status.get('uptime', 0)/3600:.1f}h")
        print(f"  Share AI:   {'Yes ✅' if status.get('share_ai') else 'No 🔇'}")
        print(f"  Stealth:    {'Yes 🔒' if status.get('stealth_mode') else 'No'}")

        peers = status.get("peers", {})
        print(f"  Peers:   {peers.get('available', 0)}/{peers.get('total', 0)} available")

        queries = status.get("queries", {})
        print(f"  Queries: {queries.get('total', 0)} ({queries.get('rate', 0):.1f}% success)")

        memory = status.get("memory", {})
        print(f"  Memory:  {memory.get('active_entries', 0)}/{memory.get('total_entries', 0)} entries")

        models = status.get("local_models", [])
        if models:
            print(f"  Models:  {', '.join(models[:5])}")
        print()

    def _show_peers(self):
        peers = self.client.peers()
        if isinstance(peers, dict) and "error" in peers:
            print(f"❌ {peers['error']}")
            return
        if not peers:
            print("No peers connected.")
            return

        print()
        print("🌐 Connected Peers:")
        print("─" * 40)
        for p in peers:
            name = p.get("name", "?")
            host = p.get("host", "?")
            port = p.get("port", "?")
            models = p.get("models", [])
            latency = p.get("latency_ms", "?")
            status_icon = "✅" if p.get("available") else "❌"
            print(f"  {status_icon} {name} ({host}:{port}) {latency}ms")
            if models:
                print(f"     Models: {', '.join(models[:4])}")
        print()

    def _show_models(self):
        status = self.client.status()
        models = status.get("local_models", [])
        providers = status.get("providers", {})

        print()
        print("🧠 Available Models:")
        print("─" * 40)
        if providers:
            for name, info in providers.items():
                ptype = info.get("type", "?")
                enabled = "✅" if info.get("enabled") else "❌"
                pmodels = info.get("models", [])
                print(f"  {enabled} {name} ({ptype})")
                for m in pmodels:
                    marker = " ← default" if m == self.default_model else ""
                    print(f"     • {m}{marker}")
        elif models:
            for m in models:
                marker = " ← default" if m == self.default_model else ""
                print(f"  • {m}{marker}")
        else:
            print("  No models available")
        print()

    def _handle_memory(self, args):
        if not args:
            print("Usage: /memory set <key> <value> | /memory get <key>")
            return
        parts = args.split(maxsplit=2)
        subcmd = parts[0].lower()

        if subcmd == "set" and len(parts) >= 3:
            key, value = parts[1], parts[2]
            result = self.client.memory_set(key, value)
            print(f"✅ Memory set: {key}")
        elif subcmd == "get" and len(parts) >= 2:
            key = parts[1]
            result = self.client.memory_get(key)
            if "error" in result:
                print(f"❌ {result['error']}")
            else:
                print(f"📦 {key}: {json.dumps(result.get('value'), indent=2)[:300]}")
        else:
            print("Usage: /memory set <key> <value> | /memory get <key>")

    def _show_history(self, args=""):
        limit = 10
        if args:
            try:
                limit = int(args)
            except:
                pass

        if not self.history:
            print("No history yet.")
            return

        print()
        print(f"📜 Recent Queries (last {limit}):")
        print("─" * 40)
        for entry in self.history[-limit:]:
            ts = time.strftime("%H:%M:%S", time.localtime(entry.get("timestamp", 0)))
            prompt = entry.get("prompt", "?")[:60]
            model = entry.get("model", "?")
            latency = entry.get("latency", "?")
            print(f"  [{ts}] {prompt}... ({model}, {latency}s)")
        print()

    def _export_history(self, fmt="json"):
        if not self.history:
            print("No history to export.")
            return
        if fmt == "json":
            print(json.dumps(self.history, indent=2, ensure_ascii=False)[:2000])
        else:
            for entry in self.history:
                print(f"[{entry.get('timestamp')}] {entry.get('prompt')}")
                print(f"  → {entry.get('response', '')[:200]}")
                print()

    def _show_quota(self, args=""):
        peer = args.strip() if args else None
        data = self.client.quota(peer)
        if "error" in data:
            print(f"\u274c {data['error']}")
            return

        print()
        print("\u2696\ufe0f  Sharing Quotas:")
        print("\u2500" * 50)

        if peer and "peer" in data:
            # Single peer detail
            print(f"  Peer:          {data['peer']}")
            print(f"  Score:         {data['score']}/100")
            print(f"  Quota:         {data['quota_qpm']} queries/min")
            print(f"  Models:        {data['models_hosted']}")
            print(f"  Chunks:        {data['chunks_distributed']}")
            print(f"  Uptime:        {data['uptime_hours']}h")
            print(f"  Reputation:    {data['reputation']}")
            print(f"  Served:        {data['queries_served']}")
            print(f"  Made:          {data['queries_made']}")
        else:
            # All peers summary
            if not data:
                print("  No peer quotas yet (peers haven't connected)")
            for name, info in data.items():
                print(f"  {name:15s}  score={info['score']:5.1f}  quota={info['quota_qpm']:3d} q/m  models={info['models_hosted']}")
        print()

    def _show_config(self):
        status = self.client.status()
        print()
        print("⚙️  Configuration:")
        print("─" * 40)
        print(f"  Node:      {status.get('node', '?')}")
        print(f"  Version:  {status.get('version', '?')}")
        print(f"  Share AI:   {status.get('share_ai', False)}")
        print(f"  Stealth:    {status.get('stealth_mode', False)}")
        print(f"  Default model: {self.default_model or 'auto'}")
        print()


# ============================================================================
# HELPER: Load config & create client
# ============================================================================

def _load_config_and_client(node, host, port, secret):
    """Load node config and return a PinkyBrainClient."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_dirs = [
        os.path.join(os.path.expanduser("~"), ".pinkybrain", "config"),
        os.path.join(os.path.dirname(script_dir), "config"),
    ]

    for config_dir in config_dirs:
        config_path = os.path.join(config_dir, f"{node}.json")
        if os.path.exists(config_path):
            try:
                with open(config_path) as f:
                    config = json.load(f)
                port = config.get("port", port)
                secret = config.get("p2p_secret", secret)
                break
            except:
                pass

    return PinkyBrainClient(host=host, port=port, secret=secret)


# ============================================================================
# SUBCOMMAND HANDLERS
# ============================================================================

def cmd_serve(args):
    """Start PinkyBrain as a headless service (no GUI)."""
    node = args.node
    client = _load_config_and_client(node, args.host, args.port, args.secret)
    status = client.status()
    if "error" not in status:
        print(f"✅ PinkyBrain service already running at {client.base}")
        print(f"   Node: {status.get('node', '?')}, v{status.get('version', '?')}")
        return

    # Service not running — try to start it
    script_dir = os.path.dirname(os.path.abspath(__file__))
    server_script = os.path.join(script_dir, "pinkybrain_v5.py")
    if not os.path.exists(server_script):
        print(f"❌ Cannot find server script: {server_script}")
        sys.exit(1)

    import subprocess
    cmd = [sys.executable, server_script, node]
    if args.host != DEFAULT_HOST:
        cmd.extend(["--host", args.host])
    if args.port != DEFAULT_PORT:
        cmd.extend(["--port", str(args.port)])

    print(f"🔧 Starting PinkyBrain service (node: {node})...")
    if args.daemon:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"✅ Service started in background (PID: {proc.pid})")
        print(f"   API: {client.base}")
    else:
        print(f"   Starting in foreground. Press Ctrl+C to stop.")
        try:
            subprocess.run(cmd)
        except KeyboardInterrupt:
            print("\n🛑 Service stopped.")


def cmd_app(args):
    """Start PinkyBrain application (opens browser)."""
    client = _load_config_and_client(args.node, args.host, args.port, args.secret)

    # Ensure server is running
    status = client.status()
    if "error" in status:
        print("⚠️  PinkyBrain not running. Starting service...")
        import subprocess
        script_dir = os.path.dirname(os.path.abspath(__file__))
        server_script = os.path.join(script_dir, "pinkybrain_v5.py")
        subprocess.Popen([sys.executable, server_script, args.node],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        import time as _t
        for _ in range(10):
            _t.sleep(1)
            status = client.status()
            if "error" not in status:
                break

    url = f"{client.base}"
    if args.native:
        try:
            import pywebview
            webview.create_window("PinkyBrain", url)
            webview.start()
        except ImportError:
            print("⚠️  pywebview not installed. Opening in browser instead.")
            import webbrowser
            webbrowser.open(url)
    else:
        import webbrowser
        print(f"🌐 Opening PinkyBrain at {url}")
        if not args.no_open:
            webbrowser.open(url)
        print("   Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n👋 PinkyBrain app closed.")


def cmd_sidekick(args):
    """Start PinkyBrain as a system tray sidekick."""
    client = _load_config_and_client(args.node, args.host, args.port, args.secret)

    # Ensure server is running
    status = client.status()
    if "error" in status:
        print("⚠️  PinkyBrain not running. Starting service...")
        import subprocess
        script_dir = os.path.dirname(os.path.abspath(__file__))
        server_script = os.path.join(script_dir, "pinkybrain_v5.py")
        subprocess.Popen([sys.executable, server_script, args.node],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        import time as _t
        for _ in range(10):
            _t.sleep(1)
            status = client.status()
            if "error" not in status:
                break

    if args.install:
        _install_sidekick_autostart()
        return
    elif args.uninstall:
        _uninstall_sidekick_autostart()
        return

    try:
        import pystray
        _run_tray_icon(client)
    except ImportError:
        print("⚠️  pystray not installed. Install with: pip install pystray Pillow")
        print("   Running in minimal mode (no tray icon).")
        print("   Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n👋 PinkyBrain sidekick stopped.")


def _run_tray_icon(client):
    """Run the system tray icon."""
    from PIL import Image, ImageDraw

    def create_icon_image():
        img = Image.new('RGB', (64, 64), color=(0, 0, 0, 0))
        dc = ImageDraw.Draw(img)
        dc.ellipse([8, 8, 56, 56], fill='#4CAF50')
        return img

    def on_open(icon, item):
        import webbrowser
        webbrowser.open(client.base)

    def on_status(icon, item):
        status = client.status()
        if "error" in status:
            icon.notify("PinkyBrain: Disconnected", "PinkyBrain")
        else:
            peers = status.get("peers", {}).get("available", 0)
            icon.notify(f"PinkyBrain: {peers} peer(s)", "PinkyBrain")

    def on_quit(icon, item):
        icon.stop()

    icon = pystray.Icon(
        "PinkyBrain",
        create_icon_image(),
        "PinkyBrain",
        menu=pystray.Menu(
            pystray.MenuItem("💬 Open Chat", on_open),
            pystray.MenuItem("📊 Status", on_status),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("❌ Quit", on_quit),
        ),
    )
    icon.run()


def _install_sidekick_autostart():
    """Install sidekick as autostart entry."""
    autostart_dir = os.path.expanduser("~/.config/autostart")
    os.makedirs(autostart_dir, exist_ok=True)
    desktop_path = os.path.join(autostart_dir, "pinkybrain-sidekick.desktop")
    content = f"""[Desktop Entry]
Type=Application
Name=PinkyBrain Sidekick
Comment=PinkyBrain P2P AI Network - System Tray
Exec={sys.executable} {os.path.abspath(sys.argv[0])} sidekick
Icon=pinkybrain
Terminal=false
Categories=Network;AI;
"""
    with open(desktop_path, "w") as f:
        f.write(content)
    print(f"✅ Sidekick autostart installed: {desktop_path}")


def _uninstall_sidekick_autostart():
    """Remove sidekick autostart entry."""
    desktop_path = os.path.expanduser("~/.config/autostart/pinkybrain-sidekick.desktop")
    if os.path.exists(desktop_path):
        os.remove(desktop_path)
        print("✅ Sidekick autostart removed.")
    else:
        print("ℹ️  No sidekick autostart found.")


def cmd_chat(args):
    """Start interactive terminal chat (REPL)."""
    client = _load_config_and_client(args.node, args.host, args.port, args.secret)
    shell = PinkyBrainShell(client)
    if args.model:
        shell.default_model = args.model
    shell.run()


def cmd_ask(args):
    """Send a single query and print the response."""
    client = _load_config_and_client(args.node, args.host, args.port, args.secret)
    strategy = "ensemble" if args.ensemble else "auto"
    result = client.query(args.question, model=args.model, strategy=strategy)
    if "error" in result:
        print(f"❌ {result['error']}")
        sys.exit(1)
    print(result.get("response", ""))


def cmd_status(args):
    """Show node status."""
    client = _load_config_and_client(args.node, args.host, args.port, args.secret)
    status = client.status()
    if "error" in status:
        print(f"❌ Cannot connect to PinkyBrain at {client.base}")
        print(f"   Make sure PinkyBrain is running: pinkybrain serve")
        sys.exit(1)

    print(f"📊 PinkyBrain v{status.get('version', '?')} — {status.get('node', '?')}")
    print("─" * 50)
    print(f"  Uptime:     {status.get('uptime', 0)/3600:.1f}h")
    print(f"  Share AI:   {'Yes ✅' if status.get('share_ai') else 'No 🔇'}")
    print(f"  Stealth:    {'Yes 🔒' if status.get('stealth_mode') else 'No'}")
    peers = status.get("peers", {})
    print(f"  Peers:      {peers.get('available', 0)}/{peers.get('total', 0)} available")
    queries = status.get("queries", {})
    print(f"  Queries:    {queries.get('total', 0)} ({queries.get('rate', 0):.1f}% success)")
    memory = status.get("memory", {})
    print(f"  Memory:     {memory.get('active_entries', 0)}/{memory.get('total_entries', 0)} entries")
    models = status.get("local_models", [])
    if models:
        print(f"  Models:     {', '.join(models[:5])}")


def cmd_peers(args):
    """List connected peers."""
    client = _load_config_and_client(args.node, args.host, args.port, args.secret)
    peers = client.peers()
    if isinstance(peers, dict) and "error" in peers:
        print(f"❌ {peers['error']}")
        sys.exit(1)
    if not peers:
        print("No peers connected.")
        return

    print("🌐 Connected Peers:")
    print("─" * 50)
    for p in peers:
        name = p.get("name", "?")
        host = p.get("host", "?")
        port = p.get("port", "?")
        models = p.get("models", [])
        latency = p.get("latency_ms", "?")
        status_icon = "✅" if p.get("available") else "❌"
        print(f"  {status_icon} {name} ({host}:{port}) {latency}ms")
        if models:
            print(f"     Models: {', '.join(models[:4])}")


def cmd_share(args):
    """Share a model with the public mesh."""
    client = _load_config_and_client(args.node, args.host, args.port, args.secret)
    result = client._request(f"/api/models/{args.model}/share", method="POST")
    if "error" in result:
        print(f"❌ {result['error']}")
        sys.exit(1)
    print(f"✅ Model '{args.model}' is now shared with the public mesh.")


def cmd_unshare(args):
    """Stop sharing a model with the public mesh."""
    client = _load_config_and_client(args.node, args.host, args.port, args.secret)
    result = client._request(f"/api/models/{args.model}/unshare", method="POST")
    if "error" in result:
        print(f"❌ {result['error']}")
        sys.exit(1)
    print(f"✅ Model '{args.model}' is no longer shared.")


def cmd_shared(args):
    """List models currently shared with the public mesh."""
    client = _load_config_and_client(args.node, args.host, args.port, args.secret)
    result = client._request("/api/models")
    if "error" in result:
        print(f"❌ {result['error']}")
        sys.exit(1)

    shared = [m for m in result if isinstance(m, dict) and m.get("shared")]
    if not shared:
        print("No models currently shared with the mesh.")
        return

    print("🌐 Shared Models:")
    print("─" * 40)
    for m in shared:
        name = m.get("name", "?")
        size = m.get("size_mb", "?")
        print(f"  🟢 {name} ({size} MB)")


def cmd_download(args):
    """Download a model from the mesh."""
    client = _load_config_and_client(args.node, args.host, args.port, args.secret)
    result = client._request(f"/api/models/{args.model}/download", method="POST")
    if "error" in result:
        print(f"❌ {result['error']}")
        sys.exit(1)
    print(f"⬇️  Downloading model '{args.model}' from the mesh...")
    # Poll for status
    import time as _t
    while True:
        status = client._request(f"/api/models/{args.model}/download/status")
        if isinstance(status, dict) and status.get("done"):
            print(f"✅ Model '{args.model}' downloaded successfully.")
            break
        elif isinstance(status, dict) and "error" in status:
            print(f"❌ Download failed: {status['error']}")
            sys.exit(1)
        progress = status.get("progress", "?") if isinstance(status, dict) else "?"
        print(f"   Progress: {progress}%...", end="\r")
        _t.sleep(2)


def cmd_mesh_join(args):
    """Join the public mesh."""
    client = _load_config_and_client(args.node, args.host, args.port, args.secret)
    data = {"tracker_url": args.tracker} if args.tracker else {}
    result = client._request("/api/network/mesh/join", data=data, method="POST")
    if "error" in result:
        print(f"❌ {result['error']}")
        sys.exit(1)
    print("✅ Joined the public mesh!")
    if result.get("tracker"):
        print(f"   Tracker: {result['tracker']}")
    if result.get("nodes"):
        print(f"   Discovered {result['nodes']} node(s)")


def cmd_mesh_leave(args):
    """Leave the public mesh."""
    client = _load_config_and_client(args.node, args.host, args.port, args.secret)
    result = client._request("/api/network/mesh/leave", method="POST")
    if "error" in result:
        print(f"❌ {result['error']}")
        sys.exit(1)
    print("✅ Left the public mesh.")


def cmd_mesh_status(args):
    """Show public mesh status."""
    client = _load_config_and_client(args.node, args.host, args.port, args.secret)
    result = client._request("/api/network/mesh/nodes")
    if "error" in result:
        print(f"❌ {result['error']}")
        sys.exit(1)

    if not result or (isinstance(result, list) and len(result) == 0):
        print("No mesh nodes discovered.")
        return

    nodes = result if isinstance(result, list) else result.get("nodes", [])
    print(f"🌐 Public Mesh — {len(nodes)} node(s)")
    print("─" * 50)
    for n in nodes:
        name = n.get("node_id", n.get("name", "?"))[:16]
        caps = n.get("capabilities", {})
        models = n.get("models", caps.get("models", []))
        latency = n.get("latency_ms", "?")
        score = n.get("score", "?")
        print(f"  🟢 {name}")
        if models:
            print(f"     Models: {', '.join(models[:3])}")
        print(f"     Latency: {latency}ms | Score: {score}")


def cmd_conversations(args):
    """List or inspect conversations."""
    client = _load_config_and_client(args.node, args.host, args.port, args.secret)

    if args.id:
        # Get specific conversation
        result = client._request(f"/api/conversations/{args.id}")
        if "error" in result:
            print(f"❌ {result['error']}")
            sys.exit(1)

        if args.export:
            export_result = client._request(f"/api/conversations/{args.id}/export", method="POST")
            if "error" in export_result:
                print(f"❌ Export failed: {export_result['error']}")
                sys.exit(1)
            print(export_result.get("content", json.dumps(export_result, indent=2)))
            return

        # Show conversation details
        messages = result.get("messages", [])
        print(f"💬 Conversation: {args.id}")
        print("─" * 50)
        for msg in messages:
            role = msg.get("role", "?")
            content = msg.get("content", "")[:200]
            icon = "🧑" if role == "user" else "🤖"
            print(f"  {icon} {content}")
            print()
    else:
        # List conversations
        result = client._request("/api/conversations")
        if "error" in result:
            print(f"❌ {result['error']}")
            sys.exit(1)

        conversations = result if isinstance(result, list) else result.get("conversations", [])
        if not conversations:
            print("No conversations yet.")
            return

        print(f"💬 Conversations ({len(conversations)}):")
        print("─" * 50)
        for conv in conversations:
            conv_id = conv.get("id", "?")
            created = conv.get("created", "?")
            metadata = conv.get("metadata", {})
            model = metadata.get("model", "?")
            tags = metadata.get("tags", [])
            msg_count = len(conv.get("messages", []))
            tag_str = f" [{', '.join(tags)}]" if tags else ""
            print(f"  📝 {conv_id}  ({msg_count} msgs, {model}){tag_str}")


def cmd_install_service(args):
    """Install PinkyBrain as a systemd service."""
    service_content = """[Unit]
Description=PinkyBrain P2P AI Network
After=network.target ollama.service
Wants=ollama.service

[Service]
Type=simple
User={user}
Group={user}
WorkingDirectory={workdir}
ExecStart={python} {server} {node}
Restart=always
RestartSec=5
Environment=OLLAMA_HOST=127.0.0.1:11434

[Install]
WantedBy=multi-user.target
""".format(
        user=os.environ.get("USER", "pinkybrain"),
        workdir=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        python=sys.executable,
        server=os.path.abspath(os.path.join(os.path.dirname(__file__), "pinkybrain_v5.py")),
        node=args.node,
    )

    print("📝 Service file content:")
    print(service_content)
    print()
    print("To install, run:")
    print(f"  sudo tee /etc/systemd/system/pinkybrain.service << 'EOF'\n{service_content}EOF")
    print("  sudo systemctl daemon-reload")
    print("  sudo systemctl enable pinkybrain")
    print("  sudo systemctl start pinkybrain")


def cmd_uninstall_service(args):
    """Uninstall PinkyBrain systemd service."""
    print("To uninstall the service, run:")
    print("  sudo systemctl stop pinkybrain")
    print("  sudo systemctl disable pinkybrain")
    print("  sudo rm /etc/systemd/system/pinkybrain.service")
    print("  sudo systemctl daemon-reload")


# ============================================================================
# MAIN
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="PinkyBrain CLI — P2P Distributed AI Network",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Modes:
  pinkybrain serve              Start headless service
  pinkybrain app                Start application (opens browser)
  pinkybrain sidekick           Start system tray sidekick
  pinkybrain chat               Interactive terminal chat (REPL)
  pinkybrain ask "question"     Single query

Models:
  pinkybrain share <model>      Share a model with the mesh
  pinkybrain unshare <model>    Stop sharing a model
  pinkybrain shared             List shared models
  pinkybrain download <model>   Download a model from the mesh

Mesh:
  pinkybrain mesh join          Join the public mesh
  pinkybrain mesh leave         Leave the public mesh
  pinkybrain mesh status        Show mesh status

Conversations:
  pinkybrain conversations           List conversations
  pinkybrain conversations <id>      Show a conversation
  pinkybrain conversations <id> export  Export a conversation

Service:
  pinkybrain status              Show node status
  pinkybrain peers               List connected peers
  pinkybrain install-service     Install as systemd service
  pinkybrain uninstall-service   Uninstall systemd service
"""
    )

    # Global options
    parser.add_argument("--host", default=DEFAULT_HOST, help="PinkyBrain host (default: %(default)s)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="PinkyBrain port (default: %(default)s)")
    parser.add_argument("--secret", help="P2P secret for auth")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # --- serve ---
    p_serve = subparsers.add_parser("serve", help="Start as headless service")
    p_serve.add_argument("node", nargs="?", default="bug", help="Node name (default: bug)")
    p_serve.add_argument("--daemon", action="store_true", help="Run in background")
    p_serve.set_defaults(func=cmd_serve)

    # --- app ---
    p_app = subparsers.add_parser("app", help="Start application (opens browser)")
    p_app.add_argument("node", nargs="?", default="bug", help="Node name (default: bug)")
    p_app.add_argument("--native", action="store_true", help="Use native window (pywebview)")
    p_app.add_argument("--no-open", action="store_true", help="Don't open browser")
    p_app.set_defaults(func=cmd_app)

    # --- sidekick ---
    p_sidekick = subparsers.add_parser("sidekick", help="Start system tray sidekick")
    p_sidekick.add_argument("node", nargs="?", default="bug", help="Node name (default: bug)")
    p_sidekick.add_argument("--install", action="store_true", help="Install sidekick as autostart")
    p_sidekick.add_argument("--uninstall", action="store_true", help="Uninstall sidekick autostart")
    p_sidekick.set_defaults(func=cmd_sidekick)

    # --- chat ---
    p_chat = subparsers.add_parser("chat", help="Interactive terminal chat (REPL)")
    p_chat.add_argument("node", nargs="?", default="bug", help="Node name (default: bug)")
    p_chat.add_argument("--model", "-m", help="Default model to use")
    p_chat.set_defaults(func=cmd_chat)

    # --- ask ---
    p_ask = subparsers.add_parser("ask", help="Send a single query")
    p_ask.add_argument("question", help="Question to ask")
    p_ask.add_argument("--model", "-m", help="Model to use")
    p_ask.add_argument("--ensemble", action="store_true", help="Use ensemble consensus")
    p_ask.set_defaults(func=cmd_ask)

    # --- status ---
    p_status = subparsers.add_parser("status", help="Show node status")
    p_status.add_argument("node", nargs="?", default="bug", help="Node name (default: bug)")
    p_status.set_defaults(func=cmd_status)

    # --- peers ---
    p_peers = subparsers.add_parser("peers", help="List connected peers")
    p_peers.add_argument("node", nargs="?", default="bug", help="Node name (default: bug)")
    p_peers.set_defaults(func=cmd_peers)

    # --- share ---
    p_share = subparsers.add_parser("share", help="Share a model with the mesh")
    p_share.add_argument("model", help="Model name to share")
    p_share.set_defaults(func=cmd_share)

    # --- unshare ---
    p_unshare = subparsers.add_parser("unshare", help="Stop sharing a model")
    p_unshare.add_argument("model", help="Model name to unshare")
    p_unshare.set_defaults(func=cmd_unshare)

    # --- shared ---
    p_shared = subparsers.add_parser("shared", help="List shared models")
    p_shared.set_defaults(func=cmd_shared)

    # --- download ---
    p_download = subparsers.add_parser("download", help="Download a model from the mesh")
    p_download.add_argument("model", help="Model name to download")
    p_download.set_defaults(func=cmd_download)

    # --- mesh subcommands ---
    p_mesh = subparsers.add_parser("mesh", help="Public mesh commands")
    mesh_sub = p_mesh.add_subparsers(dest="mesh_command", help="Mesh subcommand")

    p_mesh_join = mesh_sub.add_parser("join", help="Join the public mesh")
    p_mesh_join.add_argument("--tracker", help="Tracker URL")
    p_mesh_join.set_defaults(func=cmd_mesh_join)

    p_mesh_leave = mesh_sub.add_parser("leave", help="Leave the public mesh")
    p_mesh_leave.set_defaults(func=cmd_mesh_leave)

    p_mesh_status = mesh_sub.add_parser("status", help="Show mesh status")
    p_mesh_status.set_defaults(func=cmd_mesh_status)

    # --- conversations ---
    p_conv = subparsers.add_parser("conversations", help="List or inspect conversations")
    p_conv.add_argument("id", nargs="?", default=None, help="Conversation ID")
    p_conv.add_argument("--export", action="store_true", help="Export conversation")
    p_conv.set_defaults(func=cmd_conversations)

    # --- install-service ---
    p_install = subparsers.add_parser("install-service", help="Install as systemd service")
    p_install.add_argument("node", nargs="?", default="bug", help="Node name (default: bug)")
    p_install.set_defaults(func=cmd_install_service)

    # --- uninstall-service ---
    p_uninstall = subparsers.add_parser("uninstall-service", help="Uninstall systemd service")
    p_uninstall.set_defaults(func=cmd_uninstall_service)

    # --- Legacy positional args for backward compat ---
    parser.add_argument("legacy_node", nargs="?", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--query", "-q", help="Single query (legacy mode)")
    parser.add_argument("--model-legacy", "-m", dest="model_legacy", help=argparse.SUPPRESS)
    parser.add_argument("--ensemble", action="store_true", help=argparse.SUPPRESS)

    args = parser.parse_args()

    # If a subcommand was given, run it
    if hasattr(args, "func") and args.func:
        # For subcommands that need node, inject --host/--port/--secret
        args.host = args.host if hasattr(args, 'host') else DEFAULT_HOST
        args.port = args.port if hasattr(args, 'port') else DEFAULT_PORT
        args.secret = args.secret if hasattr(args, 'secret') else None
        args.func(args)
        return

    # Legacy fallback: no subcommand
    node = args.legacy_node or "bug"
    client = _load_config_and_client(node, args.host, args.port, args.secret)

    if args.query:
        model = args.model_legacy
        strategy = "ensemble" if args.ensemble else "auto"
        result = client.query(args.query, model=model, strategy=strategy)
        if "error" in result:
            print(f"❌ {result['error']}")
            sys.exit(1)
        print(result.get("response", ""))
        sys.exit(0)

    # Default: interactive chat
    shell = PinkyBrainShell(client)
    if args.model_legacy:
        shell.default_model = args.model_legacy
    shell.run()


if __name__ == "__main__":
    main()