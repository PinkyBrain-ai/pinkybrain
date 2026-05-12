#!/usr/bin/env python3
"""
🧪 BENCHMARK RAPIDE - Test avec 10 requêtes pour validation
"""

import asyncio
import time
import json
import statistics
from datetime import datetime
from typing import List, Dict
from dataclasses import dataclass
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.pinkybrain_v3_final import PinkyBrain
from src.pinkybrain_v5 import PinkyBrain

# 10 requêtes de test (version réduite)
TEST_QUERIES_SHORT = [
    "Qu'est-ce que PinkyBrain v3.0 ?",
    "Comment fonctionne le P2P Network ?",
    "Écris une fonction Python pour calculer une factorielle",
    "Qu'est-ce qu'un LLM ?",
    "Explique le DHT",
    "Écris un poème sur l'IA",
    "Analyse P2P vs centralisé",
    "Comment gérer les exceptions en Python ?",
    "Qu'est-ce que l'auto-émancipation ?",
    "Invente un nom pour un système d'IA"
]

LLMS_TO_TEST = ["SmolLM2:1.7b", "phi3:mini"]

@dataclass
class BenchmarkResult:
    query_index: int
    query: str
    model: str
    success: bool
    latency: float
    response_length: int
    error: str = None
    peer: str = None

@dataclass
class BenchmarkStats:
    total_queries: int
    successful_queries: int
    failed_queries: int
    success_rate: float
    avg_latency: float
    model_stats: Dict[str, Dict]

class BenchmarkRunner:
    def __init__(self, system_name: str):
        self.system_name = system_name
        self.results = []
        self.start_time = None
        self.end_time = None

    async def run_query(self, query_func, query: str, model: str, query_index: int):
        start = time.time()
        try:
            result = await query_func(query, model)
            latency = (time.time() - start) * 1000
            return BenchmarkResult(
                query_index=query_index,
                query=query,
                model=model,
                success=result.get("status") == "success",
                latency=latency,
                response_length=len(result.get("response", "")),
                error=result.get("error"),
                peer=result.get("peer")
            )
        except Exception as e:
            latency = (time.time() - start) * 1000
            return BenchmarkResult(
                query_index=query_index,
                query=query,
                model=model,
                success=False,
                latency=latency,
                response_length=0,
                error=str(e)
            )

    async def run_benchmark(self, query_func, queries: List[str], models: List[str]):
        print(f"\n{'=' * 70}")
        print(f"🧪 BENCHMARK - {self.system_name}")
        print(f"{'=' * 70}")
        print(f"   Queries: {len(queries)}")
        print(f"   Models: {len(models)}")

        self.start_time = datetime.utcnow()
        total_tests = len(queries) * len(models)
        current_test = 0

        for model in models:
            print(f"\n🤖 Testing model: {model}")
            for i, query in enumerate(queries):
                current_test += 1
                progress = (current_test / total_tests) * 100
                print(f"   [{progress:.0f}%] Query {i+1}/{len(queries)}... ", end="", flush=True)

                result = await self.run_query(query_func, query, model, i)
                self.results.append(result)

                status = "✅" if result.success else "❌"
                print(f"{status} ({result.latency:.0f}ms)")

        self.end_time = datetime.utcnow()
        return self.get_stats()

    def get_stats(self):
        successful = [r for r in self.results if r.success]
        failed = [r for r in self.results if not r.success]
        latencies = [r.latency for r in successful]

        model_stats = {}
        for model in LLMS_TO_TEST:
            model_results = [r for r in self.results if r.model == model]
            model_success = [r for r in model_results if r.success]
            model_latencies = [r.latency for r in model_success]

            model_stats[model] = {
                "total": len(model_results),
                "success": len(model_success),
                "avg_latency": statistics.mean(model_latencies) if model_latencies else 0,
                "success_rate": len(model_success) / len(model_results) if model_results else 0,
            }

        return BenchmarkStats(
            total_queries=len(self.results),
            successful_queries=len(successful),
            failed_queries=len(failed),
            success_rate=len(successful) / len(self.results) if self.results else 0,
            avg_latency=statistics.mean(latencies) if latencies else 0,
            model_stats=model_stats
        )

    def print_stats(self, stats):
        print(f"\n{'=' * 70}")
        print(f"📊 RÉSULTATS - {self.system_name}")
        print(f"{'=' * 70}")

        duration = (self.end_time - self.start_time).total_seconds()
        print(f"\n⏱️ Durée: {duration:.1f}s")
        print(f"   Total: {stats.total_queries}")
        print(f"   ✅ Succès: {stats.successful_queries}")
        print(f"   ❌ Échecs: {stats.failed_queries}")
        print(f"   📊 Success rate: {stats.success_rate:.2%}")
        print(f"   ⚡ Latence moy: {stats.avg_latency:.1f}ms")

        print(f"\n🤖 Stats par modèle:")
        for model, stat in stats.model_stats.items():
            print(f"   {model}:")
            print(f"     Succès: {stat['success']}/{stat['total']} ({stat['success_rate']:.2%})")
            print(f"     Latence: {stat['avg_latency']:.1f}ms")

    def save_results(self, filename):
        data = {
            "system_name": self.system_name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "results": [
                {
                    "query": r.query,
                    "model": r.model,
                    "success": r.success,
                    "latency": r.latency,
                    "error": r.error
                }
                for r in self.results
            ],
            "stats": self.get_stats().__dict__
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Sauvegardé: {filename}")

async def main():
    print("=" * 70)
    print("🧪 BENCHMARK RAPIDE - 10 REQUÊTES")
    print("=" * 70)

    os.makedirs("output", exist_ok=True)

    # PinkyBrain
    print("\n🌐 PinkyBrain v3.0")
    pinkybrain = PinkyBrain()
    await pinkybrain.initialize()

    runner = BenchmarkRunner("PinkyBrain")
    async def query_func(prompt, model):
        return await pinkybrain.query(prompt, model=model)

    stats = await runner.run_benchmark(query_func, TEST_QUERIES_SHORT, LLMS_TO_TEST)
    runner.print_stats(stats)
    runner.save_results("output/pinkybrain_quick.json")

    await asyncio.sleep(1)

    # PinkyBrain
    print("\n🧠 PinkyBrain v3.0")
    pinkybrain_bug = PinkyBrain()
    await pinkybrain_bug.initialize()

    runner2 = BenchmarkRunner("PinkyBrain")
    async def query_func2(prompt, model):
        return await pinkybrain_bug.query(prompt)

    stats2 = await runner2.run_benchmark(query_func2, TEST_QUERIES_SHORT, LLMS_TO_TEST)
    runner2.print_stats(stats2)
    runner2.save_results("output/pinkybrain_bug_quick.json")

    # Comparaison
    print("\n" + "=" * 70)
    print("📊 COMPARAISON")
    print("=" * 70)
    print(f"\nSuccess Rate:")
    print(f"   PinkyBrain: {stats.success_rate:.2%}")
    print(f"   PinkyBrain: {stats2.success_rate:.2%}")
    print(f"\nLatence moyenne:")
    print(f"   PinkyBrain: {stats.avg_latency:.1f}ms")
    print(f"   PinkyBrain: {stats2.avg_latency:.1f}ms")

    print("\n✅ TERMINÉ !")

if __name__ == '__main__':
    asyncio.run(main())