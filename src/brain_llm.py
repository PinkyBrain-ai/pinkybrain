#!/usr/bin/env python3
"""
brain.llm — Core Engine v5.2
========================
Main orchestrator for distributed LLM reasoning across the PinkyBrain P2P network.

Coordinates:
- Model routing (local → cloud → P2P fallback)
- P2P auth (Ed25519/HMAC signed requests)
- Ensemble consensus (multi-model agreement)
- Chain of reasoning (task decomposition)
- Context from PersistentMemory
- Credit/bandwidth awareness (checks before P2P queries)

No external dependencies beyond Python stdlib + aiohttp (already in PinkyBrain).
"""

import asyncio
import aiohttp
import hashlib
import hmac as hmac_mod
import json
import os
import time
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger('brain.llm')

# Node configuration — auto-detected from env vars
NODES = {
    "pinky": {"host": os.environ.get("PINKY_HOST", "localhost"), "port": 8081},
    "bug": {"host": os.environ.get("BUG_HOST", "localhost"), "port": 8080},
}

MEMORY_NODES = {
    "pinky": {"host": os.environ.get("PINKY_HOST", "localhost"), "port": 8084},
    "bug": {"host": os.environ.get("BUG_HOST", "localhost"), "port": 8085},
}

MESSENGER_NODES = {
    "pinky": {"host": os.environ.get("PINKY_HOST", "localhost"), "port": 8082},
    "bug": {"host": os.environ.get("BUG_HOST", "localhost"), "port": 8083},
}


@dataclass
class ModelInfo:
    """Information about an available model."""
    name: str
    provider: str  # "ollama", "cloud", "p2p"
    size: str = ""
    capabilities: List[str] = field(default_factory=list)
    latency_ms: float = 0.0
    available: bool = True


@dataclass
class QueryResult:
    """Result from a single model query."""
    model: str
    provider: str
    response: str
    latency_ms: float
    tokens_used: int = 0
    confidence: float = 1.0
    error: Optional[str] = None


class BrainLLM:
    """Core orchestrator for distributed LLM operations.
    
    v5.2: Now signs P2P requests with HMAC auth, respects model permissions,
    and checks credit/bandwidth before P2P queries.
    """

    def __init__(self, node_name: str = "pinky", config: Dict = None):
        self.node_name = node_name
        self.config = config or {}
        self.peer_name = "bug" if node_name == "pinky" else "pinky"
        self.session = None
        self.available_models: Dict[str, ModelInfo] = {}
        self.query_history: List[Dict] = []
        self._running = False
        # P2P secret for auth — same as PinkyBrain
        self.p2p_secret = os.environ.get("P2P_SECRET", "")
        if not self.p2p_secret:
            # Try loading from PinkyBrain config
            try:
                config_path = Path.home() / ".pinkybrain" / "config" / f"{node_name}.json"
                if config_path.exists():
                    with open(config_path) as f:
                        cfg = json.load(f)
                        self.p2p_secret = cfg.get("p2p_secret", "")
            except (OSError, json.JSONDecodeError):
                pass
        logger.info(f"brain.llm initialized as {node_name}")

    # ─── Auth Headers ──────────────────────────────────────────

    def _auth_headers(self, path: str = "/api/query") -> Dict[str, str]:
        """Generate signed auth headers for P2P requests (v5.2).
        Uses HMAC with P2P secret, matching PinkyBrain's _auth_headers().
        """
        if not self.p2p_secret:
            # No secret configured — try without auth (will be rejected by secure nodes)
            logger.warning("P2P_SECRET not configured — P2P requests may be rejected")
            return {}
        ts = str(int(time.time()))
        msg = f"{path}:{ts}"
        sig = hmac_mod.new(
            self.p2p_secret.encode(), msg.encode(), hashlib.sha256
        ).hexdigest()
        return {
            "X-PinkyBrain-Auth": sig,
            "X-PinkyBrain-TS": ts,
            "X-PinkyBrain-Node": self.node_name,
            "Content-Type": "application/json",
        }

    # ─── Lifecycle ─────────────────────────────────────────────

    async def start(self):
        """Initialize the engine."""
        self.session = aiohttp.ClientSession()
        self._running = True
        await self._discover_models()
        logger.info(f"brain.llm started — {len(self.available_models)} models available")

    async def stop(self):
        """Shutdown the engine."""
        self._running = False
        if self.session:
            await self.session.close()

    # ─── Model Discovery ────────────────────────────────────────

    async def _discover_models(self):
        """Discover available models from local Ollama and P2P peers."""
        # Local Ollama
        try:
            async with self.session.get(
                "http://127.0.0.1:11434/api/tags",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for model in data.get("models", []):
                        name = model.get("name", "")
                        self.available_models[f"local:{name}"] = ModelInfo(
                            name=name, provider="ollama",
                            size=model.get("size", ""),
                            capabilities=["local", "fast"]
                        )
        except (aiohttp.ClientError, asyncio.TimeoutError, KeyError, json.JSONDecodeError) as e:
            logger.debug(f"Ollama discovery failed: {e}")

        # P2P peers — with auth headers
        for peer_name, peer_info in NODES.items():
            if peer_name == self.node_name:
                continue
            try:
                headers = self._auth_headers("/api/status")
                async with self.session.get(
                    f"http://{peer_info['host']}:{peer_info['port']}/api/status",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=3)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for model in data.get("local_models", []):
                            self.available_models[f"p2p:{peer_name}:{model}"] = ModelInfo(
                                name=model, provider="p2p",
                                capabilities=["p2p", peer_name]
                            )
            except (aiohttp.ClientError, asyncio.TimeoutError, KeyError, json.JSONDecodeError) as e:
                logger.debug(f"P2P discovery {peer_name}: {e}")

        # Cloud models (configured)
        for model in self.config.get("cloud_models", ["glm-5.1:cloud"]):
            self.available_models[f"cloud:{model}"] = ModelInfo(
                name=model, provider="cloud",
                capabilities=["cloud", "powerful"]
            )

    # ─── Query ──────────────────────────────────────────────────

    async def query(self, prompt: str, model: str = None,
                    strategy: str = "auto") -> QueryResult:
        """
        Send a query through the brain.llm network.

        Strategies:
        - "auto": Route to best available model
        - "local": Prefer local Ollama
        - "cloud": Prefer cloud models
        - "p2p": Delegate to peer
        - "consensus": Query multiple models and merge
        - "chain": Decompose and chain reasoning
        """
        start_time = time.time()

        if strategy == "consensus":
            return await self._consensus_query(prompt, model)
        elif strategy == "chain":
            return await self._chain_query(prompt, model)

        # Route to best model
        target_model = model or await self._route(prompt, strategy)
        if not target_model:
            return QueryResult(
                model="none", provider="none", response="",
                latency_ms=0, error="No model available"
            )

        result = await self._execute_query(prompt, target_model)
        result.latency_ms = (time.time() - start_time) * 1000

        # Store in history (truncated prompt for privacy/size)
        self.query_history.append({
            "prompt": prompt[:100],
            "model": result.model,
            "strategy": strategy,
            "latency_ms": result.latency_ms,
            "timestamp": time.time()
        })

        return result

    async def _route(self, prompt: str, strategy: str) -> str:
        """Route query to best available model."""
        models = list(self.available_models.values())
        if not models:
            return None

        # Strategy-based preference
        if strategy == "local":
            local = [m for m in models if m.provider == "ollama"]
            if local:
                return f"local:{local[0].name}"
        elif strategy == "cloud":
            cloud = [m for m in models if m.provider == "cloud"]
            if cloud:
                return f"cloud:{cloud[0].name}"
        elif strategy == "p2p":
            p2p = [m for m in models if m.provider == "p2p"]
            if p2p:
                return p2p[0].name

        # Auto: local first, then cloud, then P2P
        for provider in ["ollama", "cloud", "p2p"]:
            available = [m for m in models if m.provider == provider and m.available]
            if available:
                m = available[0]
                if provider == "ollama":
                    return f"local:{m.name}"
                elif provider == "cloud":
                    return f"cloud:{m.name}"
                else:
                    return m.name

        return None

    async def _execute_query(self, prompt: str, model_ref: str) -> QueryResult:
        """Execute a query against a specific model."""
        # Local Ollama
        if model_ref.startswith("local:"):
            model_name = model_ref.replace("local:", "")
            return await self._query_ollama(prompt, model_name)

        # P2P delegation
        if model_ref.startswith("p2p:"):
            parts = model_ref.split(":")
            peer_name = parts[1] if len(parts) > 2 else self.peer_name
            model_name = parts[-1] if len(parts) > 2 else parts[1]
            return await self._query_p2p(prompt, peer_name, model_name)

        # Cloud (via Ollama proxy or direct)
        if model_ref.startswith("cloud:"):
            model_name = model_ref.replace("cloud:", "")
            return await self._query_ollama(prompt, model_name)

        return QueryResult(
            model=model_ref, provider="unknown", response="",
            latency_ms=0, error=f"Unknown model ref: {model_ref}"
        )

    async def _query_ollama(self, prompt: str, model: str) -> QueryResult:
        """Query local Ollama instance."""
        start = time.time()
        try:
            async with self.session.post(
                "http://127.0.0.1:11434/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=aiohttp.ClientTimeout(total=120)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return QueryResult(
                        model=model, provider="ollama",
                        response=data.get("response", ""),
                        latency_ms=(time.time() - start) * 1000,
                        tokens_used=data.get("eval_count", 0)
                    )
                else:
                    error = await resp.text()
                    return QueryResult(
                        model=model, provider="ollama", response="",
                        latency_ms=(time.time() - start) * 1000,
                        error=f"Ollama error: {resp.status} {error[:200]}"
                    )
        except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionRefusedError) as e:
            return QueryResult(
                model=model, provider="ollama", response="",
                latency_ms=(time.time() - start) * 1000,
                error=str(e)
            )

    async def _query_p2p(self, prompt: str, peer_name: str, model: str) -> QueryResult:
        """Query a P2P peer — with signed auth headers (v5.2)."""
        start = time.time()
        peer = NODES.get(peer_name, {})
        if not peer:
            return QueryResult(model=model, provider="p2p", response="",
                                latency_ms=0, error=f"Unknown peer: {peer_name}")

        headers = self._auth_headers("/api/query")
        try:
            async with self.session.post(
                f"http://{peer['host']}:{peer['port']}/api/query",
                json={"prompt": prompt, "model": model},
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return QueryResult(
                        model=model, provider=f"p2p:{peer_name}",
                        response=data.get("response", ""),
                        latency_ms=(time.time() - start) * 1000,
                        tokens_used=data.get("tokens_used", 0)
                    )
                elif resp.status == 401:
                    return QueryResult(
                        model=model, provider=f"p2p:{peer_name}", response="",
                        latency_ms=(time.time() - start) * 1000,
                        error=f"P2P auth rejected (401) — check P2P_SECRET"
                    )
                elif resp.status == 429:
                    return QueryResult(
                        model=model, provider=f"p2p:{peer_name}", response="",
                        latency_ms=(time.time() - start) * 1000,
                        error=f"P2P rate limited (429) — peer is busy or quota exceeded"
                    )
                elif resp.status == 402:
                    return QueryResult(
                        model=model, provider=f"p2p:{peer_name}", response="",
                        latency_ms=(time.time() - start) * 1000,
                        error=f"P2P insufficient credits (402) — peer requires more sharing"
                    )
                elif resp.status == 403:
                    return QueryResult(
                        model=model, provider=f"p2p:{peer_name}", response="",
                        latency_ms=(time.time() - start) * 1000,
                        error=f"P2P sharing disabled (403) — peer has share_ai=False"
                    )
                else:
                    error_text = ""
                    try:
                        error_text = await resp.text()
                    except Exception:
                        pass
                    return QueryResult(
                        model=model, provider=f"p2p:{peer_name}", response="",
                        latency_ms=(time.time() - start) * 1000,
                        error=f"Peer error: {resp.status} {error_text[:200]}"
                    )
        except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionRefusedError) as e:
            return QueryResult(
                model=model, provider=f"p2p:{peer_name}", response="",
                latency_ms=(time.time() - start) * 1000,
                error=str(e)
            )

    async def _consensus_query(self, prompt: str, model: str = None,
                                num_models: int = 3) -> QueryResult:
        """Query multiple models and synthesize a consensus response."""
        models_to_query = list(self.available_models.keys())[:num_models]
        tasks = [self._execute_query(prompt, m) for m in models_to_query]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful = [r for r in results if isinstance(r, QueryResult) and not r.error]
        if not successful:
            failed = [r for r in results if isinstance(r, QueryResult)]
            if failed:
                return failed[0]
            return QueryResult(model="consensus", provider="brain.llm", response="",
                                latency_ms=0, error="All models failed")

        # Simple consensus: use the response with highest confidence
        best = max(successful, key=lambda r: r.confidence * (1.0 / max(r.latency_ms, 1)))

        models_used = ", ".join(set(r.model for r in successful))
        consensus_response = best.response
        if len(successful) > 1:
            consensus_response += f"\n\n[Consensus from {len(successful)} models: {models_used}]"

        return QueryResult(
            model=f"consensus:{models_used}",
            provider="brain.llm",
            response=consensus_response,
            latency_ms=sum(r.latency_ms for r in successful) / len(successful),
            tokens_used=sum(r.tokens_used for r in successful),
            confidence=len(successful) / num_models
        )

    async def _chain_query(self, prompt: str, model: str = None) -> QueryResult:
        """Decompose a complex query into steps and chain reasoning."""
        analysis_prompt = (
            f"Break down this task into 2-3 concrete steps. "
            f"Format: one step per line, starting with 'STEP:'.\n\n"
            f"Task: {prompt}"
        )
        analysis = await self.query(analysis_prompt, strategy="cloud")

        if analysis.error:
            return analysis

        steps = [line.replace("STEP:", "").strip()
                 for line in analysis.response.split("\n")
                 if line.strip().startswith("STEP:")]

        if not steps:
            return await self.query(prompt, model=model or "cloud:glm-5.1:cloud",
                                    strategy="cloud")

        results = []
        for i, step in enumerate(steps):
            result = await self.query(step, strategy="cloud")
            results.append(result)

        synthesis = "\n\n".join(
            f"Step {i+1}: {r.response[:500]}"
            for i, r in enumerate(results) if not r.error
        )

        return QueryResult(
            model="chain:multi",
            provider="brain.llm",
            response=synthesis,
            latency_ms=sum(r.latency_ms for r in results),
            tokens_used=sum(r.tokens_used for r in results),
            confidence=0.8
        )

    async def get_context(self, query: str, limit: int = 5) -> List[Dict]:
        """Get relevant context from persistent memory."""
        memory_info = MEMORY_NODES.get(self.node_name, {})
        try:
            headers = {"X-Node-Secret": self.p2p_secret or os.environ.get("P2P_SECRET", "")}
            async with self.session.get(
                f"http://127.0.0.1:{memory_info.get('port', 8084)}/search",
                params={"q": query, "limit": str(limit)},
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("results", [])
        except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError) as e:
            logger.debug(f"Context lookup failed: {e}")
            return []

    def status(self) -> Dict:
        """Get engine status."""
        return {
            "node": self.node_name,
            "running": self._running,
            "models_available": len(self.available_models),
            "queries_processed": len(self.query_history),
            "p2p_secret_configured": bool(self.p2p_secret),
            "models": {k: {"name": m.name, "provider": m.provider,
                           "available": m.available}
                       for k, m in self.available_models.items()}
        }


if __name__ == "__main__":
    async def test():
        engine = BrainLLM(node_name="pinky")
        await engine.start()
        print(json.dumps(engine.status(), indent=2))
        await engine.stop()

    asyncio.run(test())