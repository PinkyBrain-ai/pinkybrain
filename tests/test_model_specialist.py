#!/usr/bin/env python3
"""
🧪 Model Specialist Tests — PinkyBrain v5
=========================================

Tests couvrant:
- ModelSpecialty enum et détection
- ModelProfile creation, sérialisation, specialty_score
- SpecialistRouter: auto-détection, sélection, routage
- MultiModelExecutor: vote, chain, fuse, compare
- Edge cases: modèle inconnu, prompt vide, spécialité forcée
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from model_specialist import (
    ModelSpecialty, ModelProfile, SpecialistRouter,
    MultiModelMode, MultiModelResult, MultiModelExecutor,
    SPECIALTY_KEYWORDS, DEFAULT_PROFILES,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def router():
    """Router avec modèles disponibles."""
    r = SpecialistRouter()
    r.set_available_models(["glm-5.1:cloud", "deepseek-v3.1:671b-cloud", "qwen3-coder-next:cloud"])
    return r


@pytest.fixture
def executor():
    """Executor avec mock query_fn."""
    async def mock_query(model: str, prompt: str) -> dict:
        return {"response": f"[{model}] {prompt[:50]}", "model": model}

    return MultiModelExecutor(query_fn=mock_query)


@pytest.fixture
def slow_executor():
    """Executor qui simule des échecs partiels."""
    call_count = {"n": 0}

    async def mock_query(model: str, prompt: str) -> dict:
        call_count["n"] += 1
        if "fail" in model:
            raise RuntimeError("Model unavailable")
        return {"response": f"Response from {model}", "model": model}

    return MultiModelExecutor(query_fn=mock_query), call_count


# ============================================================================
# MODEL SPECIALTY
# ============================================================================

class TestModelSpecialty:
    def test_all_specialties_exist(self):
        expected = {"code", "reasoning", "creative", "math", "conversation",
                    "general", "multilingual", "vision", "audio", "embedding",
                    "tool_use", "instruction"}
        actual = {s.value for s in ModelSpecialty}
        assert expected == actual

    def test_specialty_from_value(self):
        assert ModelSpecialty("code") == ModelSpecialty.CODE
        assert ModelSpecialty("reasoning") == ModelSpecialty.REASONING

    def test_specialty_invalid_value(self):
        with pytest.raises(ValueError):
            ModelSpecialty("invalid_specialty")

    def test_specialty_keywords_coverage(self):
        """Chaque spécialité (sauf embedding/audio qui sont spéciales) a des mots-clés."""
        no_keywords_expected = {ModelSpecialty.EMBEDDING, ModelSpecialty.AUDIO}
        for spec in ModelSpecialty:
            if spec in no_keywords_expected:
                continue
            assert spec in SPECIALTY_KEYWORDS, f"No keywords for {spec}"


# ============================================================================
# MODEL PROFILE
# ============================================================================

class TestModelProfile:
    def test_create_profile(self):
        p = ModelProfile(name="test-model", specialties=[ModelSpecialty.CODE, ModelSpecialty.REASONING])
        assert p.name == "test-model"
        assert len(p.specialties) == 2
        assert p.size_category == "medium"
        assert p.speed_rating == 5

    def test_has_specialty(self):
        p = ModelProfile(name="test", specialties=[ModelSpecialty.CODE])
        assert p.has_specialty(ModelSpecialty.CODE)
        assert not p.has_specialty(ModelSpecialty.CREATIVE)

    def test_specialty_score(self):
        p = ModelProfile(name="test", specialties=[ModelSpecialty.CODE, ModelSpecialty.GENERAL],
                         quality_rating=8, speed_rating=7)
        code_score = p.specialty_score(ModelSpecialty.CODE)
        general_score = p.specialty_score(ModelSpecialty.GENERAL)
        no_score = p.specialty_score(ModelSpecialty.VISION)

        assert code_score > 0
        assert general_score > 0
        assert no_score == 0.0
        # CODE est premier dans la liste → score plus élevé
        assert code_score >= general_score

    def test_specialty_score_bounds(self):
        p = ModelProfile(name="test", specialties=[ModelSpecialty.CODE],
                         quality_rating=10, speed_rating=10)
        score = p.specialty_score(ModelSpecialty.CODE)
        assert 0.0 <= score <= 1.0

    def test_to_dict(self):
        p = ModelProfile(name="test", specialties=[ModelSpecialty.CODE],
                         strengths=["good code"], languages=["en", "fr"])
        d = p.to_dict()
        assert d["name"] == "test"
        assert d["specialties"] == ["code"]
        assert d["strengths"] == ["good code"]
        assert d["languages"] == ["en", "fr"]

    def test_from_dict(self):
        data = {
            "name": "test",
            "specialties": ["code", "reasoning"],
            "strengths": ["fast"],
            "size_category": "large",
            "speed_rating": 8,
            "quality_rating": 9,
            "context_window": 32000,
            "languages": ["en", "fr"],
            "provider": "ollama",
        }
        p = ModelProfile.from_dict(data)
        assert p.name == "test"
        assert p.specialties == [ModelSpecialty.CODE, ModelSpecialty.REASONING]
        assert p.speed_rating == 8
        assert p.context_window == 32000

    def test_from_dict_invalid_specialty_skipped(self):
        data = {"name": "test", "specialties": ["code", "nonexistent"]}
        p = ModelProfile.from_dict(data)
        assert len(p.specialties) == 1
        assert p.specialties[0] == ModelSpecialty.CODE

    def test_round_trip(self):
        p = ModelProfile(name="test", specialties=[ModelSpecialty.CODE],
                         strengths=["fast"], limitations=["not creative"],
                         speed_rating=7, quality_rating=8, context_window=64000)
        d = p.to_dict()
        p2 = ModelProfile.from_dict(d)
        assert p2.name == p.name
        assert p2.specialties == p.specialties
        assert p2.speed_rating == p.speed_rating
        assert p2.context_window == p.context_window


# ============================================================================
# DEFAULT PROFILES
# ============================================================================

class TestDefaultProfiles:
    def test_default_profiles_exist(self):
        assert len(DEFAULT_PROFILES) >= 3

    def test_default_profiles_valid(self):
        for pd in DEFAULT_PROFILES:
            p = ModelProfile.from_dict(pd)
            assert p.name
            assert len(p.specialties) > 0
            assert 1 <= p.speed_rating <= 10
            assert 1 <= p.quality_rating <= 10

    def test_glm_profile(self):
        names = [pd["name"] for pd in DEFAULT_PROFILES]
        assert "glm-5.1:cloud" in names

    def test_deepseek_profile(self):
        names = [pd["name"] for pd in DEFAULT_PROFILES]
        assert "deepseek-v3.1:671b-cloud" in names


# ============================================================================
# SPECIALIST ROUTER — ENREGISTREMENT
# ============================================================================

class TestSpecialistRouterRegistration:
    def test_register_model(self, router):
        p = ModelProfile(name="my_model", specialties=[ModelSpecialty.CODE])
        router.register_model(p)
        assert router.get_profile("my_model") is not None

    def test_register_model_invalid_name(self, router):
        with pytest.raises(ValueError):
            router.register_model(ModelProfile(name="", specialties=[ModelSpecialty.CODE]))

    def test_unregister_model(self, router):
        p = ModelProfile(name="temp_model", specialties=[ModelSpecialty.GENERAL])
        router.register_model(p)
        assert router.unregister_model("temp_model")
        assert router.get_profile("temp_model") is None

    def test_unregister_nonexistent(self, router):
        assert not router.unregister_model("nonexistent")

    def test_set_available_models(self, router):
        router.set_available_models(["model-a", "model-b"])
        d = router.to_dict()
        assert "model-a" in d["available_models"]


# ============================================================================
# SPECIALIST ROUTER — AUTO-DÉTECTION
# ============================================================================

class TestSpecialistRouterDetection:
    def test_detect_code(self, router):
        results = router.detect_specialties("Write a python function to sort a list")
        specialties = [s for s, _ in results]
        assert ModelSpecialty.CODE in specialties

    def test_detect_reasoning(self, router):
        results = router.detect_specialties("Explain why democracy leads to better outcomes")
        specialties = [s for s, _ in results]
        assert ModelSpecialty.REASONING in specialties

    def test_detect_creative(self, router):
        results = router.detect_specialties("Write a poem about the ocean at sunset")
        specialties = [s for s, _ in results]
        assert ModelSpecialty.CREATIVE in specialties

    def test_detect_math(self, router):
        results = router.detect_specialties("Calculate the integral of x^2 from 0 to 1")
        specialties = [s for s, _ in results]
        assert ModelSpecialty.MATH in specialties

    def test_detect_multilingual(self, router):
        results = router.detect_specialties("Traduis cette phrase en anglais")
        specialties = [s for s, _ in results]
        assert ModelSpecialty.MULTILINGUAL in specialties

    def test_detect_conversation(self, router):
        results = router.detect_specialties("Salut, comment ça va ?")
        specialties = [s for s, _ in results]
        assert ModelSpecialty.CONVERSATION in specialties or ModelSpecialty.GENERAL in specialties

    def test_detect_empty_fallback(self, router):
        results = router.detect_specialties("asdfghjkl xyz")
        assert len(results) >= 1  # Toujours au moins une spécialité

    def test_detect_multiple_specialties(self, router):
        """Un prompt avec du code ET du raisonnement."""
        results = router.detect_specialties(
            "Debug and explain why this Python algorithm fails: the logic seems wrong"
        )
        specialties = [s for s, _ in results]
        assert ModelSpecialty.CODE in specialties

    def test_detect_confidence_range(self, router):
        results = router.detect_specialties("Write a python script for web scraping")
        for spec, score in results:
            assert 0.0 <= score <= 1.0


# ============================================================================
# SPECIALIST ROUTER — SÉLECTION
# ============================================================================

class TestSpecialistRouterSelection:
    def test_select_best_for_code(self, router):
        model = router.select_best_model(ModelSpecialty.CODE)
        assert model is not None
        # Deepseek est le meilleur en code (quality_rating=10)
        profile = router.get_profile(model)
        assert profile is not None
        assert profile.has_specialty(ModelSpecialty.CODE)

    def test_select_best_for_general(self, router):
        model = router.select_best_model(ModelSpecialty.GENERAL)
        assert model is not None

    def test_select_best_unavailable_specialty(self, router):
        model = router.select_best_model(ModelSpecialty.VISION)
        # Aucun modèle vision dans les disponibles
        assert model is None

    def test_select_for_multiple_specialties(self, router):
        selected = router.select_models_for_specialties(
            [ModelSpecialty.CODE, ModelSpecialty.REASONING]
        )
        assert len(selected) >= 1
        assert len(selected) <= 2  # Un par spécialité max

    def test_select_by_name_exact(self, router):
        result = router.select_models_by_names(["glm-5.1:cloud"])
        assert result == ["glm-5.1:cloud"]

    def test_select_by_name_fuzzy(self, router):
        result = router.select_models_by_names(["deepseek"])
        assert len(result) == 1
        assert "deepseek" in result[0].lower()

    def test_select_by_name_unknown(self, router):
        result = router.select_models_by_names(["totally-unknown-model"])
        assert result == []

    def test_get_specialty_models(self, router):
        models = router.get_specialty_models(ModelSpecialty.CODE)
        assert len(models) > 0
        assert all("name" in m for m in models)
        assert all(m["specialty_score"] > 0 for m in models)

    def test_get_all_specialties(self, router):
        specs = router.get_all_specialties()
        assert "code" in specs
        assert "general" in specs
        assert len(specs) >= 3


# ============================================================================
# SPECIALIST ROUTER — ROUTAGE COMPLET
# ============================================================================

class TestSpecialistRouterRouting:
    def test_route_auto_code(self, router):
        result = router.route("Implement a REST API in Python")
        assert len(result["models"]) >= 1
        assert not result["forced"]

    def test_route_forced_specialty(self, router):
        result = router.route("Bonjour", specialty="code")
        assert result["forced"]
        assert len(result["models"]) >= 1

    def test_route_forced_models(self, router):
        result = router.route("Bonjour", models=["deepseek-v3.1:671b-cloud"])
        assert result["forced"]
        assert result["models"] == ["deepseek-v3.1:671b-cloud"]

    def test_route_forced_multiple_models(self, router):
        result = router.route("Test", models=["deepseek", "glm"])
        assert result["forced"]
        assert len(result["models"]) >= 1

    def test_route_forced_specialties(self, router):
        result = router.route("Test", specialties=["code", "reasoning"])
        assert result["forced"]
        assert len(result["models"]) >= 1

    def test_route_forced_invalid_specialty(self, router):
        result = router.route("Test", specialty="nonexistent")
        assert result["forced"]

    def test_route_no_available_models(self):
        r = SpecialistRouter()
        r.set_available_models([])
        result = r.route("Write code")
        # Fallback aux profils connus
        assert "models" in result

    def test_route_reasoning_in_response(self, router):
        result = router.route("Implement a REST API in Python")
        assert "reasoning" in result
        assert isinstance(result["reasoning"], str)


# ============================================================================
# MULTI-MODEL EXECUTOR
# ============================================================================

class TestMultiModelExecutor:
    @pytest.mark.asyncio
    async def test_single_model(self, executor):
        result = await executor.execute("Hello", ["glm-5.1:cloud"], MultiModelMode.SINGLE)
        assert result.response
        assert result.models_used == ["glm-5.1:cloud"]
        assert result.mode == MultiModelMode.SINGLE

    @pytest.mark.asyncio
    async def test_vote_mode(self, executor):
        result = await executor.execute(
            "Explain AI",
            ["glm-5.1:cloud", "deepseek-v3.1:671b-cloud"],
            MultiModelMode.VOTE
        )
        assert result.response
        assert len(result.models_used) == 2
        assert result.mode == MultiModelMode.VOTE
        assert len(result.responses) == 2

    @pytest.mark.asyncio
    async def test_chain_mode(self, executor):
        result = await executor.execute(
            "What is quantum computing?",
            ["glm-5.1:cloud", "deepseek-v3.1:671b-cloud"],
            MultiModelMode.CHAIN
        )
        assert result.response
        assert len(result.models_used) == 2
        assert result.mode == MultiModelMode.CHAIN
        assert result.metadata.get("chain_length") == 2

    @pytest.mark.asyncio
    async def test_fuse_mode(self, executor):
        result = await executor.execute(
            "Explain gravity",
            ["glm-5.1:cloud", "deepseek-v3.1:671b-cloud"],
            MultiModelMode.FUSE
        )
        assert result.response
        assert len(result.models_used) == 2
        assert result.mode == MultiModelMode.FUSE

    @pytest.mark.asyncio
    async def test_compare_mode(self, executor):
        result = await executor.execute(
            "What is love?",
            ["glm-5.1:cloud", "deepseek-v3.1:671b-cloud"],
            MultiModelMode.COMPARE
        )
        assert result.response
        assert len(result.models_used) == 2
        assert "---" in result.response  # Séparateur entre modèles

    @pytest.mark.asyncio
    async def test_partial_failure(self):
        """Un modèle échoue, les autres répondent."""
        async def flaky_query(model: str, prompt: str) -> dict:
            if "fail" in model:
                raise RuntimeError("Unavailable")
            return {"response": f"OK from {model}", "model": model}

        ex = MultiModelExecutor(query_fn=flaky_query)
        result = await ex.execute(
            "Test",
            ["glm-5.1:cloud", "fail-model"],
            MultiModelMode.VOTE
        )
        # Au moins un modèle a répondu
        assert len(result.models_used) >= 1
        assert "fail-model" not in result.responses

    @pytest.mark.asyncio
    async def test_empty_models_list(self, executor):
        result = await executor.execute("Test", [], MultiModelMode.SINGLE)
        # With empty list, falls back to "auto" model
        assert result.models_used == ["auto"]

    @pytest.mark.asyncio
    async def test_custom_query_fn(self):
        async def custom_query(model: str, prompt: str) -> dict:
            return {"response": f"Custom: {model}", "model": model}

        ex = MultiModelExecutor()
        result = await ex.execute("Test", ["model-a"], MultiModelMode.SINGLE, query_fn=custom_query)
        assert "Custom: model-a" in result.response

    @pytest.mark.asyncio
    async def test_latency_measured(self, executor):
        result = await executor.execute("Test", ["glm-5.1:cloud"], MultiModelMode.SINGLE)
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_no_query_fn_raises(self):
        ex = MultiModelExecutor()
        with pytest.raises(RuntimeError):
            await ex.execute("Test", ["model-a"], MultiModelMode.SINGLE)


# ============================================================================
# MULTI-MODEL RESULT
# ============================================================================

class TestMultiModelResult:
    def test_to_dict(self):
        r = MultiModelResult(
            response="Hello",
            models_used=["model-a"],
            mode=MultiModelMode.SINGLE,
            confidence=0.8,
            latency_ms=100.5,
        )
        d = r.to_dict()
        assert d["response"] == "Hello"
        assert d["models_used"] == ["model-a"]
        assert d["mode"] == "single"
        assert d["confidence"] == 0.8

    def test_to_dict_with_specialty(self):
        r = MultiModelResult(
            response="Code here",
            models_used=["deepseek"],
            mode=MultiModelMode.VOTE,
            specialty="code",
        )
        d = r.to_dict()
        assert d["specialty"] == "code"

    def test_to_dict_with_responses(self):
        r = MultiModelResult(
            response="Fused",
            models_used=["a", "b"],
            mode=MultiModelMode.FUSE,
            responses={"a": "Resp A", "b": "Resp B"},
        )
        d = r.to_dict()
        assert d["responses"] == {"a": "Resp A", "b": "Resp B"}


# ============================================================================
# EDGE CASES
# ============================================================================

class TestEdgeCases:
    def test_very_short_prompt(self, router):
        result = router.route("hi")
        assert "models" in result

    def test_very_long_prompt(self, router):
        prompt = "Write code " * 5000
        result = router.route(prompt[:50000])
        assert "models" in result

    def test_special_chars_in_prompt(self, router):
        result = router.route("Débug le script <script>alert('xss')</script>")
        assert "models" in result

    def test_custom_profiles_in_config(self):
        config = {
            "model_profiles": [
                {"name": "custom-model", "specialties": ["code", "reasoning"]}
            ]
        }
        r = SpecialistRouter(config=config)
        assert r.get_profile("custom-model") is not None

    def test_preferred_language_config(self):
        r = SpecialistRouter(config={"preferred_language": "ja"})
        assert r._preferred_language == "ja"

    @pytest.mark.asyncio
    async def test_executor_all_models_fail(self):
        async def failing_query(model: str, prompt: str) -> dict:
            raise RuntimeError("All down")

        ex = MultiModelExecutor(query_fn=failing_query)
        result = await ex.execute("Test", ["a", "b"], MultiModelMode.VOTE)
        assert result.response == "" or result.response is not None

    def test_router_to_dict(self, router):
        d = router.to_dict()
        assert "available_models" in d
        assert "specialties" in d
        assert "registered_profiles" in d