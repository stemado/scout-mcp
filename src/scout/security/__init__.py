"""Scout security package — centralized security mitigations.

Public interface:
    - PromptInjectionFilter / scan_and_warn: detect prompt injection in page content
    - NavigationGuard: cross-origin navigation blocking for extension mode
    - scrub_post_body / scrub_network_events: POST body credential scrubbing
    - SecurityCounter: per-session security event counters
    - log_security_event / read_security_log: structured security logging
"""

from .audit_log import SecurityCounter, log_security_event, read_security_log
from .injection_filter import PromptInjectionFilter, scan_and_warn
from .navigation_guard import NavigationGuard, extract_registered_domain
from .scrubbing import scrub_network_events, scrub_post_body

__all__ = [
    "PromptInjectionFilter",
    "scan_and_warn",
    "NavigationGuard",
    "extract_registered_domain",
    "scrub_post_body",
    "scrub_network_events",
    "SecurityCounter",
    "log_security_event",
    "read_security_log",
]
