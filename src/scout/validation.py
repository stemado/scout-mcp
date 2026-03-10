"""Input validation utilities for the Scout MCP server."""

from __future__ import annotations

import ipaddress
import os
import re
from urllib.parse import urlparse

# --- URL validation ---

# Allowlist: only permit standard web schemes.
_ALLOWED_SCHEMES = frozenset({"http", "https"})

_LOOPBACK_HOSTNAMES = frozenset({"localhost"})

_BLOCKED_METADATA_IPS = frozenset({
    "169.254.169.254",          # AWS EC2 metadata
    "100.100.100.200",           # Alibaba Cloud metadata
})

_BLOCKED_METADATA_HOSTS = frozenset({
    "metadata.google.internal",  # GCP metadata
})


def _is_blocked_host(hostname: str, *, allow_localhost: bool = False) -> bool:
    """Check if a hostname is blocked (metadata endpoints, loopback, link-local).

    Normalizes IP addresses via the ``ipaddress`` module to catch alternative
    encodings such as IPv6-mapped IPv4 (``::ffff:169.254.169.254``).
    """
    hostname_lower = hostname.lower()

    # Named hostname checks
    if hostname_lower in _BLOCKED_METADATA_HOSTS:
        return True
    if hostname_lower in _LOOPBACK_HOSTNAMES:
        return not allow_localhost

    # Try to parse as an IP address for property-based checks
    try:
        addr = ipaddress.ip_address(hostname)
    except ValueError:
        # Not a standard IP literal — no further checks
        return False

    # IPv6-mapped IPv4: extract the v4 address for comparison
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped

    if addr.is_loopback:
        return not allow_localhost
    if addr.is_link_local:
        return True
    if str(addr) in _BLOCKED_METADATA_IPS:
        return True

    return False


def validate_url(url: str, *, allow_localhost: bool = False) -> None:
    """Validate a URL is safe to navigate to.

    Raises ValueError for non-http(s) schemes or blocked hosts.
    Allows empty strings (callers handle those as no-ops).

    Args:
        url: The URL to validate.
        allow_localhost: If True, permit loopback addresses (for testing).
    """
    if not url:
        return

    parsed = urlparse(url)

    # Scheme allowlist: only http and https are permitted.
    # Empty scheme (e.g. bare "example.com") is allowed — the browser normalizes it.
    if parsed.scheme and parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise ValueError(f"Only http and https URLs are allowed, got scheme: {parsed.scheme}")

    hostname = parsed.hostname
    if hostname and _is_blocked_host(hostname, allow_localhost=allow_localhost):
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
