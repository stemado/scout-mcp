"""Tests for the browse tool pipeline."""

import asyncio
import ipaddress
import socket
from unittest.mock import AsyncMock, patch, MagicMock

import httpx
import pytest

from scout.browse import (
    _ssrf_request_hook,
    SSRFSafeTransport,
    _check_resolved_ip,
    http_fetch,
    _is_bot_blocked,
)


class TestSSRFRequestHook:
    """Layer A: Event hook validates every URL including redirect targets."""

    @pytest.mark.asyncio
    async def test_blocks_metadata_ip(self, monkeypatch):
        monkeypatch.delenv("SCOUT_ALLOW_LOCALHOST", raising=False)
        request = httpx.Request("GET", "http://169.254.169.254/latest/meta-data/")
        with pytest.raises(ValueError, match="Blocked URL host"):
            await _ssrf_request_hook(request)

    @pytest.mark.asyncio
    async def test_blocks_localhost(self, monkeypatch):
        monkeypatch.delenv("SCOUT_ALLOW_LOCALHOST", raising=False)
        request = httpx.Request("GET", "http://127.0.0.1:9222/json")
        with pytest.raises(ValueError, match="Blocked URL host"):
            await _ssrf_request_hook(request)

    @pytest.mark.asyncio
    async def test_allows_public_url(self):
        request = httpx.Request("GET", "https://example.com")
        await _ssrf_request_hook(request)  # Should not raise


class TestCheckResolvedIP:
    """Layer B: DNS resolution IP validation."""

    def test_blocks_loopback(self):
        with pytest.raises(ValueError, match="loopback"):
            _check_resolved_ip(ipaddress.ip_address("127.0.0.1"), allow_localhost=False)

    def test_blocks_link_local(self):
        with pytest.raises(ValueError, match="link-local"):
            _check_resolved_ip(ipaddress.ip_address("169.254.1.1"))

    def test_blocks_metadata_ip(self):
        with pytest.raises(ValueError, match="metadata"):
            _check_resolved_ip(ipaddress.ip_address("169.254.169.254"))

    def test_blocks_private(self):
        with pytest.raises(ValueError, match="private"):
            _check_resolved_ip(ipaddress.ip_address("10.0.0.1"), allow_localhost=False)

    def test_blocks_ipv6_mapped_loopback(self):
        with pytest.raises(ValueError, match="loopback"):
            _check_resolved_ip(ipaddress.ip_address("::ffff:127.0.0.1"), allow_localhost=False)

    def test_allows_public_ip(self):
        _check_resolved_ip(ipaddress.ip_address("93.184.216.34"))  # example.com

    def test_allows_loopback_when_permitted(self):
        _check_resolved_ip(ipaddress.ip_address("127.0.0.1"), allow_localhost=True)

    def test_allows_private_when_permitted(self):
        _check_resolved_ip(ipaddress.ip_address("10.0.0.1"), allow_localhost=True)


class TestHTTPFetch:
    """Integration tests for the HTTP fetch with SSRF protection."""

    @pytest.mark.asyncio
    async def test_fetches_public_url(self, base_url):
        """Uses the test server from conftest.py."""
        status, headers, body, final_url = await http_fetch(f"{base_url}/api/data", timeout=5)
        assert status == 200
        assert "application/json" in headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_returns_status_and_body(self, base_url):
        status, headers, body, final_url = await http_fetch(f"{base_url}/api/data", timeout=5)
        assert status == 200
        assert b'"key"' in body
        assert "127.0.0.1" in final_url


class TestBotDetection:
    def test_detects_cloudflare_challenge(self):
        html = b"<html><head><title>Just a moment...</title></head><body></body></html>"
        assert _is_bot_blocked(403, {}, html) is True

    def test_detects_empty_body_with_scripts(self):
        html = b'<html><body><script src="challenge.js"></script><script src="verify.js"></script></body></html>'
        assert _is_bot_blocked(200, {}, html) is True

    def test_detects_cf_ray_header_with_403(self):
        assert _is_bot_blocked(403, {"cf-ray": "abc123"}, b"Access denied") is True

    def test_allows_normal_html(self):
        html = b"<html><head><title>Real Page</title></head><body><p>Content here</p></body></html>"
        assert _is_bot_blocked(200, {}, html) is False

    def test_allows_normal_404(self):
        html = b"<html><body>Not found</body></html>"
        assert _is_bot_blocked(404, {}, html) is False

    def test_detects_captcha_marker_with_form(self):
        html = b'<html><body><form><div id="captcha-container">Please verify</div></form></body></html>'
        assert _is_bot_blocked(200, {}, html) is True

    def test_ignores_captcha_in_article_text(self):
        html = b'<html><body><p>This article discusses how CAPTCHA technology works.</p></body></html>'
        assert _is_bot_blocked(200, {}, html) is False

    def test_detects_captcha_with_403(self):
        html = b'<html><body><div>Please complete the captcha to continue</div></body></html>'
        assert _is_bot_blocked(403, {}, html) is True
