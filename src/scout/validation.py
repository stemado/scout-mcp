"""Input validation utilities for the Scout MCP server."""

from __future__ import annotations

import os
import re
from urllib.parse import urlparse

# --- URL validation (Task 6) ---

_BLOCKED_SCHEMES = frozenset({
    "file", "ftp", "data", "chrome", "chrome-extension",
    "javascript", "about", "blob", "devtools",
})

_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0"})

_BLOCKED_HOSTS = frozenset({
    "169.254.169.254",          # AWS EC2 metadata
    "metadata.google.internal",  # GCP metadata
    "100.100.100.200",           # Alibaba Cloud metadata
}) | _LOOPBACK_HOSTS


def validate_url(url: str, *, allow_localhost: bool = False) -> None:
    """Validate a URL is safe to navigate to.

    Raises ValueError for blocked schemes or hosts.
    Allows empty strings (callers handle those as no-ops).

    Args:
        url: The URL to validate.
        allow_localhost: If True, permit loopback addresses (for testing).
    """
    if not url:
        return

    parsed = urlparse(url)

    if parsed.scheme.lower() in _BLOCKED_SCHEMES:
        raise ValueError(f"Blocked URL scheme: {parsed.scheme}")

    hostname = parsed.hostname
    if hostname:
        hostname_lower = hostname.lower()
        if allow_localhost and hostname_lower in _LOOPBACK_HOSTS:
            return
        if hostname_lower in _BLOCKED_HOSTS:
            raise ValueError(f"Blocked URL host: {hostname}")
        # Block link-local range (169.254.x.x)
        if hostname_lower.startswith("169.254."):
            raise ValueError(f"Blocked URL host: {hostname}")


# --- Directory path validation (Task 7) ---


def validate_directory_path(path: str) -> None:
    """Validate a directory path is relative and doesn't traverse upward.

    Raises ValueError for absolute paths, UNC paths, or parent traversal.
    """
    if not path:
        return

    # Block absolute paths (Unix and Windows)
    if os.path.isabs(path):
        raise ValueError(f"Directory path must be a relative path, got: {path}")

    # Block UNC paths
    if path.startswith("\\\\"):
        raise ValueError(f"Directory path must be a relative path, got: {path}")

    # Block parent directory traversal
    normalized = os.path.normpath(path)
    if normalized.startswith(".."):
        raise ValueError(f"Directory path must not traverse above working directory: {path}")


# --- Regex pattern validation (Task 10) ---

MAX_REGEX_LENGTH = 500


def validate_regex_pattern(pattern: str) -> re.Pattern:
    """Compile a regex pattern with safety checks.

    Raises ValueError for patterns that are too long or invalid.
    Returns the compiled pattern.
    """
    if len(pattern) > MAX_REGEX_LENGTH:
        raise ValueError(f"Regex pattern too long ({len(pattern)} chars, max {MAX_REGEX_LENGTH})")
    try:
        return re.compile(pattern)
    except re.error as e:
        raise ValueError(f"Invalid regex pattern: {e}") from e
