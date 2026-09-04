import os
from unittest.mock import patch
import pytest

from trip_planner.crew import TripPlannerCrew


def test_hermes3_model_alias_resolution(monkeypatch: pytest.MonkeyPatch):
    """
    Verifies that 'hermes3' or 'hermes-3' resolves to openrouter/nousresearch/hermes-3-llama-3.1-70b.
    """
    monkeypatch.setenv("TRIP_PLANNER_MODEL", "hermes3")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-testkey1234567890")
    crew = TripPlannerCrew()
    llm = crew._get_llm()
    assert "hermes-3-llama-3.1-70b" in llm.model
    assert llm.api_key == "sk-or-v1-testkey1234567890"
    assert "openrouter" in str(llm.api_base or "")


def test_hermes3_405b_alias_resolution(monkeypatch: pytest.MonkeyPatch):
    """
    Verifies that 'hermes-3-405b' resolves to openrouter/nousresearch/hermes-3-llama-3.1-405b.
    """
    monkeypatch.setenv("TRIP_PLANNER_MODEL", "hermes-3-405b")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-testkey1234567890")
    crew = TripPlannerCrew()
    llm = crew._get_llm()
    assert "hermes-3-llama-3.1-405b" in llm.model
    assert llm.api_key == "sk-or-v1-testkey1234567890"



def test_hermes3_fallback_to_groq_when_key_missing(monkeypatch: pytest.MonkeyPatch):
    """
    Verifies that if Hermes 3 is requested without OPENROUTER_API_KEY,
    it falls back gracefully to Groq rather than crashing.
    """
    monkeypatch.setenv("TRIP_PLANNER_MODEL", "hermes3")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_groq_key_12345")
    crew = TripPlannerCrew()
    llm = crew._get_llm()
    assert llm.model == "groq/qwen/qwen3.6-27b"
    assert llm.api_key == "gsk_test_groq_key_12345"
