"""Centralized security event logging for Scout MCP server.

All security events (injection detection, credential refusals, navigation
blocks, WebSocket rejections, POST body scrubbing) are logged as JSON lines
to ``~/.scout/security.log``.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_LOG_DIR = Path.home() / ".scout"
_LOG_FILE = _LOG_DIR / "security.log"
_lock = threading.Lock()


def _ensure_log_dir() -> None:
    """Create ~/.scout/ if it doesn't exist."""
    _LOG_DIR.mkdir(parents=True, exist_ok=True)


def log_security_event(
    session_id: str | None,
    event_type: str,
    severity: str,
    url: str = "",
    detail: dict[str, Any] | None = None,
) -> None:
    """Append a JSON security event to ~/.scout/security.log.

    Thread-safe. Never raises — failures are silently ignored so that
    logging never disrupts the main MCP flow.
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id or "",
        "event_type": event_type,
        "severity": severity,
        "url": url,
        "detail": detail or {},
    }
    try:
        _ensure_log_dir()
        with _lock:
            with open(_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
    except Exception:
        pass


def read_security_log(
    session_id: str | None = None,
    severity: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Read recent security events, optionally filtered.

    Returns events in reverse-chronological order (most recent first).
    """
    if not _LOG_FILE.exists():
        return []

    events: list[dict[str, Any]] = []
    try:
        with open(_LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if session_id and entry.get("session_id") != session_id:
                    continue
                if severity and entry.get("severity") != severity:
                    continue
                events.append(entry)
    except Exception:
        return []

    # Most recent first, limited
    events.reverse()
    return events[:limit]


class SecurityCounter:
    """Thread-safe counters for security events within a session."""

    def __init__(self) -> None:
        self.injection_attempts: int = 0
        self.credentials_refused: int = 0
        self.navigations_blocked: int = 0
        self.post_bodies_scrubbed: int = 0
        self.ws_connections_rejected: int = 0
        self._lock = threading.Lock()

    def increment(self, event_type: str) -> None:
        with self._lock:
            if event_type == "injection_detected":
                self.injection_attempts += 1
            elif event_type == "credential_refused":
                self.credentials_refused += 1
            elif event_type == "navigation_blocked":
                self.navigations_blocked += 1
            elif event_type == "scrubbing_applied":
                self.post_bodies_scrubbed += 1
            elif event_type == "ws_rejected":
                self.ws_connections_rejected += 1

    def summary(self) -> dict[str, int]:
        with self._lock:
            return {
                "injection_attempts": self.injection_attempts,
                "credentials_refused": self.credentials_refused,
                "navigations_blocked": self.navigations_blocked,
                "post_bodies_scrubbed": self.post_bodies_scrubbed,
                "ws_connections_rejected": self.ws_connections_rejected,
            }
