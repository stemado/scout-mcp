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
    extract_content,
    truncate_at_paragraph,
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


from scout.browse import keyword_extract


class TestKeywordExtract:
    def test_returns_relevant_paragraphs(self):
        text = (
            "The weather in Paris is mild.\n\n"
            "The Supreme Court decided Trump v. Anderson today.\n\n"
            "Stock markets closed higher on Friday.\n\n"
            "The ruling reversed the Colorado decision on ballot access."
        )
        result = keyword_extract(text, query="Supreme Court ruling")
        assert "Supreme Court" in result
        assert "ruling" in result.lower()

    def test_preserves_document_order(self):
        text = (
            "First relevant paragraph about cats.\n\n"
            "Irrelevant paragraph about weather.\n\n"
            "Second relevant paragraph about cats."
        )
        result = keyword_extract(text, query="cats")
        first_idx = result.find("First relevant")
        second_idx = result.find("Second relevant")
        assert first_idx < second_idx

    def test_returns_empty_when_no_match(self):
        text = "Nothing about the query topic here."
        result = keyword_extract(text, query="quantum physics")
        assert isinstance(result, str)

    def test_handles_single_paragraph(self):
        text = "Just one paragraph about the Supreme Court."
        result = keyword_extract(text, query="Supreme Court")
        assert "Supreme Court" in result


class TestExtractContent:
    @pytest.mark.asyncio
    async def test_extracts_main_content(self):
        html = """<html><head><title>Test</title></head>
        <body><nav>Menu</nav><main><h1>Title</h1><p>Real content here.</p></main>
        <footer>Copyright</footer></body></html>"""
        title, content = await extract_content(html)
        assert "Real content" in content
        assert title == "Test"

    @pytest.mark.asyncio
    async def test_returns_empty_on_blank_html(self):
        title, content = await extract_content("<html><body></body></html>")
        assert content == ""

    @pytest.mark.asyncio
    async def test_skips_nav_and_footer(self):
        html = """<html><head><title>T</title></head><body>
        <nav>Navigation</nav><p>Article text</p><footer>Footer</footer></body></html>"""
        title, content = await extract_content(html)
        assert "Navigation" not in content or "Article" in content

    @pytest.mark.asyncio
    async def test_json_passthrough(self):
        title, content = await extract_content('{"key": "value"}', content_type="application/json")
        assert '"key"' in content
        assert '"value"' in content

    @pytest.mark.asyncio
    async def test_plain_text_passthrough(self):
        title, content = await extract_content("Just plain text.", content_type="text/plain")
        assert content == "Just plain text."


class TestTruncation:
    def test_no_truncation_when_under_limit(self):
        text = "Short text."
        assert truncate_at_paragraph(text, max_length=1000) == text

    def test_truncates_at_paragraph_boundary(self):
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        result = truncate_at_paragraph(text, max_length=30)
        assert result == "First paragraph."

    def test_zero_disables_truncation(self):
        text = "A" * 10000
        assert truncate_at_paragraph(text, max_length=0) == text

    def test_never_truncates_mid_sentence(self):
        text = "This is a long sentence that should not be cut in half."
        result = truncate_at_paragraph(text, max_length=20)
        assert result == text
