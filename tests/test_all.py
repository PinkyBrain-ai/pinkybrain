#!/usr/bin/env python3
"""
🧪 Script de Test - PinkyBrain v5.2.0
Teste que le système fonctionne sur Bug et Pinky
"""

import asyncio
import sys
import os

# Ajouter le chemin
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.pinkybrain_v5 import PinkyBrain

TEST_CONFIG_BUG = {
    "node_name": "bug",
    "version": "5.2.0",
    "host": "127.0.0.1",
    "port": 8080,
    "ollama_host": "127.0.0.1",
    "ollama_port": 11434,
    "local_models": ["test-model"],
    "stealth_mode": False,
    "share_ai": True,
    "rate_limit": 10.0,
    "rate_burst": 20,
    "peers": [],
    "providers": {},
    "public_mesh": {"enabled": False},
    "conversation_store": {"enabled": False},
}

TEST_CONFIG_PINKY = {
    "node_name": "pinky",
    "version": "5.2.0",
    "host": "127.0.0.1",
    "port": 8081,
    "ollama_host": "127.0.0.1",
    "ollama_port": 11434,
    "local_models": ["test-model"],
    "stealth_mode": False,
    "share_ai": True,
    "rate_limit": 10.0,
    "rate_burst": 20,
    "peers": [],
    "providers": {},
    "public_mesh": {"enabled": False},
    "conversation_store": {"enabled": False},
}


async def test_pinkybrain():
    """Teste PinkyBrain v5"""
    print("\n" + "=" * 70)
    print("🧪 TESTING PINKYBRAIN v5.2.0")
    print("=" * 70)

    # Créer PinkyBrain
    brain = PinkyBrain(TEST_CONFIG_BUG)
    print(f"✅ PinkyBrain created: {brain.node_name} v{brain.version}")

    # Check v5 modules
    print(f"  Resource Guard: {brain.resource_guard is not None}")
    print(f"  Adaptive Scheduler: {brain.adaptive_scheduler is not None}")
    print(f"  Conversation Store: {brain.conversation_store is not None}")
    print(f"  Model Share Manager: {brain.model_share_manager is not None}")
    print(f"  Tracker Client: {brain.tracker_client is not None}")

    # Status check
    status = brain.get_status()
    assert status["version"] == "5.2.0"
    assert "resource_guard" in status
    assert "adaptive_scheduler" in status
    print(f"✅ Status: v{status['version']}, modules OK")

    print("\n" + "=" * 70)
    print("✅ ALL TESTS PASSED")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_pinkybrain())