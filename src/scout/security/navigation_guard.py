"""Cross-origin navigation guard for extension relay mode.

Intercepts Page.frameNavigated CDP events and blocks cross-origin
navigations that are not in the session's allowed_domains list.
"""

from __future__ import annotations

import threading
from typing import Any

import tldextract

from .audit_log import SecurityCounter, log_security_event


def extract_registered_domain(url: str) -> str:
    """Extract the registered domain from a URL using tldextract.

    Returns the registered domain (e.g., 'example.com' from 'https://sub.example.com/path').
    For IP addresses, returns the IP.
    """
    ext = tldextract.extract(url)
    # Use top_domain_under_public_suffix (replaces deprecated registered_domain)
    top_domain = getattr(ext, "top_domain_under_public_suffix", "")
    if top_domain:
        return top_domain
    # Fallback for IPs or unusual URLs
    return ext.domain or url


class NavigationGuard:
    """Guards against unexpected cross-origin navigations in extension mode.

    Tracks the origin domain from launch_session and blocks navigations
    to domains not in the allowed_domains list.
    """

    def __init__(
        self,
        origin_url: str,
        allowed_domains: list[str] | None = None,
        session_id: str | None = None,
        security_counter: SecurityCounter | None = None,
    ) -> None:
        self._origin_domain = extract_registered_domain(origin_url)
        self._allowed_domains: set[str] = set()
        if allowed_domains:
            self._allowed_domains = {d.lower() for d in allowed_domains}
        # Always allow the origin domain
        self._allowed_domains.add(self._origin_domain.lower())
        self._session_id = session_id
        self._security_counter = security_counter

        # Blocked navigation state
        self._blocked_url: str | None = None
        self._blocked_from: str | None = None
        self._lock = threading.Lock()

        # One-time permits granted by allow_navigation
        self._permitted_urls: set[str] = set()

    @property
    def origin_domain(self) -> str:
        return self._origin_domain

    @property
    def allowed_domains(self) -> set[str]:
        return set(self._allowed_domains)

    def is_domain_allowed(self, url: str) -> bool:
        """Check if navigation to this URL is allowed."""
        domain = extract_registered_domain(url).lower()
        return domain in self._allowed_domains

    def check_navigation(self, from_url: str, to_url: str) -> dict | None:
        """Check if a navigation should be blocked.

        Returns None if allowed, or a structured warning dict if blocked.
        """
        # Check one-time permits first
        with self._lock:
            if to_url in self._permitted_urls:
                self._permitted_urls.discard(to_url)
                return None

        to_domain = extract_registered_domain(to_url).lower()
        from_domain = extract_registered_domain(from_url).lower()

        if to_domain in self._allowed_domains:
            return None

        # Block and log
        with self._lock:
            self._blocked_url = to_url
            self._blocked_from = from_url

        log_security_event(
            session_id=self._session_id,
            event_type="navigation_blocked",
            severity="warning",
            url=to_url,
            detail={
                "from_domain": from_domain,
                "to_domain": to_domain,
                "allowed_domains": sorted(self._allowed_domains),
            },
        )

        if self._security_counter:
            self._security_counter.increment("navigation_blocked")

        return {
            "type": "navigation_blocked",
            "from_domain": from_domain,
            "to_domain": to_domain,
            "message": (
                "Cross-origin navigation detected outside allowed_domains. "
                "Confirm intent before proceeding."
            ),
            "action_required": (
                "Call allow_navigation(url) to permit this navigation "
                "or close_session() to abort."
            ),
        }

    def permit_url(self, url: str) -> None:
        """Grant a one-time navigation permit for a specific URL."""
        with self._lock:
            self._permitted_urls.add(url)
            # Clear blocked state if this URL was blocked
            if self._blocked_url == url:
                self._blocked_url = None
                self._blocked_from = None

    def get_blocked_navigation(self) -> dict | None:
        """Return the currently blocked navigation, if any."""
        with self._lock:
            if self._blocked_url:
                return {
                    "blocked_url": self._blocked_url,
                    "from_url": self._blocked_from,
                }
            return None
