#!/usr/bin/env python3
"""
🎯 MODEL SPECIALIST — PinkyBrain v5
====================================

Système de spécialités et sélection multi-LLM.

Permet de:
1. Déclarer les spécialités de chaque modèle (code, raisonnement, créatif, général, etc.)
2. Sélectionner un ou plusieurs modèles par spécialité
3. Combiner les réponses de plusieurs modèles (fusion, vote, chaîne)
4. Auto-détecter la spécialité d'un prompt pour router vers le bon modèle
5. Permettre à l'utilisateur de forcer la spécialité ou le(s) modèle(s)

Architecture:
- ModelSpecialty: enum des spécialités (CODE, REASONING, CREATIVE, MATH, CONVERSATION, GENERAL, MULTILINGUAL, VISION, AUDIO)
- ModelProfile: profil complet d'un modèle (nom, spécialités, forces, limites, taille, vitesse)
- SpecialistRouter: routeur intelligent qui sélectionne le(s) meilleur(s) modèle(s) selon le prompt
- MultiModelQuery: exécution multi-modèles avec stratégies de fusion

Usage via API:
  POST /api/query {"prompt": "...", "specialty": "code"}           → route vers le meilleur modèle code
  POST /api/query {"prompt": "...", "models": ["deepseek", "qwen"]} → interroge ces modèles spécifiques
  POST /api/query {"prompt": "...", "specialties": ["code", "reasoning"]} → interroge les meilleurs de chaque spécialité
  POST /api/multi  {"prompt": "...", "mode": "vote"}               → multi-LLM avec vote majoritaire
  POST /api/multi  {"prompt": "...", "mode": "chain"}              → chaîne séquentielle
  POST /api/multi  {"prompt": "...", "mode": "fuse"}              → fusion des réponses
  GET  /api/specialties                                           → liste les spécialités disponibles
  GET  /api/specialties/{name}/models                              → modèles pour une spécialité
"""

import asyncio
import re
import time
import json
import logging
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger('PinkyBrain.Specialist')

# ============================================================================
# CONSTANTES
# ============================================================================

MAX_PROMPT_LENGTH = 50000
SPECIALTY_PATTERN = re.compile(r'^[a-zA-Z0-9._:/-]+$')


# ============================================================================
# SPÉCIALITÉS
# ============================================================================

class ModelSpecialty(Enum):
    """Spécialités de modèles reconnues par PinkyBrain."""
    CODE = "code"
    REASONING = "reasoning"
    CREATIVE = "creative"
    MATH = "math"
    CONVERSATION = "conversation"
    GENERAL = "general"
    MULTILINGUAL = "multilingual"
    VISION = "vision"
    AUDIO = "audio"
    EMBEDDING = "embedding"
    TOOL_USE = "tool_use"
    INSTRUCTION = "instruction"


# Mots-clés pour auto-détection de spécialité depuis un prompt
SPECIALTY_KEYWORDS: Dict[ModelSpecialty, List[str]] = {
    ModelSpecialty.CODE: [
        'code', 'program', 'script', 'debug', 'implement', 'function',
        'class ', 'def ', 'async ', 'import ', 'module', 'api', 'bug',
        'compile', 'syntax', 'variable', 'loop', 'algorithm', 'refactor',
        'python', 'javascript', 'rust', 'golang', 'typescript', 'html', 'css',
        'docker', 'deploy', 'git', 'github', 'gitlab', 'test unitaire', 'test unit',
        'function', 'parse', 'format', 'convert', 'extract', 'generate',
        'regex', 'json', 'xml', 'sql', 'database', 'query',
        'web scraper', 'scraper', 'crawler', 'bot',
        'security vulnerability', 'pentest', 'vulnerability', 'fastapi', 'flask', 'django',
    ],
    ModelSpecialty.REASONING: [
        'explain', 'why', 'how does', 'analyze', 'compare', 'what if',
        'reason', 'logic', 'deduce', 'infer', 'argument', 'fallacy',
        'philosophy', 'ethical', 'debate', 'pros and cons', 'evaluate',
        'critique', 'hypothesis', 'cause and effect',
    ],
    ModelSpecialty.CREATIVE: [
        'write', 'story', 'poem', 'creative', 'imagine', 'design',
        'fiction', 'novel', 'song', 'lyrics', 'character', 'dialogue',
        'scenario', 'worldbuild', 'plot', 'narrative', 'brainstorm',
        'invent', 'compose',
    ],
    ModelSpecialty.MATH: [
        'calculate', 'equation', 'formula', 'theorem', 'proof',
        'integral', 'derivative', 'matrix', 'vector', 'probability',
        'statistics', 'algebra', 'geometry', 'calculus', 'optimization',
        'linear', 'polynomial', 'solve for',
    ],
    ModelSpecialty.CONVERSATION: [
        'chat', 'talk', 'discuss', 'conversation', 'hello', 'hi',
        'how are you', 'help me', 'suggest', 'recommend', 'advice',
        'opinion', 'what do you think', 'tell me about',
    ],
    ModelSpecialty.GENERAL: [
        'what is', 'who is', 'when did', 'where is', 'define', 'describe',
        'summarize', 'overview', 'list', 'information about',
    ],
    ModelSpecialty.MULTILINGUAL: [
        'translate', 'traduis', 'traduire', 'traduction', 'translation',
        'language', 'langue', 'idioma', 'english', 'french', 'spanish',
        'japanese', 'chinese', 'arabic', 'german', 'portuguese',
        'en français', 'in english', 'en español',
    ],
    ModelSpecialty.VISION: [
        'image', 'picture', 'photo', 'screenshot', 'visual',
        'see', 'look at', 'describe what you see', 'ocr',
        'diagram', 'chart', 'graph',
    ],
    ModelSpecialty.TOOL_USE: [
        'tool', 'function call', 'api call', 'execute', 'run command',
        'shell', 'terminal', 'search web', 'fetch url',
        'use the api', 'call the api', 'rest api', 'graphql',
    ],
    ModelSpecialty.INSTRUCTION: [
        'instruction', 'step by step', 'tutorial', 'guide', 'how to',
        'follow these', 'do the following',
    ],
}


# ============================================================================
# PROFIL DE MODÈLE
# ============================================================================

@dataclass
class ModelProfile:
    """Profil complet d'un modèle avec ses spécialités et caractéristiques."""
    name: str
    specialties: List[ModelSpecialty] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    size_category: str = "medium"  # tiny, small, medium, large, xl
    speed_rating: int = 5  # 1 (very slow) to 10 (very fast)
    quality_rating: int = 5  # 1 (poor) to 10 (excellent)
    context_window: int = 8192  # tokens
    languages: List[str] = field(default_factory=lambda: ["en"])
    provider: str = "ollama"  # ollama, openai, anthropic, custom
    metadata: Dict[str, Any] = field(default_factory=dict)

    def has_specialty(self, specialty: ModelSpecialty) -> bool:
        return specialty in self.specialties

    def specialty_score(self, specialty: ModelSpecialty) -> float:
        """Score de pertinence pour une spécialité (0.0 à 1.0)."""
        if not self.has_specialty(specialty):
            return 0.0
        # Combinaison: qualité × vitesse × position dans la liste
        base = 0.5
        # Plus c'est haut dans la liste, plus c'est spécialisé
        try:
            position_bonus = (len(self.specialties) - self.specialties.index(specialty)) / len(self.specialties)
        except ValueError:
            position_bonus = 0.0
        quality_bonus = self.quality_rating / 20.0  # max 0.5
        speed_bonus = self.speed_rating / 40.0  # max 0.25
        return min(1.0, base + position_bonus * 0.15 + quality_bonus + speed_bonus)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "specialties": [s.value for s in self.specialties],
            "strengths": self.strengths,
            "limitations": self.limitations,
            "size_category": self.size_category,
            "speed_rating": self.speed_rating,
            "quality_rating": self.quality_rating,
            "context_window": self.context_window,
            "languages": self.languages,
            "provider": self.provider,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModelProfile':
        specialties = []
        for s in data.get("specialties", []):
            try:
                specialties.append(ModelSpecialty(s))
            except ValueError:
                pass
        return cls(
            name=data["name"],
            specialties=specialties,
            strengths=data.get("strengths", []),
            limitations=data.get("limitations", []),
            size_category=data.get("size_category", "medium"),
            speed_rating=data.get("speed_rating", 5),
            quality_rating=data.get("quality_rating", 5),
            context_window=data.get("context_window", 8192),
            languages=data.get("languages", ["en"]),
            provider=data.get("provider", "ollama"),
        )


# ============================================================================
# PROFILS PAR DÉFAUT — Modèles connus
# ============================================================================

DEFAULT_PROFILES: List[Dict[str, Any]] = [
    {
        "name": "glm-5.1:cloud",
        "specialties": ["general", "conversation", "reasoning", "multilingual"],
        "strengths": ["Excellent en français", "Bon raisonnement", "Multilingue", "Suivi d'instructions"],
        "limitations": ["Moins bon en code complexe", "Créatif moyen"],
        "size_category": "large",
        "speed_rating": 7,
        "quality_rating": 8,
        "context_window": 131072,
        "languages": ["en", "fr", "es", "de", "zh", "ja"],
        "provider": "ollama",
    },
    {
        "name": "deepseek-v3.1:671b-cloud",
        "specialties": ["code", "reasoning", "math", "tool_use"],
        "strengths": ["Code exceptionnel", "Raisonnement avancé", "Maths", "Appels d'outils"],
        "limitations": ["Plus lent", "Moins créatif", "Anglais dominant"],
        "size_category": "xl",
        "speed_rating": 5,
        "quality_rating": 10,
        "context_window": 131072,
        "languages": ["en", "zh"],
        "provider": "ollama",
    },
    {
        "name": "qwen3-coder-next:cloud",
        "specialties": ["code", "multilingual", "instruction"],
        "strengths": ["Code multilingue", "Bon suivi d'instructions", "Rapide"],
        "limitations": ["Raisonnement moyen", "Pas optimal pour créatif"],
        "size_category": "large",
        "speed_rating": 8,
        "quality_rating": 7,
        "context_window": 65536,
        "languages": ["en", "zh", "ja", "ko", "fr", "de", "es"],
        "provider": "ollama",
    },
    {
        # Alias courants
        "name": "qwen3:8b",
        "specialties": ["code", "general", "multilingual"],
        "strengths": ["Rapide", "Bon rapport qualité/vitesse", "Multilingue"],
        "limitations": ["Raisonnement limité", "Contexte court"],
        "size_category": "small",
        "speed_rating": 9,
        "quality_rating": 5,
        "context_window": 32768,
        "languages": ["en", "zh"],
        "provider": "ollama",
    },
    {
        "name": "llama3.1:8b",
        "specialties": ["general", "conversation", "instruction"],
        "strengths": ["Rapide", "Bon pour conversation", "Suivi d'instructions"],
        "limitations": ["Code basique", "Raisonnement limité"],
        "size_category": "small",
        "speed_rating": 9,
        "quality_rating": 5,
        "context_window": 8192,
        "languages": ["en"],
        "provider": "ollama",
    },
    {
        "name": "mistral:7b",
        "specialties": ["general", "conversation", "code", "multilingual"],
        "strengths": ["Bon en français", "Code correct", "Rapide"],
        "limitations": ["Raisonnement moyen", "Contexte court"],
        "size_category": "small",
        "speed_rating": 9,
        "quality_rating": 6,
        "context_window": 32768,
        "languages": ["en", "fr", "de", "es", "it"],
        "provider": "ollama",
    },
    {
        "name": "codellama:13b",
        "specialties": ["code", "instruction"],
        "strengths": ["Code spécialisé", "Completion de code", "Inférence"],
        "limitations": ["Pas créatif", "Conversation limitée"],
        "size_category": "medium",
        "speed_rating": 7,
        "quality_rating": 7,
        "context_window": 16384,
        "languages": ["en"],
        "provider": "ollama",
    },
    {
        "name": "gpt-4o",
        "specialties": ["general", "reasoning", "code", "creative", "vision", "multilingual", "tool_use"],
        "strengths": ["Très polyvalent", "Vision", "Outils", "Raisonnement fort"],
        "limitations": ["Coûteux", "Propriétaire"],
        "size_category": "xl",
        "speed_rating": 6,
        "quality_rating": 9,
        "context_window": 128000,
        "languages": ["en", "fr", "es", "de", "zh", "ja", "ko", "pt", "ar"],
        "provider": "openai",
    },
    {
        "name": "claude-sonnet-4-20250514",
        "specialties": ["reasoning", "code", "creative", "conversation", "multilingual", "tool_use"],
        "strengths": ["Raisonnement excellent", "Code", "Créatif", "Long contexte"],
        "limitations": ["Coûteux", "Pas de vision"],
        "size_category": "xl",
        "speed_rating": 6,
        "quality_rating": 9,
        "context_window": 200000,
        "languages": ["en", "fr", "es", "de", "zh", "ja"],
        "provider": "anthropic",
    },
]


# ============================================================================
# STRATÉGIES MULTI-MODÈLES
# ============================================================================

class MultiModelMode(Enum):
    """Modes de requête multi-modèles."""
    SINGLE = "single"         # Un seul modèle (le meilleur pour la spécialité)
    VOTE = "vote"              # Interroge plusieurs modèles, vote majoritaire
    CHAIN = "chain"            # Chaîne séquentielle (sortie de l'un → entrée du suivant)
    FUSE = "fuse"              # Fusion intelligente des réponses
    COMPARE = "compare"        # Retourne les réponses séparées pour comparaison
    SPECIALIST = "specialist"  # Chaque spécialité → son meilleur modèle


@dataclass
class MultiModelResult:
    """Résultat d'une requête multi-modèles."""
    response: str
    models_used: List[str] = field(default_factory=list)
    mode: MultiModelMode = MultiModelMode.SINGLE
    specialty: Optional[str] = None
    responses: Dict[str, str] = field(default_factory=dict)  # model → response (si multi)
    confidence: float = 0.0
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "response": self.response,
            "models_used": self.models_used,
            "mode": self.mode.value,
            "confidence": round(self.confidence, 2),
            "latency_ms": round(self.latency_ms, 1),
        }
        if self.specialty:
            d["specialty"] = self.specialty
        if self.responses:
            d["responses"] = self.responses
        if self.metadata:
            d["metadata"] = self.metadata
        return d


# ============================================================================
# ROUTEUR DE SPÉCIALITÉS
# ============================================================================

class SpecialistRouter:
    """Routeur intelligent basé sur les spécialités des modèles.

    Fonctionnalités:
    - Auto-détection de spécialité depuis un prompt
    - Sélection du meilleur modèle par spécialité
    - Sélection multi-modèles (un par spécialité détectée)
    - Profils personnalisables (ajout/suppression de modèles)
    - Considération du contexte (langue, taille, vitesse)
    """

    def __init__(self, config: Dict = None):
        config = config or {}
        self._profiles: Dict[str, ModelProfile] = {}
        self._available_models: Set[str] = set()

        # Charger les profils par défaut
        for pd in DEFAULT_PROFILES:
            profile = ModelProfile.from_dict(pd)
            self._profiles[profile.name] = profile

        # Charger les profils custom depuis la config
        custom_profiles = config.get("model_profiles", [])
        for cp in custom_profiles:
            profile = ModelProfile.from_dict(cp)
            self._profiles[profile.name] = profile

        # Langue préférée (pour le routage multilingue)
        self._preferred_language = config.get("preferred_language", "fr")

        # Seuil de confiance pour l'auto-détection
        self._detection_threshold = config.get("detection_threshold", 0.10)

    def register_model(self, profile: ModelProfile):
        """Enregistrer un nouveau modèle avec son profil."""
        if not profile.name or not SPECIALTY_PATTERN.match(profile.name):
            raise ValueError(f"Invalid model name: {profile.name}")
        self._profiles[profile.name] = profile
        logger.info(f"🎯 Model registered: {profile.name} — specialties: {[s.value for s in profile.specialties]}")

    def unregister_model(self, name: str) -> bool:
        """Supprimer un modèle du registre."""
        if name in self._profiles:
            del self._profiles[name]
            logger.info(f"🎯 Model unregistered: {name}")
            return True
        return False

    def set_available_models(self, models: List[str]):
        """Mettre à jour la liste des modèles actuellement disponibles."""
        self._available_models = set(models)

    def detect_specialties(self, prompt: str) -> List[Tuple[ModelSpecialty, float]]:
        """Auto-détecter les spécialités pertinentes depuis un prompt.

        Returns:
            Liste de (specialty, confidence) triée par confiance décroissante.
        """
        prompt_lower = prompt.lower()
        scores: Dict[ModelSpecialty, float] = {}

        for specialty, keywords in SPECIALTY_KEYWORDS.items():
            match_count = 0
            total_keywords = len(keywords)
            specific_matches = 0  # More specific/longer keywords = stronger signal
            # Mots-clés ambigus qui ne comptent pas comme spécifiques
            AMBIGUOUS_KEYWORDS = {'write', 'how', 'what', 'make', 'use', 'run', 'test', 'new'}
            for kw in keywords:
                if kw in prompt_lower:
                    match_count += 1
                    # Longer keywords are more specific (python, javascript vs hi, what)
                    # Mais les mots ambigus comme "write" ne comptent pas comme spécifiques
                    if len(kw) > 4 and kw not in AMBIGUOUS_KEYWORDS:
                        specific_matches += 1
            if match_count > 0:
                # Score: base density + bonus for specific matches
                raw_score = match_count / total_keywords
                # Specific matches get much higher weight
                specificity_bonus = min(0.5, specific_matches * 0.12)
                scores[specialty] = min(1.0, raw_score + specificity_bonus)

        # Si rien détecté, c'est probablement général ou conversation
        if not scores:
            # Check si c'est une courte question conversationnelle
            if len(prompt) < 100 and ('?' in prompt or any(g in prompt_lower for g in ['hello', 'hi', 'salut', 'bonjour', 'hey'])):
                scores[ModelSpecialty.CONVERSATION] = 0.5
            else:
                scores[ModelSpecialty.GENERAL] = 0.3

        # Trier par score
        sorted_specialties = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        # Filtrer par seuil
        result = [(s, score) for s, score in sorted_specialties if score >= self._detection_threshold]

        # Toujours garder au moins une spécialité
        if not result and sorted_specialties:
            result = [sorted_specialties[0]]

        return result

    def select_best_model(self, specialty: ModelSpecialty, available: List[str] = None) -> Optional[str]:
        """Sélectionner le meilleur modèle pour une spécialité.

        Args:
            specialty: La spécialité cible
            available: Liste de modèles disponibles (si None, utilise self._available_models)

        Returns:
            Nom du meilleur modèle, ou None si aucun ne correspond
        """
        pool = available or list(self._available_models)
        if not pool:
            # Fallback: utiliser tous les profils connus
            pool = list(self._profiles.keys())

        candidates = []
        for name in pool:
            if name in self._profiles:
                profile = self._profiles[name]
                score = profile.specialty_score(specialty)
                if score > 0:
                    candidates.append((name, score))

        if not candidates:
            return None

        # Trier par score de spécialité
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    def select_models_for_specialties(
        self,
        specialties: List[ModelSpecialty],
        available: List[str] = None,
        max_models: int = 4
    ) -> List[str]:
        """Sélectionner le meilleur modèle pour chaque spécialité.

        Returns:
            Liste de noms de modèles (un par spécialité, dédupliquée).
        """
        pool = available or list(self._available_models)
        selected = []
        seen = set()

        for specialty in specialties:
            best = self.select_best_model(specialty, pool)
            if best and best not in seen:
                selected.append(best)
                seen.add(best)
                if len(selected) >= max_models:
                    break

        return selected

    def select_models_by_names(self, names: List[str]) -> List[str]:
        """Sélectionner des modèles par nom (avec fuzzy matching).

        Supporte les noms partiels: 'deepseek' → 'deepseek-v3.1:671b-cloud'
        """
        result = []
        for query in names:
            # Match exact d'abord
            if query in self._profiles:
                result.append(query)
                continue

            # Fuzzy: nom partiel dans un profil
            query_lower = query.lower()
            matches = [
                name for name in self._profiles
                if query_lower in name.lower()
            ]
            if matches:
                # Prendre le premier match (le plus court = le plus pertinent)
                matches.sort(key=len)
                result.append(matches[0])
            else:
                logger.warning(f"🎯 No model matching '{query}'")

        return result

    def get_specialty_models(self, specialty: ModelSpecialty) -> List[Dict[str, Any]]:
        """Lister tous les modèles avec une spécialité donnée."""
        results = []
        for name, profile in self._profiles.items():
            if profile.has_specialty(specialty):
                results.append({
                    **profile.to_dict(),
                    "specialty_score": profile.specialty_score(specialty),
                })
        results.sort(key=lambda x: x["specialty_score"], reverse=True)
        return results

    def get_all_specialties(self) -> Dict[str, List[str]]:
        """Lister toutes les spécialités et leurs modèles associés."""
        result = {}
        for specialty in ModelSpecialty:
            models = self.get_specialty_models(specialty)
            if models:
                result[specialty.value] = [m["name"] for m in models]
        return result

    def get_profile(self, model_name: str) -> Optional[ModelProfile]:
        """Récupérer le profil d'un modèle."""
        return self._profiles.get(model_name)

    def route(self, prompt: str, available: List[str] = None,
              specialty: str = None, models: List[str] = None,
              specialties: List[str] = None) -> Dict[str, Any]:
        """Route principal — sélectionne le(s) meilleur(s) modèle(s) pour un prompt.

        Args:
            prompt: Le prompt utilisateur
            available: Modèles disponibles
            specialty: Forcer une spécialité (ex: "code")
            models: Forcer des modèles spécifiques (ex: ["deepseek", "qwen"])
            specialties: Forcer plusieurs spécialités (ex: ["code", "reasoning"])

        Returns:
            Dict avec:
              - models: liste des modèles sélectionnés
              - detected_specialties: spécialités détectées
              - forced: True si l'utilisateur a forcé le choix
              - reasoning: explication du routage
        """
        pool = available or list(self._available_models)

        # 1. Si l'utilisateur force des modèles spécifiques → priorité absolue
        if models:
            selected = self.select_models_by_names(models)
            return {
                "models": selected,
                "detected_specialties": [],
                "forced": True,
                "reasoning": f"User forced models: {selected}",
            }

        # 2. Si l'utilisateur force une spécialité
        if specialty:
            try:
                spec = ModelSpecialty(specialty)
            except ValueError:
                return {
                    "models": pool[:1] if pool else [],
                    "detected_specialties": [],
                    "forced": True,
                    "reasoning": f"Unknown specialty '{specialty}', falling back to first available",
                }
            best = self.select_best_model(spec, pool)
            return {
                "models": [best] if best else (pool[:1] if pool else []),
                "detected_specialties": [(spec.value, 1.0)],
                "forced": True,
                "reasoning": f"User forced specialty '{specialty}', selected: {best}",
            }

        # 3. Si l'utilisateur force plusieurs spécialités
        if specialties:
            specs = []
            for s in specialties:
                try:
                    specs.append(ModelSpecialty(s))
                except ValueError:
                    pass
            if specs:
                selected = self.select_models_for_specialties(specs, pool)
                return {
                    "models": selected,
                    "detected_specialties": [(s.value, 1.0) for s in specs],
                    "forced": True,
                    "reasoning": f"User forced specialties {[s.value for s in specs]}, selected: {selected}",
                }

        # 4. Auto-détection
        detected = self.detect_specialties(prompt)
        if not detected:
            # Fallback: premier modèle disponible
            return {
                "models": pool[:1] if pool else [],
                "detected_specialties": [],
                "forced": False,
                "reasoning": "No specialty detected, using first available model",
            }

        top_specialties = [s for s, _ in detected[:3]]  # Top 3 spécialités
        selected = self.select_models_for_specialties(top_specialties, pool, max_models=3)

        reasoning_parts = []
        for spec, score in detected[:3]:
            reasoning_parts.append(f"{spec.value}({score:.0%})")

        return {
            "models": selected,
            "detected_specialties": [(s.value, round(score, 2)) for s, score in detected[:3]],
            "forced": False,
            "reasoning": f"Auto-detected: {', '.join(reasoning_parts)} → {selected}",
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "available_models": list(self._available_models),
            "registered_profiles": list(self._profiles.keys()),
            "specialties": self.get_all_specialties(),
            "preferred_language": self._preferred_language,
        }


# ============================================================================
# EXÉCUTEUR MULTI-MODÈLES
# ============================================================================

class MultiModelExecutor:
    """Exécute des requêtes sur plusieurs modèles avec des stratégies de fusion.

    Ne gère PAS les appels HTTP directement — reçoit un callback de requête.
    Cela permet de l'utiliser avec n'importe quel backend (HTTP, WebSocket, etc.).
    """

    def __init__(self, query_fn=None, config: Dict = None):
        """
        Args:
            query_fn: async callable(model: str, prompt: str) -> Dict
                      Doit retourner {"response": str, ...}
            config: Configuration
        """
        self._query_fn = query_fn
        config = config or {}
        self._max_concurrent = config.get("max_concurrent", 3)
        self._chain_prompt_template = config.get(
            "chain_prompt_template",
            "Based on this analysis:\n\n{previous}\n\nNow provide your own analysis of:\n\n{prompt}"
        )
        self._fuse_prompt_template = config.get(
            "fuse_prompt_template",
            "Synthesize the following analyses into one comprehensive response:\n\n{responses}"
        )

    async def execute(
        self,
        prompt: str,
        models: List[str],
        mode: MultiModelMode = MultiModelMode.SINGLE,
        query_fn=None
    ) -> MultiModelResult:
        """Exécuter une requête multi-modèles.

        Args:
            prompt: Le prompt
            models: Liste des modèles à interroger
            mode: Stratégie de fusion
            query_fn: Override du query_fn par défaut

        Returns:
            MultiModelResult avec la réponse fusionnée et les métadonnées
        """
        qfn = query_fn or self._query_fn
        if not qfn:
            raise RuntimeError("No query function provided")

        start = time.time()

        if mode == MultiModelMode.SINGLE or len(models) == 1:
            model = models[0] if models else "auto"
            result = await qfn(model, prompt)
            elapsed = (time.time() - start) * 1000
            return MultiModelResult(
                response=result.get("response", ""),
                models_used=[model],
                mode=mode,
                latency_ms=elapsed,
                confidence=0.7,
            )

        elif mode == MultiModelMode.VOTE:
            result = await self._execute_vote(prompt, models, qfn)
            result.latency_ms = (time.time() - start) * 1000
            return result

        elif mode == MultiModelMode.CHAIN:
            result = await self._execute_chain(prompt, models, qfn)
            result.latency_ms = (time.time() - start) * 1000
            return result

        elif mode == MultiModelMode.FUSE:
            result = await self._execute_fuse(prompt, models, qfn)
            result.latency_ms = (time.time() - start) * 1000
            return result

        elif mode == MultiModelMode.COMPARE:
            result = await self._execute_compare(prompt, models, qfn)
            result.latency_ms = (time.time() - start) * 1000
            return result

        elif mode == MultiModelMode.SPECIALIST:
            result = await self._execute_specialist(prompt, models, qfn)
            result.latency_ms = (time.time() - start) * 1000
            return result

        else:
            # Fallback: single
            model = models[0] if models else "auto"
            r = await qfn(model, prompt)
            elapsed = (time.time() - start) * 1000
            return MultiModelResult(
                response=r.get("response", ""),
                models_used=[model],
                mode=mode,
                latency_ms=elapsed,
            )

    async def _execute_vote(self, prompt: str, models: List[str], qfn) -> MultiModelResult:
        """Vote majoritaire — interroge tous les modèles, prend la réponse la plus fréquente/similaire."""
        responses = await self._query_all(prompt, models, qfn)

        if not responses:
            return MultiModelResult(response="", models_used=models, mode=MultiModelMode.VOTE, confidence=0.0)

        if len(responses) == 1:
            model, resp = list(responses.items())[0]
            return MultiModelResult(
                response=resp, models_used=[model], mode=MultiModelMode.VOTE,
                confidence=1.0, responses=responses,
            )

        # Trouver la réponse la plus longue/complète comme "gagnante" du vote
        # (Heuristique simple — un vrai système comparerait le contenu)
        best_model = max(responses.keys(), key=lambda m: len(responses[m]))
        best_response = responses[best_model]

        # Confiance basée sur l'accord (longueurs similaires = probablement d'accord)
        lengths = [len(r) for r in responses.values()]
        avg_len = sum(lengths) / len(lengths)
        variance = sum((l - avg_len) ** 2 for l in lengths) / len(lengths)
        agreement = max(0.0, 1.0 - (variance / (avg_len ** 2 + 1)))
        agreement = min(1.0, agreement)

        return MultiModelResult(
            response=best_response,
            models_used=list(responses.keys()),
            mode=MultiModelMode.VOTE,
            responses=responses,
            confidence=agreement,
            metadata={"vote_method": "longest_response", "agreement": round(agreement, 2)},
        )

    async def _execute_chain(self, prompt: str, models: List[str], qfn) -> MultiModelResult:
        """Chaîne séquentielle — chaque modèle enrichit la réponse du précédent."""
        current_prompt = prompt
        all_responses = {}

        for model in models:
            result = await qfn(model, current_prompt)
            response = result.get("response", "")
            all_responses[model] = response

            # Le prochain modèle reçoit la sortie du précédent
            if response and model != models[-1]:
                current_prompt = self._chain_prompt_template.format(
                    previous=response[:2000],  # Limiter pour ne pas exploser le contexte
                    prompt=prompt,
                )

        # La réponse finale est celle du dernier modèle
        final_response = all_responses.get(models[-1], "") if models else ""

        return MultiModelResult(
            response=final_response,
            models_used=models,
            mode=MultiModelMode.CHAIN,
            responses=all_responses,
            confidence=0.6,
            metadata={"chain_length": len(models)},
        )

    async def _execute_fuse(self, prompt: str, models: List[str], qfn) -> MultiModelResult:
        """Fusion intelligente — interroge tous les modèles en parallèle, puis fusionne."""
        responses = await self._query_all(prompt, models, qfn)

        if not responses:
            return MultiModelResult(response="", models_used=models, mode=MultiModelMode.FUSE, confidence=0.0)

        if len(responses) == 1:
            model, resp = list(responses.items())[0]
            return MultiModelResult(response=resp, models_used=[model], mode=MultiModelMode.FUSE, confidence=1.0)

        # Fusion simple: concaténer avec des séparateurs
        # (Une vraie fusion utiliserait un LLM pour synthétiser)
        parts = []
        for model, response in responses.items():
            short_name = model.split(':')[0].split('/')[-1]
            parts.append(f"**{short_name}:**\n{response}")

        fused = "\n\n---\n\n".join(parts)

        # Si on a un query_fn, on peut l'utiliser pour synthétiser
        if len(models) > 1 and qfn:
            # Le premier modèle synthétise
            synth_prompt = self._fuse_prompt_template.format(
                responses=fused[:3000],  # Limiter
            )
            synth_result = await qfn(models[0], synth_prompt)
            synth_response = synth_result.get("response", "")
            if synth_response:
                fused = synth_response

        return MultiModelResult(
            response=fused,
            models_used=list(responses.keys()),
            mode=MultiModelMode.FUSE,
            responses=responses,
            confidence=0.7,
            metadata={"fusion_method": "synthesis"},
        )

    async def _execute_compare(self, prompt: str, models: List[str], qfn) -> MultiModelResult:
        """Comparaison — retourne les réponses séparées pour comparaison manuelle."""
        responses = await self._query_all(prompt, models, qfn)

        if not responses:
            return MultiModelResult(response="", models_used=models, mode=MultiModelMode.COMPARE, confidence=0.0)

        # Format de comparaison lisible
        parts = []
        for model, response in responses.items():
            short_name = model.split(':')[0].split('/')[-1]
            parts.append(f"## {short_name}\n\n{response}")

        combined = "\n\n---\n\n".join(parts)

        return MultiModelResult(
            response=combined,
            models_used=list(responses.keys()),
            mode=MultiModelMode.COMPARE,
            responses=responses,
            confidence=0.5,
        )

    async def _execute_specialist(self, prompt: str, models: List[str], qfn) -> MultiModelResult:
        """Chaque modèle répond avec sa spécialité, puis fusion."""
        # Même que fuse pour l'instant — la spécialisation est dans la sélection
        return await self._execute_fuse(prompt, models, qfn)

    async def _query_all(self, prompt: str, models: List[str], qfn) -> Dict[str, str]:
        """Interroger tous les modèles en parallèle (avec concurrence limitée)."""
        semaphore = asyncio.Semaphore(self._max_concurrent)

        async def _query_one(model: str) -> Tuple[str, str]:
            async with semaphore:
                try:
                    result = await qfn(model, prompt)
                    return (model, result.get("response", ""))
                except Exception as e:
                    logger.warning(f"🎯 Query to {model} failed: {e}")
                    return (model, "")

        tasks = [_query_one(m) for m in models]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        responses = {}
        for r in results:
            if isinstance(r, Exception):
                logger.warning(f"🎯 Query exception: {r}")
                continue
            model, response = r
            if response:
                responses[model] = response

        return responses