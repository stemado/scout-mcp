"""Tests for cross-origin navigation guard."""

from unittest.mock import patch

import pytest

from scout.security.audit_log import SecurityCounter
from scout.security.navigation_guard import NavigationGuard, extract_registered_domain


class TestExtractRegisteredDomain:
    """Test domain extraction utility."""

    def test_simple_domain(self):
        assert extract_registered_domain("https://example.com/path") == "example.com"

    def test_subdomain(self):
        assert extract_registered_domain("https://sub.example.com") == "example.com"

    def test_deep_subdomain(self):
        assert extract_registered_domain("https://a.b.c.example.com") == "example.com"

    def test_co_uk(self):
        assert extract_registered_domain("https://foo.co.uk") == "foo.co.uk"

    def test_ip_address(self):
        result = extract_registered_domain("http://192.168.1.1:8080")
        assert "192.168.1.1" in result


class TestNavigationGuard:
    """Test navigation guard behavior."""

    def test_same_domain_allowed(self):
        guard = NavigationGuard(
            origin_url="https://example.com",
            allowed_domains=["example.com"],
        )
        result = guard.check_navigation(
            "https://example.com/page1",
            "https://example.com/page2",
        )
        assert result is None  # allowed

    def test_subdomain_of_origin_allowed(self):
        """Subdomains share the registered domain."""
        guard = NavigationGuard(
            origin_url="https://app.example.com",
            allowed_domains=["example.com"],
        )
        result = guard.check_navigation(
            "https://app.example.com/page1",
            "https://login.example.com/auth",
        )
        assert result is None  # same registered domain

    def test_cross_origin_blocked(self):
        guard = NavigationGuard(
            origin_url="https://example.com",
            allowed_domains=["example.com"],
        )
        result = guard.check_navigation(
            "https://example.com/page1",
            "https://evil.com/phish",
        )
        assert result is not None
        assert result["type"] == "navigation_blocked"
        assert result["to_domain"] == "evil.com"

    def test_allowed_domains_permits(self):
        guard = NavigationGuard(
            origin_url="https://example.com",
            allowed_domains=["example.com", "example.net"],
        )
        result = guard.check_navigation(
            "https://example.com",
            "https://cdn.example.net/asset",
        )
        assert result is None

    def test_origin_always_allowed(self):
        """Origin domain is automatically added to allowed list."""
        guard = NavigationGuard(
            origin_url="https://mysite.com",
            allowed_domains=[],  # empty list
        )
        result = guard.check_navigation(
            "https://mysite.com/a",
            "https://mysite.com/b",
        )
        assert result is None

    def test_permit_url(self):
        guard = NavigationGuard(
            origin_url="https://example.com",
        )
        target = "https://other.com/page"
        # First attempt blocked
        result = guard.check_navigation("https://example.com", target)
        assert result is not None

        # Permit it
        guard.permit_url(target)

        # Second attempt allowed (one-time)
        result = guard.check_navigation("https://example.com", target)
        assert result is None

        # Third attempt blocked again (one-time permit consumed)
        result = guard.check_navigation("https://example.com", target)
        assert result is not None

    def test_security_counter_incremented(self):
        counter = SecurityCounter()
        guard = NavigationGuard(
            origin_url="https://example.com",
            security_counter=counter,
        )
        guard.check_navigation("https://example.com", "https://evil.com")
        assert counter.summary()["navigations_blocked"] == 1

    def test_get_blocked_navigation(self):
        guard = NavigationGuard(origin_url="https://example.com")
        guard.check_navigation("https://example.com", "https://evil.com/page")
        blocked = guard.get_blocked_navigation()
        assert blocked is not None
        assert blocked["blocked_url"] == "https://evil.com/page"

    def test_no_blocked_navigation_initially(self):
        guard = NavigationGuard(origin_url="https://example.com")
        assert guard.get_blocked_navigation() is None

    def test_case_insensitive_domain_matching(self):
        guard = NavigationGuard(
            origin_url="https://Example.COM",
            allowed_domains=["Other.NET"],
        )
        result = guard.check_navigation(
            "https://example.com",
            "https://other.net/path",
        )
        assert result is None  # allowed (case-insensitive)
