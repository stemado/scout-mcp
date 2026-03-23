"""Browse tool — lightweight page fetch with content extraction.

Pipeline: HTTP fetch -> bot detection -> browser fallback -> content extraction -> query extraction -> truncation.
"""

from __future__ import annotations

import asyncio
import ipaddress
import os
import socket
from typing import Any

import httpx

from .validation import validate_url

# --- Configuration ---


def _get_browse_timeout() -> int:
    return int(os.environ.get("SCOUT_BROWSE_TIMEOUT", "10"))


def _get_browse_max_length() -> int:
    return int(os.environ.get("SCOUT_BROWSE_MAX_LENGTH", "5000"))


def _allow_localhost() -> bool:
    return os.environ.get("SCOUT_ALLOW_LOCALHOST", "").lower() in ("1", "true", "yes")


_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_BLOCKED_METADATA_IPS = frozenset({
    "169.254.169.254",
    "100.100.100.200",
})

# Browser fallback concurrency limit — lazy-init to avoid binding to
# the wrong event loop when the module is imported before asyncio starts.
_browser_semaphore: asyncio.Semaphore | None = None
_BROWSER_FALLBACK_TIMEOUT = 30


def _get_browser_semaphore() -> asyncio.Semaphore:
    global _browser_semaphore
    if _browser_semaphore is None:
        _browser_semaphore = asyncio.Semaphore(2)
    return _browser_semaphore


# --- SSRF Defense Layer A: Request event hook ---


async def _ssrf_request_hook(request: httpx.Request) -> None:
    """Validate every request URL (including redirect hops) before sending."""
    validate_url(str(request.url), allow_localhost=_allow_localhost())


# --- SSRF Defense Layer B: DNS rebinding protection ---


def _check_resolved_ip(
    addr: ipaddress.IPv4Address | ipaddress.IPv6Address,
    *,
    allow_localhost: bool = False,
) -> None:
    """Raise ValueError if a resolved IP is in a blocked range."""
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped

    # Check metadata IPs first (before link-local, since metadata IPs are link-local)
    if str(addr) in _BLOCKED_METADATA_IPS:
        raise ValueError(f"DNS resolved to metadata endpoint: {addr}")

    if addr.is_loopback:
        if not allow_localhost:
            raise ValueError(f"DNS resolved to loopback: {addr}")
        return

    if addr.is_link_local:
        raise ValueError(f"DNS resolved to link-local: {addr}")

    if addr.is_private:
        if not allow_localhost:
            raise ValueError(f"DNS resolved to private IP: {addr}")
        return


class SSRFSafeTransport(httpx.AsyncBaseTransport):
    """Transport that validates resolved IPs before connecting."""

    def __init__(self) -> None:
        self._inner = httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        hostname = request.url.host
        if hostname:
            await self._validate_resolved_ips(hostname)
        return await self._inner.handle_async_request(request)

    async def _validate_resolved_ips(self, hostname: str) -> None:
        allow_lh = _allow_localhost()

        # If it's already an IP literal, validate directly.
        try:
            addr = ipaddress.ip_address(hostname)
        except ValueError:
            pass  # Not an IP literal — resolve DNS below
        else:
            _check_resolved_ip(addr, allow_localhost=allow_lh)
            return

        loop = asyncio.get_event_loop()
        addrs = await loop.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
        for family, _, _, _, sockaddr in addrs:
            ip_str = sockaddr[0]
            addr = ipaddress.ip_address(ip_str)
            _check_resolved_ip(addr, allow_localhost=allow_lh)

    async def aclose(self) -> None:
        await self._inner.aclose()


# --- HTTP fetch ---


async def http_fetch(
    url: str, *, timeout: int | None = None
) -> tuple[int, dict[str, str], bytes, str]:
    """Fetch a URL with SSRF protection. Returns (status, headers_dict, body, final_url)."""
    t = timeout if timeout is not None else _get_browse_timeout()
    async with httpx.AsyncClient(
        transport=SSRFSafeTransport(),
        follow_redirects=True,
        event_hooks={"request": [_ssrf_request_hook]},
        headers=_BROWSER_HEADERS,
        timeout=httpx.Timeout(t),
    ) as client:
        response = await client.get(url)
        headers = {k.lower(): v for k, v in response.headers.items()}
        return response.status_code, headers, response.content, str(response.url)


# --- Bot detection heuristics ---

_CF_CHALLENGE_TITLES = {b"just a moment", b"attention required", b"please wait"}
_CAPTCHA_MARKERS = {b"captcha", b"recaptcha", b"hcaptcha", b"cf-turnstile"}
_CHALLENGE_HEADERS = {"cf-ray", "x-amzn-captcha", "x-sucuri-id"}


def _is_bot_blocked(status: int, headers: dict[str, str], body: bytes) -> bool:
    """Detect if an HTTP response is a bot challenge rather than real content."""
    body_lower = body.lower()

    # Cloudflare / Akamai challenge title
    for title in _CF_CHALLENGE_TITLES:
        if b"<title>" + title in body_lower:
            return True

    # Challenge headers with blocked status
    if status in (403, 429):
        for header in _CHALLENGE_HEADERS:
            if header in headers:
                return True

    # CAPTCHA markers in body — only flag with suspicious status codes
    # to avoid false positives on pages that merely discuss CAPTCHAs
    if status in (403, 429, 503, 200):
        # For non-200, any CAPTCHA marker is suspicious
        if status != 200:
            for marker in _CAPTCHA_MARKERS:
                if marker in body_lower:
                    return True
        else:
            # For 200: only trigger if CAPTCHA marker appears near form/challenge elements
            for marker in _CAPTCHA_MARKERS:
                if marker in body_lower and (b"<form" in body_lower or b"challenge" in body_lower):
                    return True

    # JS-redirect-only page: small body dominated by <script> tags
    if len(body) < 2000:
        script_count = body_lower.count(b"<script")
        text_without_tags = body_lower
        for tag in [b"<script", b"</script>", b"<html", b"</html>", b"<head", b"</head>", b"<body", b"</body>", b"<meta", b"<link"]:
            text_without_tags = text_without_tags.replace(tag, b"")
        stripped = text_without_tags.strip()
        if script_count >= 2 and len(stripped) < 100:
            return True

    return False


# --- Browser fallback ---


async def _browser_fetch(url: str) -> tuple[str, str]:
    """Fetch a page using a transient botasaurus browser. Returns (html, final_url).

    Uses a semaphore to limit concurrent browser instances to 2.
    """
    from botasaurus_driver import Driver

    async with _get_browser_semaphore():
        def _fetch_sync() -> tuple[str, str]:
            driver = Driver(headless=True)
            try:
                driver.get(url, wait=_BROWSER_FALLBACK_TIMEOUT)
                html = driver.page_html
                final_url = driver.current_url
                return html, final_url
            finally:
                try:
                    driver.close()
                except Exception:
                    pass

        return await asyncio.wait_for(
            asyncio.to_thread(_fetch_sync),
            timeout=_BROWSER_FALLBACK_TIMEOUT + 5,  # grace period beyond page wait
        )
