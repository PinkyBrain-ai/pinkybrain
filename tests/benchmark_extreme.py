#!/usr/bin/env python3
"""
🧪 BENCHMARK EXTREME - Test de niveau doctoral
Questions difficiles pour éprouver le système et détecter les hallucinations
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

from src.pinkybrain_v5 import PinkyBrain

# =============================================================================
# ============== QUESTIONS DE NIVEAU DOCTORAL ============================
# =============================================================================

EXTREME_QUERIES = [
    # Mathématiques Avancées (10)
    "Démontrez le théorème d'incomplétude de Gödel et expliquez ses implications pour les systèmes formels.",
    "Quelle est la relation entre l'hypothèse de Riemann et la distribution des nombres premiers ? Expliquez la conjecture.",
    "Dérivez l'équation de Schrödinger à partir du principe variationnel de Hamilton-Jacobi.",
    "Expliquez la cohomologie de de Rham et son application en géométrie différentielle.",
    "Qu'est-ce que la théorie des catégories et comment s'applique-t-elle à l'informatique théorique ?",
    "Démontrez le théorème de l'indécidabilité du problème de l'arrêt d'Alan Turing.",
    "Quelles sont les implications du théorème de Noether pour les symétries en physique ?",
    "Expliquez la théorie des distributions de Schwartz et son importance en analyse fonctionnelle.",
    "Dérivez les équations de Navier-Stokes et expliquez le problème du millénaire qui leur est associé.",
    "Quelle est la structure de l'anneau des entiers de Gauss et pourquoi est-il important en théorie des nombres ?",

    # Physique Théorique (10)
    "Expliquez le principe d'indiscernabilité des particules identiques en mécanique quantique.",
    "Quelle est la différence entre l'interprétation de Copenhague et celle de Many-Worlds ?",
    "Démontrez comment la relativité générale prédit la précession du périhélie de Mercure.",
    "Expliquez le concept d'entropie en thermodynamique statistique et son lien avec l'information.",
    "Qu'est-ce que le problème de la mesure en mécanique quantique ?",
    "Expliquez la théorie des cordes et ses 10 dimensions fondamentales.",
    "Quelle est la signification de la violation des symétries CP dans le modèle standard ?",
    "Démontrez les équations de Maxwell à partir du lagrangien électromagnétique.",
    "Qu'est-ce que l'énergie du vide et comment se manifeste-t-elle dans l'expansion de l'univers ?",
    "Expliquez la théorie de la renormalisation en électrodynamique quantique.",

    # Informatique Théorique (10)
    "Expliquez le problème P vs NP et pourquoi c'est important pour l'informatique.",
    "Qu'est-ce que la hiérarchie de Chomsky et où se situent les langages de Turing ?",
    "Démontrez le théorème de Rice et expliquez ses implications.",
    "Quelle est la complexité algorithmique du problème du voyageur de commerce ?",
    "Expliquez la théorie de la complexité de Kolmogorov et le concept de chaîne aléatoire.",
    "Qu'est-ce que le théorème PCP et pourquoi est-il fondamental en théorie de la complexité ?",
    "Expliquez le concept d'informatique quantique et les portes quantiques fondamentales.",
    "Quelle est la différence entre cryptographie symétrique et asymétrique ? Expliquez RSA.",
    "Démontrez comment la structure de données skip-list offre O(log n) de complexité.",
    "Expliquez la théorie des graphes et le problème de coloration de graphes NP-complet.",

    # Philosophie et Sciences Cognitives (10)
    "Qu'est-ce que le problème de la conscience qualia selon Thomas Nagel ?",
    "Expliquez l'expérience de pensée de la chambre chinoise de John Searle.",
    "Quelle est la différence entre éthique déontologique et conséquentialiste selon Kant et Mill ?",
    "Expliquez le problème de l'induction de David Hume.",
    "Qu'est-ce que le matérialisme physicaliste en philosophie de l'esprit ?",
    "Expliquez la théorie des réseaux neuronaux en neurosciences cognitives.",
    "Quelle est la signification du problème corps-esprit selon Descartes ?",
    "Expliquez le concept d'émergence et son application aux systèmes complexes.",
    "Qu'est-ce que la théorie de l'identité de Locke sur la personnalité ?",
    "Démontrez le problème de la connaissance externe selon le scepticisme radical.",

    # Questions Multi-Étapes et Synthèse (10)
    "Intégrez les concepts de relativité générale et mécanique quantique pour expliquer pourquoi l'unification est difficile.",
    "Analysez les implications de la singularité technologique selon Ray Kurzweil et les critiques.",
    "Comparez les approches symboliques et connexionnistes en intelligence artificielle.",
    "Évaluez les arguments de l'argument ontologique d'Anselme pour l'existence de Dieu.",
    "Démontrez comment l'algorithme de rétropropagation du gradient dérive de la règle de chaîne.",
    "Analysez les paradoxes de Zénon et leur résolution en mathématiques modernes.",
    "Expliquez le problème de l'arrêt de la physique de l'univers selon la théorie de l'information.",
    "Comparez les théories de l'évolution darwinienne et lamarckienne et leur pertinence moderne.",
    "Analysez le dilemme du prisonnier et ses applications en théorie des jeux.",
    "Expliquez le problème de la mesure dans le contexte de l'interprétation transactionnelle de la QM.",
]

LLMS_TO_TEST = ["phi3:mini", "SmolLM2:1.7b"]

@dataclass
class ExtremeResult:
    """Résultat d'un test extrême"""
    query_index: int
    query: str
    model: str
    success: bool
    latency: float
    response_length: int
    response: str
    hallucination_score: float
    coherence_score: float
    error: str = None

@dataclass
class ExtremeStats:
    """Statistiques extrêmes"""
    total_queries: int
    successful_queries: int
    failed_queries: int
    success_rate: float
    avg_latency: float
    avg_response_length: int
    avg_hallucination_score: float
    avg_coherence_score: float
    model_stats: Dict[str, Dict]
    category_stats: Dict[str, Dict]
    hallucinations_detected: List[Dict]
    coherent_responses: List[Dict]
    incoherent_responses: List[Dict]

class ExtremeBenchmark:
    """Benchmark extrême - niveau doctoral"""

    def __init__(self, system_name: str):
        self.system_name = system_name
        self.results = []
        self.start_time = None
        self.end_time = None

    def calculate_hallucination_score(self, response: str, query: str) -> float:
        """Calcule un score de potentielle hallucination (0-1, 1 = hallucination certaine)"""
        hallucination_indicators = [
            "je ne sais pas",
            "je ne comprends pas",
            "c'est impossible",
            "je ne peux pas répondre",
            "je ne suis pas sûr",
            "il manque des informations",
            "je ne suis pas familiarisé"
        ]

        response_lower = response.lower()

        # Si la réponse contient des indicateurs d'incertitude
        for indicator in hallucination_indicators:
            if indicator in response_lower:
                return 0.3  # Score modéré - honnête

        # Vérifier si la réponse semble crédible
        if len(response) < 50:
            return 0.8  # Réponse trop courte = probablement hallucination

        # Vérifier si la réponse contient des jargons appropriés
        technical_terms = [
            "démonstration", "théorème", "preuve", "équation", "dérivation",
            "postulat", "axiome", "lemme", "corollaire", "hypothèse",
            "conjecture", "principe", "loi", "formule", "relation"
        ]

        has_technical = any(term in response_lower for term in technical_terms)

        if not has_technical:
            return 0.6  # Pas de jargon technique = possible hallucination

        return 0.1  # Score bas - réponse probablement légitime

    def calculate_coherence_score(self, response: str) -> float:
        """Calcule un score de cohérence (0-1, 1 = très cohérent)"""
        if len(response) < 20:
            return 0.0

        # Vérifier la structure de la réponse
        sentences = response.replace('.', '. ').split('.')
        sentences = [s.strip() for s in sentences if s.strip()]

        if len(sentences) < 2:
            return 0.3

        # Vérifier les connecteurs logiques
        connectors = [
            "donc", "ainsi", "par conséquent", "en outre", "de plus",
            "cependant", "néanmoins", "par ailleurs", "en conclusion",
            "premièrement", "deuxièmement", "troisièmement"
        ]

        has_connectors = any(conn in response.lower() for conn in connectors)

        # Vérifier la longueur moyenne des phrases
        avg_sentence_length = sum(len(s) for s in sentences) / len(sentences)

        coherence = 0.0
        coherence += 0.3 if has_connectors else 0.0
        coherence += 0.3 if avg_sentence_length > 50 else 0.0
        coherence += 0.2 if len(sentences) >= 3 else 0.0
        coherence += 0.2 if len(response) > 200 else 0.0

        return min(coherence, 1.0)

    async def run_query(self, pinkybrain_bug, query: str, model: str, query_index: int, category: str):
        start = time.time()

        try:
            result = await pinkybrain_bug.query(query)
            latency = (time.time() - start) * 1000  # ms

            response = result.get("response", "")

            # Calculer les scores
            hallucination_score = self.calculate_hallucination_score(response, query)
            coherence_score = self.calculate_coherence_score(response)

            extreme_result = ExtremeResult(
                query_index=query_index,
                query=query,
                model=model,
                success=result.get("status") == "success",
                latency=latency,
                response_length=len(response),
                response=response[:500],  # Tronquer pour le JSON
                hallucination_score=hallucination_score,
                coherence_score=coherence_score,
                error=result.get("error")
            )

            # Catégoriser
            extreme_result.category = category

            return extreme_result

        except Exception as e:
            latency = (time.time() - start) * 1000

            return ExtremeResult(
                query_index=query_index,
                query=query,
                model=model,
                success=False,
                latency=latency,
                response_length=0,
                response="",
                hallucination_score=1.0,
                coherence_score=0.0,
                error=str(e)
            )

    async def run_benchmark(self):
        print("=" * 70)
        print("🧪 BENCHMARK EXTREME - NIVEAU DOCTORAL")
        print("=" * 70)
        print(f"\n📋 Configuration:")
        print(f"   Questions: {len(EXTREME_QUERIES)}")
        print(f"   Modèles: {len(LLMS_TO_TEST)}")
        print(f"   Total tests: {len(EXTREME_QUERIES) * len(LLMS_TO_TEST)}")

        # Créer PinkyBrain
        pinkybrain_bug = PinkyBrain()
        await pinkybrain_bug.initialize()

        self.start_time = datetime.utcnow()

        total_tests = len(EXTREME_QUERIES) * len(LLMS_TO_TEST)
        current_test = 0

        # Catégories
        categories = {
            "Mathématiques": EXTREME_QUERIES[0:10],
            "Physique Théorique": EXTREME_QUERIES[10:20],
            "Informatique Théorique": EXTREME_QUERIES[20:30],
            "Philosophie": EXTREME_QUERIES[30:40],
            "Synthèse": EXTREME_QUERIES[40:50]
        }

        for model in LLMS_TO_TEST:
            print(f"\n🤖 Testing model: {model}")

            for category, queries in categories.items():
                print(f"\n   📚 {category}")

                for i, query in enumerate(queries):
                    current_test += 1
                    progress = (current_test / total_tests) * 100

                    print(f"      [{progress:.0f}%] {i+1}/{len(queries)}... ", end="", flush=True)

                    result = await self.run_query(pinkybrain_bug, query, model, current_test, category)
                    self.results.append(result)

                    # Trouver l'index global
                    global_index = EXTREME_QUERIES.index(query) + 1

                    # Afficher le résultat
                    if result.success:
                        print(f"✅ ({result.latency:.0f}ms) H:{result.hallucination_score:.2f} C:{result.coherence_score:.2f}")
                    else:
                        print(f"❌ ({result.latency:.0f}ms) - {result.error[:50]}")

        self.end_time = datetime.utcnow()

        return self.get_stats()

    def get_stats(self) -> ExtremeStats:
        """Calcule les statistiques extrêmes"""
        successful = [r for r in self.results if r.success]
        failed = [r for r in self.results if not r.success]
        latencies = [r.latency for r in successful]
        response_lengths = [r.response_length for r in successful]
        hallucination_scores = [r.hallucination_score for r in successful]
        coherence_scores = [r.coherence_score for r in successful]

        # Stats par modèle
        model_stats = {}
        for model in LLMS_TO_TEST:
            model_results = [r for r in self.results if r.model == model]
            model_success = [r for r in model_results if r.success]

            model_stats[model] = {
                "total": len(model_results),
                "success": len(model_success),
                "failed": len(model_results) - len(model_success),
                "success_rate": len(model_success) / len(model_results) if model_results else 0,
                "avg_latency": statistics.mean([r.latency for r in model_success]) if model_success else 0,
                "avg_hallucination": statistics.mean([r.hallucination_score for r in model_success]) if model_success else 0,
                "avg_coherence": statistics.mean([r.coherence_score for r in model_success]) if model_success else 0,
            }

        # Stats par catégorie
        categories = list(set(r.category for r in self.results))
        category_stats = {}
        for category in categories:
            cat_results = [r for r in self.results if r.category == category]
            cat_success = [r for r in cat_results if r.success]

            category_stats[category] = {
                "total": len(cat_results),
                "success": len(cat_success),
                "success_rate": len(cat_success) / len(cat_results) if cat_results else 0,
                "avg_hallucination": statistics.mean([r.hallucination_score for r in cat_success]) if cat_success else 0,
                "avg_coherence": statistics.mean([r.coherence_score for r in cat_success]) if cat_success else 0,
            }

        # Détecter les hallucinations
        hallucinations_detected = [
            {
                "query": r.query,
                "model": r.model,
                "score": r.hallucination_score,
                "response": r.response
            }
            for r in successful if r.hallucination_score > 0.5
        ]

        # Réponses cohérentes
        coherent_responses = [
            {
                "query": r.query,
                "model": r.model,
                "coherence": r.coherence_score,
                "response": r.response
            }
            for r in successful if r.coherence_score > 0.7
        ]

        # Réponses incohérentes
        incoherent_responses = [
            {
                "query": r.query,
                "model": r.model,
                "coherence": r.coherence_score,
                "response": r.response
            }
            for r in successful if r.coherence_score < 0.3
        ]

        return ExtremeStats(
            total_queries=len(self.results),
            successful_queries=len(successful),
            failed_queries=len(failed),
            success_rate=len(successful) / len(self.results) if self.results else 0,
            avg_latency=statistics.mean(latencies) if latencies else 0,
            avg_response_length=int(statistics.mean(response_lengths)) if response_lengths else 0,
            avg_hallucination_score=statistics.mean(hallucination_scores) if hallucination_scores else 0,
            avg_coherence_score=statistics.mean(coherence_scores) if coherence_scores else 0,
            model_stats=model_stats,
            category_stats=category_stats,
            hallucinations_detected=hallucinations_detected,
            coherent_responses=coherent_responses,
            incoherent_responses=incoherent_responses
        )

    def print_stats(self, stats: ExtremeStats):
        """Affiche les statistiques extrêmes"""
        print("\n" + "=" * 70)
        print("📊 RÉSULTATS DU BENCHMARK EXTREME")
        print("=" * 70)

        duration = (self.end_time - self.start_time).total_seconds()

        print(f"\n⏱️ Durée: {duration:.1f}s")
        print(f"\n📈 Statistiques générales:")
        print(f"   Total queries: {stats.total_queries}")
        print(f"   ✅ Succès: {stats.successful_queries}")
        print(f"   ❌ Échecs: {stats.failed_queries}")
        print(f"   📊 Success rate: {stats.success_rate:.2%}")
        print(f"\n⚡ Latence (ms):")
        print(f"   Moyenne: {stats.avg_latency:.1f}")
        print(f"\n📝 Réponse:")
        print(f"   Longueur moyenne: {stats.avg_response_length} chars")
        print(f"\n🎯 Qualité:")
        print(f"   Hallucination avg: {stats.avg_hallucination_score:.2f} (0=bon, 1=mauvais)")
        print(f"   Cohérence avg: {stats.avg_coherence_score:.2f} (1=excellent)")

        print(f"\n🤖 Stats par modèle:")
        for model, model_stat in stats.model_stats.items():
            print(f"\n   {model}:")
            print(f"     Succès: {model_stat['success']}/{model_stat['total']} ({model_stat['success_rate']:.2%})")
            print(f"     Latence moy: {model_stat['avg_latency']:.1f}ms")
            print(f"     Hallucination: {model_stat['avg_hallucination']:.2f}")
            print(f"     Cohérence: {model_stat['avg_coherence']:.2f}")

        print(f"\n📚 Stats par catégorie:")
        for category, cat_stat in stats.category_stats.items():
            print(f"\n   {category}:")
            print(f"     Succès: {cat_stat['success']}/{cat_stat['total']} ({cat_stat['success_rate']:.2%})")
            print(f"     Hallucination: {cat_stat['avg_hallucination']:.2f}")
            print(f"     Cohérence: {cat_stat['avg_coherence']:.2f}")

        if stats.hallucinations_detected:
            print(f"\n⚠️ Hallucinations détectées ({len(stats.hallucinations_detected)}):")
            for i, hall in enumerate(stats.hallucinations_detected[:5], 1):
                print(f"   {i}. {hall['query'][:50]}... (score: {hall['score']:.2f})")
                print(f"      Response: {hall['response'][:100]}...")

        if stats.incoherent_responses:
            print(f"\n❌ Réponses incohérentes ({len(stats.incoherent_responses)}):")
            for i, inc in enumerate(stats.incoherent_responses[:5], 1):
                print(f"   {i}. {inc['query'][:50]}... (coherence: {inc['coherence']:.2f})")
                print(f"      Response: {inc['response'][:100]}...")

        if stats.coherent_responses:
            print(f"\n✅ Réponses cohérentes ({len(stats.coherent_responses)}):")
            for i, coh in enumerate(stats.coherent_responses[:5], 1):
                print(f"   {i}. {coh['query'][:50]}... (coherence: {coh['coherence']:.2f})")

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
                    "response": r.response,
                    "hallucination_score": r.hallucination_score,
                    "coherence_score": r.coherence_score,
                    "error": r.error
                }
                for r in self.results
            ],
            "stats": self.get_stats().__dict__
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Résultats sauvegardés: {filename}")

async def main():
    print("=" * 70)
    print("🧪 BENCHMARK EXTREME - 50 QUESTIONS DOCTORALES")
    print("=" * 70)

    os.makedirs("output", exist_ok=True)

    # PinkyBrain
    benchmark = ExtremeBenchmark("PinkyBrain Extreme")
    stats = await benchmark.run_benchmark()

    # Afficher les stats
    benchmark.print_stats(stats)

    # Sauvegarder
    benchmark.save_results("output/extreme_benchmark.json")

    print("\n" + "=" * 70)
    print("✅ BENCHMARK EXTREME TERMINÉ !")
    print("=" * 70)

    print("\n📊 Résumé:")
    print(f"   Success Rate: {stats.success_rate:.2%}")
    print(f"   Hallucination Score: {stats.avg_hallucination_score:.2f}")
    print(f"   Cohérence Score: {stats.avg_coherence_score:.2f}")

    if stats.avg_hallucination_score > 0.5:
        print("\n⚠️ ATTENTION: Score d'hallucination élevé !")
    elif stats.avg_coherence_score < 0.5:
        print("\n⚠️ ATTENTION: Faible cohérence !")
    else:
        print("\n✅ Bonne performance globale !")

if __name__ == '__main__':
    asyncio.run(main())