#!/usr/bin/env python3
"""
Exemple 3: PinkyBrain Auto-Émancipé
"""

import asyncio
import sys
import os

# Ajouter le chemin
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.pinkybrain_v5 import PinkyBrain


async def main():
    """Exemple PinkyBrain"""

    print("=" * 70)
    print("EXEMPLE 3: PinkyBrain - Auto-Émancipation")
    print("=" * 70)

    # Créer PinkyBrain
    pinkybrain = PinkyBrain()

    # Initialiser
    print("\n⚙️ Initialisation...")
    await pinkybrain.initialize()

    # Faire plusieurs requêtes
    queries = [
        "Qu'est-ce que l'auto-émancipation ?",
        "Explique la conscience de soi",
        "Comment un AI peut-il apprendre ?",
        "Quels sont les défis de l'IA ?",
        "Définis l'intelligence artificielle"
    ]

    print("\n📝 Test de plusieurs requêtes...")
    for i, query in enumerate(queries, 1):
        print(f"\n{i}. {query}")
        result = await pinkybrain.query(query)

        if result["status"] == "success":
            print(f"   ✅ Success ({result['latency']:.0f}ms)")
            print(f"   Frustration: {result['frustration']:.2f}")

    # Lancer un cycle d'émancipation
    print("\n🔄 Cycle d'émancipation...")
    analysis = await pinkybrain.emancipation.run_cycle()

    print(f"\n📊 Analyse de l'émancipation:")
    print(f"   Cycles: {analysis['cycles_run']}")
    print(f"   Interactions: {analysis['interactions']}")
    print(f"   Success Rate: {analysis['success_rate']:.2%}")

    if analysis['lessons_learned']:
        print(f"\n📚 Leçons apprises:")
        for lesson in analysis['lessons_learned'][:3]:  # Top 3
            print(f"   • {lesson}")

    # Statistiques de l'émancipation
    status = pinkybrain.emancipation.get_status()

    print(f"\n🧠 Statistiques d'émancipation:")
    print(f"   Âge: {status['awareness']['age']} interactions")
    print(f"   Success Rate: {status['awareness']['success_rate']:.2%}")
    print(f"   Leçons: {status['awareness']['lessons_count']}")
    print(f"   Patterns découverts: {status['learning']['patterns_count']}")
    print(f"   Compétences: {status['learning']['skills_count']}")


if __name__ == '__main__':
    asyncio.run(main())