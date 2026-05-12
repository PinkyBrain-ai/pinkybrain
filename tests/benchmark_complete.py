#!/usr/bin/env python3
"""
🧪 BENCHMARK COMPLET - PinkyBrain & PinkyBrain v3.0
Test avec 100 requêtes, multi-LLM, et analyse d'évolution
"""

import asyncio
import time
import json
import statistics
from datetime import datetime
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
import random
import sys
import os

# Ajouter le chemin
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.pinkybrain_v3_final import PinkyBrain
from src.pinkybrain_v5 import PinkyBrain

# ============================================================================
# ============== 100 REQUÊTES DE TEST ======================================
# ============================================================================

TEST_QUERIES = [
    # Questions générales sur PinkyBrain (20)
    "Qu'est-ce que PinkyBrain v3.0 ?",
    "Comment fonctionne le P2P Network ?",
    "Explique le DHT (Distributed Hash Table)",
    "Qu'est-ce que le Gossip Protocol ?",
    "Comment fonctionne Kademlia ?",
    "Qu'est-ce que l'auto-émancipation ?",
    "Explique la self-awareness",
    "Comment PinkyBrain apprend-il ?",
    "Qu'est-ce que le consensus d'ensemble ?",
    "Comment fonctionne le load balancing ?",
    "Qu'est-ce que la distributed memory ?",
    "Explique l'UX Monitor",
    "Comment fonctionne le circuit breaker ?",
    "Qu'est-ce que le retry logic ?",
    "Explique le rate limiting",
    "Comment fonctionne le cache intelligent ?",
    "Qu'est-ce que le model versioning ?",
    "Comment fonctionne le streaming ?",
    "Qu'est-ce que batch requests ?",
    "Explique la sybil resistance",

    # Questions techniques (20)
    "Écris une fonction Python pour calculer une factorielle",
    "Comment faire un appel HTTP en Python ?",
    "Explique le concept d'asynchronicité",
    "Qu'est-ce qu'un decorator en Python ?",
    "Comment gérer les exceptions en Python ?",
    "Explique le concept de closure",
    "Qu'est-ce qu'une liste en compréhension ?",
    "Comment créer une classe en Python ?",
    "Explique le concept d'héritage",
    "Qu'est-ce qu'un générateur ?",
    "Comment utiliser async/await en Python ?",
    "Explique le concept de coroutine",
    "Qu'est-ce qu'un context manager ?",
    "Comment lire un fichier en Python ?",
    "Explique le JSON parsing",
    "Qu'est-ce que le multithreading ?",
    "Comment utiliser multiprocessing ?",
    "Explique le concept de race condition",
    "Qu'est-ce qu'un deadlock ?",
    "Comment optimiser le code Python ?",

    # Questions sur l'IA et le ML (20)
    "Qu'est-ce qu'un LLM ?",
    "Explique le concept de transformer",
    "Qu'est-ce que l'attention mechanism ?",
    "Comment fonctionne le fine-tuning ?",
    "Qu'est-ce que le RLHF ?",
    "Explique le concept de temperature",
    "Qu'est-ce que top-k sampling ?",
    "Comment fonctionne top-p sampling ?",
    "Qu'est-ce que beam search ?",
    "Explique le concept de tokenization",
    "Qu'est-ce qu'un embedding ?",
    "Comment fonctionne le vector database ?",
    "Explique le concept de RAG",
    "Qu'est-ce que le retrieval augmented generation ?",
    "Comment fonctionne la chunking ?",
    "Qu'est-ce que le semantic search ?",
    "Explique le concept de cosine similarity ?",
    "Qu'est-ce que le vector space ?",
    "Comment fonctionne le re-ranking ?",
    "Explique le concept de hallucination",

    # Questions créatives (20)
    "Écris un poème sur l'intelligence artificielle",
    "Raconte une histoire courte sur un robot",
    "Invente un nom pour un système d'IA",
    "Crée un slogan pour une entreprise de tech",
    "Écris une chanson sur le P2P",
    "Fais une blague sur l'IA",
    "Invente un concept de futur",
    "Décris un monde sans humains",
    "Crée un personnage de science-fiction",
    "Écris un proverbe moderne",
    "Invente un nouveau mot",
    "Crée une métaphore pour l'IA",
    "Écris une citation inspirante",
    "Invente une histoire alternative",
    "Crée un jeu de rôle",
    "Écris un dialogue entre deux AIs",
    "Invente un concept d'art",
    "Crée une fable moderne",
    "Écris un haïku sur la technologie",
    "Invente un mythe futuriste",

    # Questions analytiques (20)
    "Analyse les avantages du P2P par rapport au centralisé",
    "Compare les différents LLM",
    "Évalue les risques de l'auto-émancipation",
    "Analyse l'impact de l'IA sur la société",
    "Compare P2P vs Client-Server",
    "Évalue l'efficacité du cache",
    "Analyse les problèmes du centralisé",
    "Compare les algorithmes de routing",
    "Évalue les avantages de l'asynchronicité",
    "Analyse l'importance de la sécurité",
    "Compare les méthodes de scaling",
    "Évalue l'impact des logs structurés",
    "Analyse les métriques importantes",
    "Compare les stratégies de retry",
    "Évalue l'utilité du circuit breaker",
    "Analyse les problèmes du rate limiting",
    "Compare les méthodes de sharding",
    "Évalue l'importance du versioning",
    "Analyse les défis de l'observability",
    "Compare P2P vs blockchain",
]

# LLMs à tester
LLMS_TO_TEST = [
    "SmolLM2:1.7b",
    "phi3:mini",
    "TinyLlama:latest",
    "Stable-code:3b"
]

# ============================================================================
# ============== BENCHMARK STATS ===========================================
# ============================================================================

@dataclass
class BenchmarkResult:
    """Résultat d'un benchmark"""
    query_index: int
    query: str
    model: str
    success: bool
    latency: float
    response_length: int
    error: str = None
    peer: str = None
    frustration: float = 0.0

@dataclass
class BenchmarkStats:
    """Statistiques de benchmark"""
    total_queries: int
    successful_queries: int
    failed_queries: int
    success_rate: float
    avg_latency: float
    min_latency: float
    max_latency: float
    median_latency: float
    std_dev_latency: float
    avg_response_length: int
    model_stats: Dict[str, Dict]
    peer_stats: Dict[str, Dict]
    errors: List[str]

# ============================================================================
# ============== BENCHMARK RUNNER =========================================
# ============================================================================

class BenchmarkRunner:
    """Runner de benchmark"""

    def __init__(self, system_name: str):
        self.system_name = system_name
        self.results: List[BenchmarkResult] = []
        self.start_time: datetime = None
        self.end_time: datetime = None

    async def run_query(self, query_func, query: str, model: str,
                       query_index: int) -> BenchmarkResult:
        """Exécute une query"""
        start = time.time()

        try:
            result = await query_func(query, model)

            latency = (time.time() - start) * 1000  # ms

            return BenchmarkResult(
                query_index=query_index,
                query=query,
                model=model,
                success=result.get("status") == "success",
                latency=latency,
                response_length=len(result.get("response", "")),
                error=result.get("error"),
                peer=result.get("peer"),
                frustration=result.get("frustration", 0.0)
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
                error=str(e),
                frustration=1.0
            )

    async def run_benchmark(self, query_func, queries: List[str],
                           models: List[str], iterations: int = 1):
        """Exécute le benchmark"""
        print(f"\n{'=' * 70}")
        print(f"🧪 BENCHMARK - {self.system_name}")
        print(f"{'=' * 70}")
        print(f"\n📋 Configuration:")
        print(f"   Queries: {len(queries)}")
        print(f"   Models: {len(models)}")
        print(f"   Total tests: {len(queries) * len(models)}")

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

    def get_stats(self) -> BenchmarkStats:
        """Calcule les statistiques"""
        successful = [r for r in self.results if r.success]
        failed = [r for r in self.results if not r.success]

        latencies = [r.latency for r in successful]
        response_lengths = [r.response_length for r in successful]

        # Stats par modèle
        model_stats = {}
        for model in LLS_TO_TEST:
            model_results = [r for r in self.results if r.model == model]
            model_success = [r for r in model_results if r.success]
            model_latencies = [r.latency for r in model_success]

            model_stats[model] = {
                "total": len(model_results),
                "success": len(model_success),
                "failed": len(model_results) - len(model_success),
                "success_rate": len(model_success) / len(model_results) if model_results else 0,
                "avg_latency": statistics.mean(model_latencies) if model_latencies else 0,
                "min_latency": min(model_latencies) if model_latencies else 0,
                "max_latency": max(model_latencies) if model_latencies else 0,
            }

        # Stats par peer
        peer_stats = {}
        peers = [r.peer for r in self.results if r.peer]
        for peer in set(peers):
            peer_results = [r for r in self.results if r.peer == peer]
            peer_latencies = [r.latency for r in peer_results if r.success]

            peer_stats[peer] = {
                "total": len(peer_results),
                "avg_latency": statistics.mean(peer_latencies) if peer_latencies else 0,
            }

        # Erreurs
        errors = [r.error for r in failed if r.error]

        return BenchmarkStats(
            total_queries=len(self.results),
            successful_queries=len(successful),
            failed_queries=len(failed),
            success_rate=len(successful) / len(self.results) if self.results else 0,
            avg_latency=statistics.mean(latencies) if latencies else 0,
            min_latency=min(latencies) if latencies else 0,
            max_latency=max(latencies) if latencies else 0,
            median_latency=statistics.median(latencies) if latencies else 0,
            std_dev_latency=statistics.stdev(latencies) if len(latencies) > 1 else 0,
            avg_response_length=int(statistics.mean(response_lengths)) if response_lengths else 0,
            model_stats=model_stats,
            peer_stats=peer_stats,
            errors=errors
        )

    def print_stats(self, stats: BenchmarkStats):
        """Affiche les statistiques"""
        print(f"\n{'=' * 70}")
        print(f"📊 RÉSULTATS DU BENCHMARK - {self.system_name}")
        print(f"{'=' * 70}")

        duration = (self.end_time - self.start_time).total_seconds()

        print(f"\n⏱️ Durée: {duration:.1f}s")
        print(f"\n📈 Statistiques générales:")
        print(f"   Total queries: {stats.total_queries}")
        print(f"   ✅ Succès: {stats.successful_queries}")
        print(f"   ❌ Échecs: {stats.failed_queries}")
        print(f"   📊 Success rate: {stats.success_rate:.2%}")
        print(f"\n⚡ Latence (ms):")
        print(f"   Moyenne: {stats.avg_latency:.1f}")
        print(f"   Min: {stats.min_latency:.1f}")
        print(f"   Max: {stats.max_latency:.1f}")
        print(f"   Médiane: {stats.median_latency:.1f}")
        print(f"   Écart-type: {stats.std_dev_latency:.1f}")
        print(f"\n📝 Réponse:")
        print(f"   Longueur moyenne: {stats.avg_response_length} chars")

        print(f"\n🤖 Stats par modèle:")
        for model, model_stat in stats.model_stats.items():
            print(f"\n   {model}:")
            print(f"     Total: {model_stat['total']}")
            print(f"     Succès: {model_stat['success']}")
            print(f"     Échecs: {model_stat['failed']}")
            print(f"     Success rate: {model_stat['success_rate']:.2%}")
            print(f"     Latence moy: {model_stat['avg_latency']:.1f}ms")

        if stats.peer_stats:
            print(f"\n🌐 Stats par peer:")
            for peer, peer_stat in stats.peer_stats.items():
                print(f"\n   {peer}:")
                print(f"     Total: {peer_stat['total']}")
                print(f"     Latence moy: {peer_stat['avg_latency']:.1f}ms")

        if stats.errors:
            print(f"\n❌ Erreurs ({len(stats.errors)}):")
            for i, error in enumerate(stats.errors[:10], 1):
                print(f"   {i}. {error}")

    def save_results(self, filename: str):
        """Sauvegarde les résultats"""
        data = {
            "system_name": self.system_name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "results": [
                {
                    "query_index": r.query_index,
                    "query": r.query,
                    "model": r.model,
                    "success": r.success,
                    "latency": r.latency,
                    "response_length": r.response_length,
                    "error": r.error,
                    "peer": r.peer,
                    "frustration": r.frustration
                }
                for r in self.results
            ],
            "stats": self.get_stats().__dict__
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Résultats sauvegardés: {filename}")

# ============================================================================
# ============== MAIN ========================================================
# ============================================================================

async def benchmark_pinkybrain():
    """Benchmark PinkyBrain"""
    print("\n" + "=" * 70)
    print("🧪 BENCHMARK PINKYBRAIN v3.0")
    print("=" * 70)

    # Créer PinkyBrain
    pinkybrain = PinkyBrain()
    await pinkybrain.initialize()

    # Créer le runner
    runner = BenchmarkRunner("PinkyBrain")

    # Query function
    async def query_func(prompt, model):
        return await pinkybrain.query(prompt, model=model)

    # Exécuter le benchmark
    stats = await runner.run_benchmark(query_func, TEST_QUERIES, LLMS_TO_TEST)

    # Afficher les stats
    runner.print_stats(stats)

    # Sauvegarder
    runner.save_results("output/pinkybrain_benchmark.json")

    # Stats d'émancipation (si disponible)
    if hasattr(pinkybrain, 'prod'):
        print(f"\n🔍 Production stats:")
        prod_stats = pinkybrain.prod.get_status()
        print(f"   Cache size: {prod_stats.get('cache', {}).get('size', 0)}")
        print(f"   Cache hit rate: {prod_stats.get('cache', {}).get('hit_rate', 0):.2%}")

    return runner

async def benchmark_pinkybrain_bug():
    """Benchmark PinkyBrain"""
    print("\n" + "=" * 70)
    print("🧪 BENCHMARK PINKYBRAIN_BUG v3.0")
    print("=" * 70)

    # Créer PinkyBrain
    pinkybrain_bug = PinkyBrain()
    await pinkybrain_bug.initialize()

    # Créer le runner
    runner = BenchmarkRunner("PinkyBrain")

    # Query function
    async def query_func(prompt, model):
        return await pinkybrain_bug.query(prompt)

    # Exécuter le benchmark
    stats = await runner.run_benchmark(query_func, TEST_QUERIES, LLMS_TO_TEST[:2])

    # Afficher les stats
    runner.print_stats(stats)

    # Sauvegarder
    runner.save_results("output/pinkybrain_bug_benchmark.json")

    # Stats d'émancipation
    emancipation_status = pinkybrain_bug.emancipation.get_status()
    print(f"\n🧠 Stats d'émancipation:")
    print(f"   Âge: {emancipation_status['awareness']['age']} interactions")
    print(f"   Success rate: {emancipation_status['awareness']['success_rate']:.2%}")
    print(f"   Leçons: {emancipation_status['awareness']['lessons_count']}")
    print(f"   Patterns: {emancipation_status['learning']['patterns_count']}")
    print(f"   Compétences: {emancipation_status['learning']['skills_count']}")

    return runner

async def compare_results():
    """Compare les résultats"""
    print("\n" + "=" * 70)
    print("📊 COMPARAISON DES RÉSULTATS")
    print("=" * 70)

    try:
        with open("output/pinkybrain_benchmark.json", 'r', encoding='utf-8') as f:
            pinkybrain_data = json.load(f)
    except:
        print("❌ PinkyBrain benchmark not found")
        pinkybrain_data = None

    try:
        with open("output/pinkybrain_bug_benchmark.json", 'r', encoding='utf-8') as f:
            pinkybrain_bug_data = json.load(f)
    except:
        print("❌ PinkyBrain benchmark not found")
        pinkybrain_bug_data = None

    if pinkybrain_data and pinkybrain_bug_data:
        print(f"\n📈 Success Rate:")
        print(f"   PinkyBrain: {pinkybrain_data['stats']['success_rate']:.2%}")
        print(f"   PinkyBrain: {pinkybrain_bug_data['stats']['success_rate']:.2%}")

        print(f"\n⚡ Latence moyenne:")
        print(f"   PinkyBrain: {pinkybrain_data['stats']['avg_latency']:.1f}ms")
        print(f"   PinkyBrain: {pinkybrain_bug_data['stats']['avg_latency']:.1f}ms")

        print(f"\n📝 Longueur moyenne des réponses:")
        print(f"   PinkyBrain: {pinkybrain_data['stats']['avg_response_length']} chars")
        print(f"   PinkyBrain: {pinkybrain_bug_data['stats']['avg_response_length']} chars")

        # Meilleur modèle
        print(f"\n🤖 Meilleur modèle (PinkyBrain):")
        ub_models = pinkybrain_data['stats']['model_stats']
        best_model = min(ub_models.items(), key=lambda x: x[1]['avg_latency'] if x[1]['avg_latency'] > 0 else float('inf'))
        print(f"   {best_model[0]}: {best_model[1]['avg_latency']:.1f}ms ({best_model[1]['success_rate']:.2%} success)")

async def main():
    """Main function"""
    print("=" * 70)
    print("🧪 BENCHMARK COMPLET - 100 REQUÊTES")
    print("=" * 70)

    # Créer le répertoire output
    os.makedirs("output", exist_ok=True)

    # Benchmark PinkyBrain
    pinkybrain_runner = await benchmark_pinkybrain()

    # Attendre un peu
    await asyncio.sleep(2)

    # Benchmark PinkyBrain
    pinkybrain_bug_runner = await benchmark_pinkybrain_bug()

    # Comparaison
    await compare_results()

    print("\n" + "=" * 70)
    print("✅ BENCHMARK TERMINÉ !")
    print("=" * 70)

    print("\n📁 Fichiers générés:")
    print("   output/pinkybrain_benchmark.json")
    print("   output/pinkybrain_bug_benchmark.json")

if __name__ == '__main__':
    asyncio.run(main())