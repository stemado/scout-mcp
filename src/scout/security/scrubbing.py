"""POST body scrubbing for network monitor responses.

Redacts sensitive fields in captured POST request bodies before they
are returned in monitor_network tool responses.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .audit_log import SecurityCounter, log_security_event

# URL-encoded form field patterns: key=value in POST bodies
_FORM_FIELD_PATTERNS = re.compile(
    r"(?i)\b(password|passwd|pwd|pass|token|api_key|apikey|secret|client_secret)"
    r"=([^&\s]+)"
)

# JSON body field patterns: "key": "value" or "key": value
_JSON_FIELD_PATTERNS = re.compile(
    r'(?i)"(password|passwd|pwd|pass|token|api_key|apikey|secret|client_secret)"\s*:\s*'
    r'("(?:[^"\\]|\\.)*"|[^,}\s]+)'
)


def scrub_post_body(
    body: str | None,
    env_keys: set[str] | None = None,
    env_values: dict[str, str] | None = None,
) -> tuple[str | None, int]:
    """Scrub sensitive values from a POST request body.

    Args:
        body: The raw POST body string.
        env_keys: Set of .env key names (case-insensitive match against body field names).
        env_values: Dict of env key -> value for value-based matching.

    Returns:
        Tuple of (scrubbed_body, scrubbed_fields_count).
    """
    if not body:
        return body, 0

    scrubbed = body
    count = 0

    # Scrub URL-encoded form fields
    def _form_replacer(m: re.Match) -> str:
        nonlocal count
        count += 1
        return f"{m.group(1)}=[REDACTED]"

    scrubbed = _FORM_FIELD_PATTERNS.sub(_form_replacer, scrubbed)

    # Scrub JSON body fields
    def _json_replacer(m: re.Match) -> str:
        nonlocal count
        count += 1
        return f'"{m.group(1)}": "[REDACTED]"'

    scrubbed = _JSON_FIELD_PATTERNS.sub(_json_replacer, scrubbed)

    # Scrub values matching .env keys (case-insensitive key match in body)
    if env_keys:
        for key in env_keys:
            # URL-encoded form: KEY=value
            pattern = re.compile(
                re.escape(key) + r"=([^&\s]+)", re.IGNORECASE
            )
            if pattern.search(scrubbed):
                scrubbed = pattern.sub(f"{key}=[REDACTED]", scrubbed)
                count += 1
            # JSON: "KEY": "value"
            json_pat = re.compile(
                r'"' + re.escape(key) + r'"\s*:\s*("(?:[^"\\]|\\.)*"|[^,}\s]+)',
                re.IGNORECASE,
            )
            if json_pat.search(scrubbed):
                scrubbed = json_pat.sub(f'"{key}": "[REDACTED]"', scrubbed)
                count += 1

    # Scrub actual env values found in body
    if env_values:
        for key, value in sorted(env_values.items(), key=lambda kv: len(kv[1]), reverse=True):
            if value and len(value) >= 4 and value in scrubbed:
                scrubbed = scrubbed.replace(value, "[REDACTED]")
                count += 1

    return scrubbed, count


def scrub_network_events(
    events: list[dict[str, Any]],
    env_keys: set[str] | None = None,
    env_values: dict[str, str] | None = None,
    session_id: str | None = None,
    security_counter: SecurityCounter | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Scrub POST bodies in a list of network event dicts.

    Returns (scrubbed_events, total_scrubbed_fields).
    """
    total_scrubbed = 0

    for event in events:
        body = event.get("response_body")
        if body:
            scrubbed, count = scrub_post_body(body, env_keys, env_values)
            if count > 0:
                event["response_body"] = scrubbed
                total_scrubbed += count

    if total_scrubbed > 0 and security_counter:
        security_counter.increment("scrubbing_applied")
        log_security_event(
            session_id=session_id,
            event_type="scrubbing_applied",
            severity="info",
            detail={"scrubbed_fields": total_scrubbed},
        )

    return events, total_scrubbed
