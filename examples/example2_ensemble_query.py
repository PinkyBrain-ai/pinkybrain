#!/usr/bin/env python3
"""
Exemple 2: PinkyBrain Ensemble Query
"""

import asyncio
import sys
import os

# Ajouter le chemin
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.pinkybrain_v3_final import PinkyBrain, Peer


async def main():
    """Exemple ensemble"""

    print("=" * 70)
    print("EXEMPLE 2: PinkyBrain - Requête Ensemble (Multi-modèles)")
    print("=" * 70)

    # Créer PinkyBrain
    pinkybrain = PinkyBrain()

    # Ajouter plusieurs peers
    peer1 = Peer(
        name="Peer1",
        host="127.0.0.1",
        port=11434,
        models=["SmolLM2:1.7b"]
    )

    peer2 = Peer(
        name="Peer2",
        host="127.0.0.1",
        port=11434,
        models=["phi3:mini"]
    )

    peer3 = Peer(
        name="Peer3",
        host="127.0.0.1",
        port=11434,
        models=["TinyLlama:latest"]
    )

    await pinkybrain.add_peer(peer1)
    await pinkybrain.add_peer(peer2)
    await pinkybrain.add_peer(peer3)

    # Initialiser
    print("\n⚙️ Initialisation...")
    await pinkybrain.initialize()

    # Faire une requête avec ensemble
    print("\n📝 Requête: 'Explique le concept de réseau P2P'")
    print("🎯 Mode: Ensemble (consensus multi-modèles)")

    result = await pinkybrain.query(
        "Explique le concept de réseau P2P",
        use_ensemble=True
    )

    if result["status"] == "success":
        print(f"\n✅ Succès !")
        print(f"   Peer final: {result['peer']}")
        print(f"   Model final: {result['model']}")
        print(f"   Latence: {result['latency']:.0f}ms")

        if "consensus" in result:
            print(f"\n📊 Consensus:")
            print(f"   Votes: {len(result['consensus']['votes'])}")
            print(f"   Confiance: {result['consensus']['confidence']:.2f}")

        print(f"\n💬 Réponse:\n{result['response']}")
    else:
        print(f"\n❌ Erreur: {result}")

    # Exporter l'historique
    print("\n💾 Export de l'historique...")
    pinkybrain.query_history.export("csv", "../output/history.csv")
    print("✅ Historique exporté vers output/history.csv")


if __name__ == '__main__':
    asyncio.run(main())