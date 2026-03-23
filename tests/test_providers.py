"""Tests for LLM provider routing."""

import pytest

from scout.providers import parse_model_config, extract_with_llm, ProviderError


class TestParseModelConfig:
    def test_parses_anthropic(self):
        provider, model = parse_model_config("anthropic:claude-sonnet-4-20250514")
        assert provider == "anthropic"
        assert model == "claude-sonnet-4-20250514"

    def test_parses_openai(self):
        provider, model = parse_model_config("openai:gpt-4o-mini")
        assert provider == "openai"
        assert model == "gpt-4o-mini"

    def test_parses_ollama(self):
        provider, model = parse_model_config("ollama:phi3")
        assert provider == "ollama"
        assert model == "phi3"

    def test_raises_on_invalid_format(self):
        with pytest.raises(ValueError, match="provider:model"):
            parse_model_config("just-a-model-name")

    def test_raises_on_empty(self):
        with pytest.raises(ValueError):
            parse_model_config("")

    def test_raises_on_unknown_provider(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            parse_model_config("cohere:command-r")


class TestExtractWithLLM:
    @pytest.mark.asyncio
    async def test_raises_provider_error_on_missing_api_key(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(ProviderError, match="ANTHROPIC_API_KEY"):
            await extract_with_llm("content", "query", "anthropic", "claude-sonnet-4-20250514")

    @pytest.mark.asyncio
    async def test_ollama_no_key_required(self, monkeypatch):
        """Ollama should not fail on missing API key -- only on connection."""
        with pytest.raises(ProviderError, match="(Connection|connect|refused|Failed)"):
            await extract_with_llm("content", "query", "ollama", "phi3")
