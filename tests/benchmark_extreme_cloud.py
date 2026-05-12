#!/usr/bin/env python3
"""
🧪 BENCHMARK EXTREME v2 - Avec modèles cloud capables
Test avec glm-4.7:cloud et glm-5:cloud pour de vraies réponses
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

# 5 questions représentatives de niveau doctoral
EXTREME_QUERIES_SAMPLE = [
    "Démontrez le théorème d'incomplétude de Gödel et expliquez ses implications.",
    "Expliquez le problème P vs NP et pourquoi c'est important.",
    "Démontrez comment la relativité générale prédit la précession du périhélie de Mercure.",
    "Qu'est-ce que le problème de la conscience qualia selon Thomas Nagel ?",
    "Intégrez les concepts de relativité générale et mécanique quantique.",
]

CLOUD_MODELS = ["glm-4.7:cloud", "glm-5:cloud"]

@dataclass
class CloudResult:
    query: str
    model: str
    success: bool
    latency: float
    response_length: int
    response: str
    error: str = None

class CloudBenchmark:
    def __init__(self):
        self.results = []
        self.start_time = None
        self.end_time = None

    async def run_benchmark(self):
        print("=" * 70)
        print("🧪 BENCHMARK EXTREME v2 - Modèles Cloud")
        print("=" * 70)
        print(f"\n📋 Configuration:")
        print(f"   Questions: {len(EXTREME_QUERIES_SAMPLE)}")
        print(f"   Modèles: {len(CLOUD_MODELS)}")
        print(f"   Total tests: {len(EXTREME_QUERIES_SAMPLE) * len(CLOUD_MODELS)}")

        # Créer PinkyBrain
        pinkybrain_bug = PinkyBrain()
        pinkybrain_bug.model = "glm-4.7:cloud"  # Forcer le modèle cloud
        await pinkybrain_bug.initialize()

        self.start_time = datetime.utcnow()

        for model in CLOUD_MODELS:
            print(f"\n🤖 Testing model: {model}")

            # Changer de modèle
            pinkybrain_bug.model = model

            for i, query in enumerate(EXTREME_QUERIES_SAMPLE):
                print(f"\n   [{i+1}/{len(EXTREME_QUERIES_SAMPLE)}] {query[:50]}...")

                start = time.time()

                try:
                    result = await pinkybrain_bug.query(query)
                    latency = (time.time() - start) * 1000

                    response = result.get("response", "")
                    print(f"      ✅ ({latency:.0f}ms) - {len(response)} chars")
                    print(f"      Response: {response[:200]}...")

                    self.results.append(CloudResult(
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

                    self.results.append(CloudResult(
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
        print("📊 RÉSULTATS DU BENCHMARK EXTREME v2")
        print("=" * 70)

        duration = (self.end_time - self.start_time).total_seconds()
        successful = [r for r in self.results if r.success]

        print(f"\n⏱️ Durée: {duration:.1f}s")
        print(f"\n📈 Statistiques:")
        print(f"   Total: {len(self.results)}")
        print(f"   ✅ Succès: {len(successful)}")
        print(f"   📊 Success rate: {len(successful) / len(self.results):.2%}")

        if successful:
            latencies = [r.latency for r in successful]
            lengths = [r.response_length for r in successful]

            print(f"\n⚡ Latence moy: {sum(latencies) / len(latencies):.1f}ms")
            print(f"📝 Longueur moy: {sum(lengths) / len(lengths):.0f} chars")

        print(f"\n🤖 Stats par modèle:")
        for model in CLOUD_MODELS:
            model_results = [r for r in self.results if r.model == model]
            model_success = [r for r in model_results if r.success]

            print(f"\n   {model}:")
            print(f"     Succès: {len(model_success)}/{len(model_results)}")
            if model_success:
                print(f"     Latence moy: {sum(r.latency for r in model_success) / len(model_success):.1f}ms")
                print(f"     Longueur moy: {sum(r.response_length for r in model_success) / len(model_success):.0f} chars")

        # Afficher les meilleures réponses
        print(f"\n📝 Meilleures réponses (par longueur):")
        top_responses = sorted(successful, key=lambda r: r.response_length, reverse=True)[:3]

        for i, r in enumerate(top_responses, 1):
            print(f"\n   {i}. Model: {r.model}")
            print(f"      Query: {r.query[:60]}...")
            print(f"      Length: {r.response_length} chars")
            print(f"      Latency: {r.latency:.0f}ms")
            print(f"      Response: {r.response[:300]}...")

async def main():
    print("=" * 70)
    print("🧪 BENCHMARK EXTREME v2 - QUESTIONS DOCTORALES AVEC MODELS CLOUD")
    print("=" * 70)

    os.makedirs("output", exist_ok=True)

    benchmark = CloudBenchmark()
    await benchmark.run_benchmark()

    print("\n" + "=" * 70)
    print("✅ BENCHMARK TERMINÉ !")
    print("=" * 70)

if __name__ == '__main__':
    asyncio.run(main())