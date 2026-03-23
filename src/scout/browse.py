"""Browse tool — lightweight page fetch with content extraction.

Pipeline: HTTP fetch -> bot detection -> browser fallback -> content extraction -> query extraction -> truncation.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json as _json
import math
import os
import re as _re
import socket
from typing import Any

import httpx
import trafilatura

from .models import BrowseResult
from .providers import ProviderError, extract_with_llm, parse_model_config
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


# --- BM25-style keyword extraction ---


def keyword_extract(text: str, *, query: str, max_passages: int = 5) -> str:
    """Extract the most relevant paragraphs using BM25-style scoring.

    Returns passages in their original document order.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return ""

    query_terms = _re.findall(r"\w+", query.lower())
    if not query_terms:
        return text

    # BM25 parameters
    k1 = 1.5
    b = 0.75
    avg_dl = sum(len(p.split()) for p in paragraphs) / len(paragraphs)

    df: dict[str, int] = {}
    for term in query_terms:
        df[term] = sum(1 for p in paragraphs if term in p.lower())

    scored: list[tuple[int, float]] = []
    for i, para in enumerate(paragraphs):
        words = para.lower().split()
        dl = len(words)
        score = 0.0
        for term in query_terms:
            tf = words.count(term)
            idf = math.log(
                (len(paragraphs) - df.get(term, 0) + 0.5)
                / (df.get(term, 0) + 0.5)
                + 1
            )
            numerator = tf * (k1 + 1)
            denominator = tf + k1 * (1 - b + b * dl / avg_dl)
            score += idf * numerator / denominator
        scored.append((i, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    top_indices = sorted([idx for idx, _ in scored[:max_passages]])
    return "\n\n".join(paragraphs[i] for i in top_indices)


# --- Main browse pipeline ---


async def browse(
    url: str,
    query: str | None = None,
    max_length: int | None = None,
) -> BrowseResult:
    """Fetch a URL, extract clean content, optionally filter by query."""
    # Validate URL upfront
    try:
        validate_url(url, allow_localhost=_allow_localhost())
    except ValueError as e:
        return BrowseResult(success=False, url=url, error=str(e))

    effective_max = max_length if max_length is not None else _get_browse_max_length()

    fetch_method = "http"
    html: str = ""
    final_url = url
    content_type = "text/html"

    # Layer 1: HTTP fast path
    try:
        status, headers, body, final_url = await http_fetch(url)
        content_type = headers.get("content-type", "text/html")

        # Layer 0: Content-type detection for non-HTML
        ct_base = content_type.lower().split(";")[0].strip()
        if ct_base in ("application/json", "text/plain"):
            title, content = await extract_content(
                body.decode(errors="replace"), content_type=ct_base
            )
            return BrowseResult(
                success=True, url=final_url, title=title,
                content=truncate_at_paragraph(content, max_length=effective_max),
                extraction_mode="full", fetch_method="http",
            )

        if ct_base not in ("text/html", "application/xhtml+xml", ""):
            return BrowseResult(
                success=False, url=final_url,
                error=f"Unsupported content type: {ct_base}",
            )

        html = body.decode(errors="replace")

        # Layer 2: Bot detection → browser fallback
        if _is_bot_blocked(status, headers, body):
            try:
                html, final_url = await _browser_fetch(url)
                fetch_method = "browser"
            except Exception as e:
                return BrowseResult(
                    success=False, url=url,
                    error=f"Browser fallback failed: {e}",
                    fetch_method="browser",
                )

    except ValueError as e:
        return BrowseResult(success=False, url=url, error=str(e))
    except httpx.TimeoutException:
        return BrowseResult(success=False, url=url, error="HTTP request timed out")
    except httpx.HTTPError as e:
        return BrowseResult(success=False, url=url, error=f"HTTP error: {e}")

    # Layer 3: Content extraction
    title, content = await extract_content(html)
    if not content:
        return BrowseResult(
            success=True, url=final_url, title=title, content="",
            extraction_mode="full", fetch_method=fetch_method,
        )

    # Layer 4: Query extraction (optional)
    extraction_mode = "full"
    if query:
        extraction_mode = "extracted"
        model_config = os.environ.get("SCOUT_BROWSE_MODEL")
        if model_config:
            try:
                provider, model = parse_model_config(model_config)
                content = await extract_with_llm(content, query, provider, model)
            except (ProviderError, ValueError):
                content = keyword_extract(content, query=query)
        else:
            content = keyword_extract(content, query=query)

    # Truncation (final step)
    content = truncate_at_paragraph(content, max_length=effective_max)

    return BrowseResult(
        success=True, url=final_url, title=title, content=content,
        extraction_mode=extraction_mode, fetch_method=fetch_method,
    )


# --- Content extraction ---


async def extract_content(
    raw: str, *, content_type: str = "text/html"
) -> tuple[str, str]:
    """Extract clean content from raw response. Returns (title, markdown_content).

    Handles HTML (via trafilatura), JSON (pretty-print), and plain text (passthrough).
    trafilatura is sync and can be slow on large pages, so it runs in a thread.
    """
    ct = content_type.lower().split(";")[0].strip()

    if ct == "application/json":
        try:
            parsed = _json.loads(raw)
            return "", _json.dumps(parsed, indent=2)
        except _json.JSONDecodeError:
            return "", raw

    if ct == "text/plain":
        return "", raw

    # HTML extraction via trafilatura — run in thread to avoid blocking the event loop
    result = await asyncio.to_thread(
        trafilatura.extract,
        raw,
        include_links=True,
        include_tables=True,
        output_format="txt",
        favor_recall=True,
    )

    # Extract title from HTML
    title = ""
    raw_lower = raw.lower() if isinstance(raw, str) else raw.decode(errors="replace").lower()
    start = raw_lower.find("<title>")
    end = raw_lower.find("</title>")
    if start != -1 and end != -1:
        title_raw = raw[start + 7:end] if isinstance(raw, str) else raw.decode(errors="replace")[start + 7:end]
        title = title_raw.strip()

    return title, result or ""


# --- Truncation ---


def truncate_at_paragraph(text: str, *, max_length: int) -> str:
    """Truncate text at paragraph boundaries. max_length=0 disables truncation."""
    if max_length == 0 or len(text) <= max_length:
        return text

    paragraphs = text.split("\n\n")
    result: list[str] = []
    current_length = 0

    for para in paragraphs:
        addition = len(para) + (2 if result else 0)
        if current_length + addition > max_length and result:
            break
        result.append(para)
        current_length += addition

    return "\n\n".join(result)
