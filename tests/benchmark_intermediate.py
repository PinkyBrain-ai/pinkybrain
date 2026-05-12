#!/usr/bin/env python3
"""
🧪 BENCHMARK INTERMÉDIAIRE - Niveau réaliste pour SmolLM2, phi3, qwen3
Questions que les modèles peuvent réellement répondre
"""

import asyncio
import time
import json
from datetime import datetime
from typing import List
from dataclasses import dataclass
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.pinkybrain_v5 import PinkyBrain

# Questions de niveau intermédiaire (réalisables par nos modèles)
INTERMEDIATE_QUERIES = [
    # 🧮 Mathématiques de base
    "Calcule 47 × 38 et explique le résultat.",
    "Qu'est-ce qu'un nombre premier ? Donne un exemple.",
    "Explique la différence entre pourcentage et fraction.",

    # 🔬 Sciences
    "Qu'est-ce que la photosynthèse ?",
    "Explique le cycle de l'eau simplement.",
    "Quelle est la différence entre une étoile et une planète ?",

    # 📚 Histoire et Culture
    "Qu'est-ce que la Révolution française ?",
    "Explique qui était Albert Einstein.",
    "Qu'est-ce que la Renaissance ?",

    # 🧠 Raisonnement
    "Si tu as 3 pommes et que tu en donnes 2, combien en reste-t-il ?",
    "Qu'est-ce qui pèse plus : un kilo de plume ou un kilo de plomb ?",
    "Explique pourquoi le ciel est bleu.",

    # 💻 Informatique
    "Qu'est-ce qu'un algorithme ?",
    "Explique la différence entre hardware et software.",
    "Qu'est-ce que l'internet ?",

    # 🎯 Problèmes pratiques
    "Comment faire un œuf à la coque ?",
    "Quelle est la capitale de la Belgique ?",
    "Explique comment planter une graine.",
]

# Modèles disponibles
MODELS = ["SmolLM2:1.7b", "phi3:mini", "qwen3:8b"]

@dataclass
class IntermediateResult:
    query: str
    model: str
    success: bool
    latency: float
    response_length: int
    response: str
    error: str = None

class IntermediateBenchmark:
    def __init__(self):
        self.results = []
        self.start_time = None
        self.end_time = None

    async def run_benchmark(self):
        print("=" * 70)
        print("🧪 BENCHMARK INTERMÉDIAIRE - Épreuve Réaliste")
        print("=" * 70)
        print(f"\n📋 Configuration:")
        print(f"   Questions: {len(INTERMEDIATE_QUERIES)}")
        print(f"   Modèles: {len(MODELS)}")
        print(f"   Total tests: {len(INTERMEDIATE_QUERIES) * len(MODELS)}")

        self.start_time = datetime.utcnow()

        for model in MODELS:
            print(f"\n🤖 Testing model: {model}")

            # Créer PinkyBrain avec le modèle
            pinkybrain_bug = PinkyBrain()
            pinkybrain_bug.model = model
            await pinkybrain_bug.initialize()

            for i, query in enumerate(INTERMEDIATE_QUERIES):
                print(f"\n   [{i+1}/{len(INTERMEDIATE_QUERIES)}] {query[:50]}...")

                start = time.time()

                try:
                    result = await pinkybrain_bug.query(query)
                    latency = (time.time() - start) * 1000

                    response = result.get("response", "")

                    if len(response) > 0:
                        print(f"      ✅ ({latency:.0f}ms) - {len(response)} chars")
                        print(f"      {response[:150]}...")
                    else:
                        print(f"      ⚠️ ({latency:.0f}ms) - Réponse vide")

                    self.results.append(IntermediateResult(
                        query=query,
                        model=model,
                        success=result.get("status") == "success",
                        latency=latency,
                        response_length=len(response),
                        response=response,
                        error=result.get("error")
                    ))

                except Exception as e:
                    latency = (time.time() - start) * 1000
                    print(f"      ❌ ({latency:.0f}ms) - {e}")

                    self.results.append(IntermediateResult(
                        query=query,
                        model=model,
                        success=False,
                        latency=latency,
                        response_length=0,
                        response="",
                        error=str(e)
                    ))

        self.end_time = datetime.utcnow()

        self.print_stats()

    def print_stats(self):
        print("\n" + "=" * 70)
        print("📊 RÉSULTATS DU BENCHMARK INTERMÉDIAIRE")
        print("=" * 70)

        duration = (self.end_time - self.start_time).total_seconds()
        successful = [r for r in self.results if r.success]

        print(f"\n⏱️ Durée: {duration:.1f}s")
        print(f"\n📈 Statistiques globales:")
        print(f"   Total: {len(self.results)}")
        print(f"   ✅ Succès: {len(successful)}")
        print(f"   📊 Success rate: {len(successful) / len(self.results):.2%}")

        # Stats par modèle
        print(f"\n🤖 Stats par modèle:")
        for model in MODELS:
            model_results = [r for r in self.results if r.model == model]
            model_success = [r for r in model_results if r.success]
            model_with_answers = [r for r in model_success if r.response_length > 0]

            print(f"\n   {model}:")
            print(f"     Succès technique: {len(model_success)}/{len(model_results)}")
            print(f"     Avec réponses: {len(model_with_answers)}/{len(model_success)}")

            if model_with_answers:
                latencies = [r.latency for r in model_with_answers]
                lengths = [r.response_length for r in model_with_answers]

                print(f"     Latence moy: {sum(latencies) / len(latencies):.1f}ms")
                print(f"     Longueur moy: {sum(lengths) / len(lengths):.0f} chars")
            else:
                print(f"     ⚠️ Aucune réponse significative")

        # Qualité globale
        all_with_answers = [r for r in successful if r.response_length > 0]
        if all_with_answers:
            avg_length = sum(r.response_length for r in all_with_answers) / len(all_with_answers)
            print(f"\n🎯 Qualité globale:")
            print(f"   Total avec réponses: {len(all_with_answers)}")
            print(f"   Longueur moyenne: {avg_length:.0f} chars")

            if avg_length > 100:
                print(f"   ✅ Réponses substantielles")
            elif avg_length > 20:
                print(f"   ⚠️ Réponses courtes mais présentes")
            else:
                print(f"   ❌ Réponses très courtes")

        # Meilleures réponses
        print(f"\n📝 Meilleures réponses:")
        top_responses = sorted(all_with_answers, key=lambda r: r.response_length, reverse=True)[:5]

        for i, r in enumerate(top_responses, 1):
            print(f"\n   {i}. {r.model}")
            print(f"      Query: {r.query}")
            print(f"      Length: {r.response_length} chars ({r.latency:.0f}ms)")
            print(f"      Response: {r.response[:200]}...")

async def main():
    print("=" * 70)
    print("🧪 BENCHMARK INTERMÉDIAIRE - ÉPREUVE RÉALISTE")
    print("=" * 70)

    os.makedirs("output", exist_ok=True)

    benchmark = IntermediateBenchmark()
    await benchmark.run_benchmark()

    print("\n" + "=" * 70)
    print("✅ BENCHMARK TERMINÉ !")
    print("=" * 70)

if __name__ == '__main__':
    asyncio.run(main())