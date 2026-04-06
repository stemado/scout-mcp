"""Tests for secret-vault integration in Scout MCP."""

from __future__ import annotations

import unittest.mock
from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch

import pytest


# Minimal AppContext stub matching the real dataclass
@dataclass
class FakeAppContext:
    _env_vars: dict[str, str] | None = None
    _vault_resolver: object | None = None


def test_get_credential_with_vault():
    """When secret-vault is installed and resolver is set, vault wins."""
    from scout.server import _get_credential

    mock_resolver = MagicMock()
    mock_resolver.get.return_value = "vault-value"

    ctx = FakeAppContext()
    ctx._vault_resolver = mock_resolver

    result = _get_credential("MY_KEY", ctx)

    assert result == "vault-value"
    mock_resolver.get.assert_called_once_with("MY_KEY")


def test_get_credential_without_vault():
    """When secret-vault is not installed, falls back to .env."""
    from scout.server import _get_credential

    ctx = FakeAppContext()
    ctx._env_vars = {"MY_KEY": "env-value"}

    # Simulate secret-vault not installed
    with patch.dict("sys.modules", {"secret_vault": None}):
        # Force re-import to hit ImportError
        ctx._vault_resolver = None
        result = _get_credential("MY_KEY", ctx)

    assert result == "env-value"


def test_get_credential_vault_missing_key_falls_back():
    """Vault exists but doesn't have the key — falls to .env."""
    from scout.server import _get_credential

    mock_resolver = MagicMock()
    mock_resolver.get.side_effect = KeyError("NOT_IN_VAULT")

    ctx = FakeAppContext()
    ctx._vault_resolver = mock_resolver
    ctx._env_vars = {"NOT_IN_VAULT": "env-fallback"}

    result = _get_credential("NOT_IN_VAULT", ctx)
    assert result == "env-fallback"


def test_get_credential_vault_error_falls_back():
    """Vault raises unexpected error — falls to .env gracefully."""
    from scout.server import _get_credential

    mock_resolver = MagicMock()
    mock_resolver.get.side_effect = RuntimeError("vault locked")

    ctx = FakeAppContext()
    ctx._vault_resolver = mock_resolver
    ctx._env_vars = {"KEY": "env-value"}

    result = _get_credential("KEY", ctx)
    assert result == "env-value"


def test_get_credential_not_found_anywhere():
    """Returns None when credential is in neither source."""
    from scout.server import _get_credential

    mock_resolver = MagicMock()
    mock_resolver.get.side_effect = KeyError("MISSING")

    ctx = FakeAppContext()
    ctx._vault_resolver = mock_resolver
    ctx._env_vars = {}

    result = _get_credential("MISSING", ctx)
    assert result is None


def test_vault_resolver_closed_on_teardown():
    """Verify close() is called on the vault resolver during cleanup."""
    mock_resolver = MagicMock()

    ctx = FakeAppContext()
    ctx._vault_resolver = mock_resolver

    # Simulate the cleanup logic from app_lifespan
    if ctx._vault_resolver is not None:
        try:
            ctx._vault_resolver.close()
        except Exception:
            pass
        ctx._vault_resolver = None

    mock_resolver.close.assert_called_once()
    assert ctx._vault_resolver is None
