"""LLM provider routing for browse tool query extraction.

Supports anthropic, openai, and ollama providers via lazy imports.
"""

from __future__ import annotations

import os

_KNOWN_PROVIDERS = frozenset({"anthropic", "openai", "ollama"})

_EXTRACTION_SYSTEM_PROMPT = (
    "Extract only the content from the following text that is relevant to the user's query. "
    "Return the relevant passages as-is, preserving formatting. "
    "If nothing is relevant, say so."
)

_MAX_INPUT_CHARS = 32_000  # ~8K tokens
_TIMEOUT = 15


class ProviderError(Exception):
    """Raised when a provider call fails."""


def parse_model_config(config: str) -> tuple[str, str]:
    """Parse 'provider:model' string. Returns (provider, model)."""
    if not config:
        raise ValueError("Model config cannot be empty")
    if ":" not in config:
        raise ValueError(f"Invalid model config '{config}' — expected format: provider:model")
    provider, model = config.split(":", 1)
    if provider not in _KNOWN_PROVIDERS:
        raise ValueError(f"Unknown provider '{provider}'. Supported: {', '.join(sorted(_KNOWN_PROVIDERS))}")
    return provider, model


async def extract_with_llm(content: str, query: str, provider: str, model: str) -> str:
    """Send content + query to an LLM for focused extraction.

    Raises ProviderError on any failure.
    """
    truncated = content[:_MAX_INPUT_CHARS]
    user_message = f"Query: {query}\n\nText:\n{truncated}"

    if provider == "anthropic":
        return await _call_anthropic(model, user_message)
    elif provider == "openai":
        return await _call_openai(model, user_message)
    elif provider == "ollama":
        return await _call_ollama(model, user_message)
    else:
        raise ProviderError(f"Unknown provider: {provider}")


async def _call_anthropic(model: str, user_message: str) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ProviderError("ANTHROPIC_API_KEY not set")
    try:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=api_key, timeout=_TIMEOUT)
        response = await client.messages.create(
            model=model,
            max_tokens=2048,
            system=_EXTRACTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text
    except ProviderError:
        raise
    except Exception as e:
        raise ProviderError(f"Anthropic API error: {e}") from e


async def _call_openai(model: str, user_message: str) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ProviderError("OPENAI_API_KEY not set")
    try:
        import openai

        client = openai.AsyncOpenAI(api_key=api_key, timeout=_TIMEOUT)
        response = await client.chat.completions.create(
            model=model,
            max_tokens=2048,
            messages=[
                {"role": "system", "content": _EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
        )
        return response.choices[0].message.content or ""
    except ProviderError:
        raise
    except Exception as e:
        raise ProviderError(f"OpenAI API error: {e}") from e


async def _call_ollama(model: str, user_message: str) -> str:
    try:
        import httpx

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": model,
                    "system": _EXTRACTION_SYSTEM_PROMPT,
                    "prompt": user_message,
                    "stream": False,
                },
            )
            response.raise_for_status()
            return response.json().get("response", "")
    except Exception as e:
        raise ProviderError(f"Failed to call Ollama: {e}") from e
