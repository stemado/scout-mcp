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
