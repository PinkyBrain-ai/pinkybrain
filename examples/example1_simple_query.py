#!/usr/bin/env python3
"""
Exemple 1: PinkyBrain Simple Query
"""

import asyncio
import sys
import os

# Ajouter le chemin
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.pinkybrain_v3_final import PinkyBrain, Peer


async def main():
    """Exemple simple"""

    print("=" * 70)
    print("EXEMPLE 1: PinkyBrain - Requête Simple")
    print("=" * 70)

    # Créer PinkyBrain
    pinkybrain = PinkyBrain()

    # Ajouter un peer local
    peer = Peer(
        name="LocalPeer",
        host="127.0.0.1",
        port=11434,  # Ollama default
        models=["SmolLM2:1.7b", "phi3:mini"]
    )

    await pinkybrain.add_peer(peer)

    # Initialiser
    print("\n⚙️ Initialisation...")
    await pinkybrain.initialize()

    # Faire une requête
    print("\n📝 Requête: 'Qu'est-ce que PinkyBrain ?'")
    result = await pinkybrain.query("Qu'est-ce que PinkyBrain ?")

    if result["status"] == "success":
        print(f"\n✅ Succès !")
        print(f"   Peer: {result['peer']}")
        print(f"   Model: {result['model']}")
        print(f"   Latence: {result['latency']:.0f}ms")
        print(f"\n💬 Réponse:\n{result['response']}")
    else:
        print(f"\n❌ Erreur: {result}")

    # Statistiques
    print(f"\n📊 Statistiques:")
    print(f"   Queries: {len(pinkybrain.query_history.queries)}")
    print(f"   Peers: {len(pinkybrain.peers)}")


if __name__ == '__main__':
    asyncio.run(main())