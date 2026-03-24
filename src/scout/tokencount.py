"""Token counting utility using tiktoken for benchmarking response sizes.

Uses cl100k_base encoding — the closest publicly available encoding to
Claude's tokenizer. Not exact, but consistent and good enough for relative
benchmarking. Falls back to character-based estimation (~4 chars/token) if
tiktoken can't load its encoding data (e.g., no internet on first run).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_encoder = None  # tiktoken.Encoding | None
_tiktoken_available: bool | None = None  # None = not yet attempted


def _get_encoder():
    global _encoder, _tiktoken_available
    if _tiktoken_available is False:
        return None
    if _encoder is None:
        try:
            import tiktoken
            _encoder = tiktoken.get_encoding("cl100k_base")
            _tiktoken_available = True
        except Exception as e:
            logger.warning("tiktoken unavailable, falling back to char-based estimation: %s", e)
            _tiktoken_available = False
            return None
    return _encoder


# Fallback ratio: ~4 characters per token for mixed English/JSON content.
_CHARS_PER_TOKEN = 4


def count_tokens(text: str) -> int:
    """Count the approximate number of tokens in a string.

    Uses tiktoken (cl100k_base) when available, otherwise estimates
    from character count at ~4 chars/token.
    """
    encoder = _get_encoder()
    if encoder is not None:
        return len(encoder.encode(text))
    # Fallback: integer division with a minimum of 1 for non-empty text
    if not text:
        return 0
    return max(1, len(text) // _CHARS_PER_TOKEN)
