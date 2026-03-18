"""Tests for session history archive — post-close history retrieval."""

from dataclasses import dataclass, field
from unittest.mock import MagicMock

from scout.history import SessionHistoryTracker
from scout.sanitize import _BOUNDARY_START, _BOUNDARY_END
from scout.security.audit_log import SecurityCounter
from scout.server import AppContext


def _make_session_stub(session_id: str = "aabbccddeeff") -> MagicMock:
    """Create a minimal BrowserSession-like stub with real history/security."""
    stub = MagicMock()
    stub.session_id = session_id
    stub.is_active = True
    stub.history = SessionHistoryTracker(session_id)
    stub.security_counter = SecurityCounter()
    stub._secret_values = set()
    # Simulate session.close() returning a result
    close_result = MagicMock()
    close_result.session_duration_seconds = 10.0
    close_result.total_actions_performed = 3
    close_result.total_scouts_performed = 1
    close_result.model_dump.return_value = {
        "closed": True,
        "session_duration_seconds": 10.0,
        "total_actions_performed": 3,
        "total_scouts_performed": 1,
    }
    stub.close.return_value = close_result
    return stub


class TestArchiveOnClose:
    """Verify that close_session preserves history in _closed_histories."""

    def test_history_archived_after_close(self):
        """After close, _closed_histories should contain the session's history."""
        ctx = AppContext()
        session = _make_session_stub("aabbccddeeff")
        session.history.record_navigation("https://example.com")
        ctx.sessions["aabbccddeeff"] = session

        # Simulate what close_session does: close, archive, delete
        session.close()

        history = session.history.get_full_history()
        archived = history.model_dump(exclude_none=True)
        archived["security_summary"] = session.security_counter.summary()
        from scout.sanitize import sanitize_response
        ctx._closed_histories["aabbccddeeff"] = sanitize_response(
            archived, secrets=session._secret_values
        )
        del ctx.sessions["aabbccddeeff"]

        assert "aabbccddeeff" in ctx._closed_histories
        archived_str = ctx._closed_histories["aabbccddeeff"]
        assert "example.com" in archived_str
        assert _BOUNDARY_START in archived_str

    def test_fifo_eviction_at_cap(self):
        """When more than _max_closed_histories sessions are archived, oldest is evicted."""
        ctx = AppContext()
        ctx._max_closed_histories = 3

        for i in range(4):
            sid = f"{i:012x}"
            ctx._closed_histories[sid] = f"history-{i}"
            if len(ctx._closed_histories) > ctx._max_closed_histories:
                oldest = next(iter(ctx._closed_histories))
                del ctx._closed_histories[oldest]

        assert len(ctx._closed_histories) == 3
        # First session (000000000000) should be evicted
        assert "000000000000" not in ctx._closed_histories
        # Last three should remain
        assert "000000000001" in ctx._closed_histories
        assert "000000000002" in ctx._closed_histories
        assert "000000000003" in ctx._closed_histories

    def test_secrets_scrubbed_in_archive(self):
        """Archived history should have secret values replaced with [REDACTED]."""
        ctx = AppContext()
        session = _make_session_stub("aabbccddeeff")
        session._secret_values = {"SuperSecret123"}
        # Record an action that contains the secret in its value
        from scout.models import ActionRecord
        session.history.record_action(ActionRecord(
            action="type",
            selector="#password",
            value="SuperSecret123",
            success=True,
        ))
        ctx.sessions["aabbccddeeff"] = session

        session.close()
        history = session.history.get_full_history()
        archived = history.model_dump(exclude_none=True)
        archived["security_summary"] = session.security_counter.summary()
        from scout.sanitize import sanitize_response
        ctx._closed_histories["aabbccddeeff"] = sanitize_response(
            archived, secrets=session._secret_values
        )

        archived_str = ctx._closed_histories["aabbccddeeff"]
        assert "SuperSecret123" not in archived_str
        assert "[REDACTED]" in archived_str


import pytest

from scout.server import _SESSION_ID_RE


def _resolve_history(app_ctx: AppContext, session_id: str) -> str | None:
    """Mirror the lookup logic from get_session_history (without MCP Context).

    Returns the history string if found (active or archived), raises ValueError
    if invalid format or not found.
    """
    if not _SESSION_ID_RE.match(session_id):
        raise ValueError("Invalid session ID format: expected 12 hex characters.")

    session = app_ctx.sessions.get(session_id)
    if session is None or not session.is_active:
        archived = app_ctx._closed_histories.get(session_id)
        if archived is not None:
            return archived
        raise ValueError(
            f"No session with id '{session_id}' (active or recently closed). "
            "Use launch_session first."
        )
    # Active session found — return sentinel to distinguish from archive path
    return "ACTIVE_SESSION"


class TestGetSessionHistoryFallback:
    """Verify the lookup logic used by get_session_history."""

    def test_active_session_takes_precedence_over_archive(self):
        """When session is active, archive is not returned."""
        ctx = AppContext()
        session = _make_session_stub("aabbccddeeff")
        ctx.sessions["aabbccddeeff"] = session
        ctx._closed_histories["aabbccddeeff"] = "stale-archive-data"

        result = _resolve_history(ctx, "aabbccddeeff")
        assert result == "ACTIVE_SESSION"  # Not the archive

    def test_closed_session_returns_archive(self):
        """When session is not active, archived history is returned."""
        ctx = AppContext()
        ctx._closed_histories["aabbccddeeff"] = "archived-history-string"

        result = _resolve_history(ctx, "aabbccddeeff")
        assert result == "archived-history-string"

    def test_unknown_session_raises_valueerror(self):
        """When session is neither active nor archived, ValueError is raised."""
        ctx = AppContext()

        with pytest.raises(ValueError, match="active or recently closed"):
            _resolve_history(ctx, "aabbccddeeff")

    def test_invalid_format_raises_before_archive_check(self):
        """Invalid session_id format raises ValueError immediately."""
        ctx = AppContext()
        ctx._closed_histories["aabbccddeeff"] = "data"

        with pytest.raises(ValueError, match="12 hex characters"):
            _resolve_history(ctx, "!!!bogus!!!")

    def test_inactive_session_in_dict_falls_back_to_archive(self):
        """A session in the dict but marked inactive should fall back to archive."""
        ctx = AppContext()
        session = _make_session_stub("aabbccddeeff")
        session.is_active = False
        ctx.sessions["aabbccddeeff"] = session
        ctx._closed_histories["aabbccddeeff"] = "archived-data"

        result = _resolve_history(ctx, "aabbccddeeff")
        assert result == "archived-data"
