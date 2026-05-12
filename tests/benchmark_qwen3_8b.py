#!/usr/bin/env python3
"""
🧪 BENCHMARK EXTREME v3 - Avec qwen3:8b (modèle capable)
Test avec un modèle réellement capable de répondre à des questions doctorales
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
    "Démontrez le théorème d'incomplétude de Gödel et expliquez ses implications pour les systèmes formels.",
    "Expliquez le problème P vs NP et pourquoi c'est important pour l'informatique.",
    "Démontrez comment la relativité générale prédit la précession du périhélie de Mercure.",
    "Qu'est-ce que le problème de la conscience qualia selon Thomas Nagel ?",
    "Intégrez les concepts de relativité générale et mécanique quantique pour expliquer l'unification.",
]

# qwen3:8b est capable (8B paramètres)
MODEL = "qwen3:8b"

@dataclass
class CapableResult:
    query: str
    model: str
    success: bool
    latency: float
    response_length: int
    response: str
    error: str = None

class CapableBenchmark:
    def __init__(self):
        self.results = []
        self.start_time = None
        self.end_time = None

    async def run_benchmark(self):
        print("=" * 70)
        print("🧪 BENCHMARK EXTREME v3 - Qwen3 8B (Modèle Capable)")
        print("=" * 70)
        print(f"\n📋 Configuration:")
        print(f"   Questions: {len(EXTREME_QUERIES_SAMPLE)}")
        print(f"   Modèle: {MODEL} (8B paramètres)")
        print(f"   Total tests: {len(EXTREME_QUERIES_SAMPLE)}")

        # Créer PinkyBrain avec qwen3:8b
        pinkybrain_bug = PinkyBrain()
        pinkybrain_bug.model = MODEL
        await pinkybrain_bug.initialize()

        self.start_time = datetime.utcnow()

        for i, query in enumerate(EXTREME_QUERIES_SAMPLE):
            print(f"\n[{i+1}/{len(EXTREME_QUERIES_SAMPLE)}] {query[:60]}...")

            start = time.time()

            try:
                result = await pinkybrain_bug.query(query)
                latency = (time.time() - start) * 1000

                response = result.get("response", "")
                print(f"✅ ({latency:.0f}ms) - {len(response)} chars")
                print(f"   Response: {response[:300]}...")

                self.results.append(CapableResult(
                    query=query,
                    model=MODEL,
                    success=result.get("status") == "success",
                    latency=latency,
                    response_length=len(response),
                    response=response,
                    error=result.get("error")
                ))

            except Exception as e:
                latency = (time.time() - start) * 1000
                print(f"❌ ({latency:.0f}ms) - {e}")

                self.results.append(CapableResult(
                    query=query,
                    model=MODEL,
                    success=False,
                    latency=latency,
                    response_length=0,
                    response="",
                    error=str(e)
                ))

        self.end_time = datetime.utcnow()

        self.print_stats()
        self.save_results()

    def print_stats(self):
        print("\n" + "=" * 70)
        print("📊 RÉSULTATS DU BENCHMARK EXTREME v3")
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

            print(f"\n⚡ Latence:")
            print(f"   Moyenne: {sum(latencies) / len(latencies):.1f}ms")
            print(f"   Min: {min(latencies):.1f}ms")
            print(f"   Max: {max(latencies):.1f}ms")
            print(f"\n📝 Réponses:")
            print(f"   Longueur moyenne: {sum(lengths) / len(lengths):.0f} chars")
            print(f"   Min: {min(lengths)} chars")
            print(f"   Max: {max(lengths)} chars")

        # Qualité des réponses
        print(f"\n🎯 Qualité:")
        if successful:
            avg_length = sum(r.response_length for r in successful) / len(successful)
            if avg_length > 200:
                print(f"   ✅ Réponses substantielles ({avg_length:.0f} chars moy)")
            elif avg_length > 50:
                print(f"   ⚠️ Réponses courtes mais présentes ({avg_length:.0f} chars moy)")
            else:
                print(f"   ❌ Réponses trop courtes ({avg_length:.0f} chars moy)")

    def save_results(self):
        data = {
            "model": MODEL,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "results": [
                {
                    "query": r.query,
                    "success": r.success,
                    "latency": r.latency,
                    "response_length": r.response_length,
                    "response": r.response,
                    "error": r.error
                }
                for r in self.results
            ]
        }

        with open("output/qwen3_8b_benchmark.json", 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Résultats sauvegardés: output/qwen3_8b_benchmark.json")

async def main():
    print("=" * 70)
    print("🧪 BENCHMARK EXTREME v3 - QWEN3 8B")
    print("=" * 70)

    os.makedirs("output", exist_ok=True)

    benchmark = CapableBenchmark()
    await benchmark.run_benchmark()

    print("\n" + "=" * 70)
    print("✅ BENCHMARK TERMINÉ !")
    print("=" * 70)

if __name__ == '__main__':
    asyncio.run(main())