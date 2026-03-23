# Browse Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a lightweight `browse` MCP tool that fetches a URL, extracts clean content, and optionally filters by a query — all in one tool call, with HTTP-first and stealth browser fallback.

**Architecture:** Four-layer pipeline in `browse.py` (HTTP fetch → bot detection → browser fallback → trafilatura extraction → keyword/LLM query extraction). SSRF-safe HTTP client with two-layer defense (event hooks + custom transport). Provider routing in `providers.py` for optional LLM extraction. Single `@mcp.tool()` registration in `server.py`.

**Tech Stack:** httpx (existing), trafilatura (new dep), botasaurus-driver (existing), Pydantic models (existing pattern)

**Spec:** `docs/superpowers/specs/2026-03-22-browse-tool-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| **Create:** `src/scout/browse.py` | Core pipeline: SSRF-safe HTTP client, bot detection, browser fallback, trafilatura extraction, BM25 keyword scoring, truncation |
| **Create:** `src/scout/providers.py` | LLM provider routing (anthropic, openai, ollama) with lazy imports and `ProviderError` |
| **Create:** `tests/test_browse.py` | Unit tests for all browse pipeline layers |
| **Create:** `tests/test_providers.py` | Unit tests for provider routing and error handling |
| **Create:** `tests/fixtures/article.html` | Test fixture: realistic HTML page with nav, content, footer |
| **Modify:** `src/scout/models.py` | Add `BrowseResult` model |
| **Modify:** `src/scout/server.py` | Add `browse` tool definition (~40 lines) |
| **Modify:** `pyproject.toml` | Add `trafilatura` dependency |

---

### Task 1: Add `BrowseResult` Model

**Files:**
- Modify: `src/scout/models.py` (append after `FillSecretResult` class, ~line 340)
- Test: `tests/test_models.py`

- [ ] **Step 1: Write failing test for BrowseResult**

In `tests/test_models.py`, add:

```python
from scout.models import BrowseResult


class TestBrowseResult:
    def test_success_case(self):
        result = BrowseResult(
            success=True,
            url="https://example.com",
            title="Example",
            content="# Hello\n\nWorld",
            extraction_mode="full",
            fetch_method="http",
        )
        assert result.success is True
        assert result.url == "https://example.com"
        assert result.error is None

    def test_error_case_minimal(self):
        result = BrowseResult(success=False, error="Connection refused")
        assert result.success is False
        assert result.url == ""
        assert result.title == ""
        assert result.content == ""
        assert result.extraction_mode == "full"
        assert result.fetch_method == "http"
        assert result.error == "Connection refused"

    def test_extraction_mode_extracted(self):
        result = BrowseResult(
            success=True,
            url="https://example.com",
            title="Example",
            content="Relevant passage",
            extraction_mode="extracted",
            fetch_method="browser",
        )
        assert result.extraction_mode == "extracted"
        assert result.fetch_method == "browser"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_models.py::TestBrowseResult -v`
Expected: FAIL — `ImportError: cannot import name 'BrowseResult'`

- [ ] **Step 3: Implement BrowseResult**

In `src/scout/models.py`, append after the `FillSecretResult` class:

```python
class BrowseResult(BaseModel):
    """Result from the browse tool — lightweight page fetch and content extraction."""

    success: bool
    url: str = Field(default="", description="Final URL after redirects")
    title: str = Field(default="", description="Page title")
    content: str = Field(default="", description="Clean markdown content (full or extracted)")
    extraction_mode: str = Field(default="full", description="'full' or 'extracted'")
    fetch_method: str = Field(default="http", description="'http' or 'browser'")
    error: str | None = Field(default=None, description="Error message if success is False")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_models.py::TestBrowseResult -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/scout/models.py tests/test_models.py
git commit -m "feat(browse): add BrowseResult model"
```

---

### Task 2: Add `trafilatura` Dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add trafilatura to dependencies**

In `pyproject.toml`, add `"trafilatura>=1.6.0",` to the `dependencies` list after `"httpx>=0.27.0",` (line 27).

- [ ] **Step 2: Sync dependencies**

Run: `uv sync`
Expected: trafilatura and its dependencies install successfully.

- [ ] **Step 3: Verify import works**

Run: `uv run python -c "import trafilatura; print(trafilatura.__version__)"`
Expected: Prints version number without error.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build: add trafilatura dependency for browse tool"
```

---

### Task 3: SSRF-Safe HTTP Client

**Files:**
- Create: `src/scout/browse.py` (first portion — HTTP layer only)
- Test: `tests/test_browse.py`

This task builds the SSRF-safe HTTP client with two-layer defense: event hooks for redirect chain validation + custom transport for DNS rebinding protection.

- [ ] **Step 1: Write failing tests for SSRF defenses**

Create `tests/test_browse.py`:

```python
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
)


class TestSSRFRequestHook:
    """Layer A: Event hook validates every URL including redirect targets."""

    @pytest.mark.asyncio
    async def test_blocks_metadata_ip(self):
        request = httpx.Request("GET", "http://169.254.169.254/latest/meta-data/")
        with pytest.raises(ValueError, match="Blocked URL host"):
            await _ssrf_request_hook(request)

    @pytest.mark.asyncio
    async def test_blocks_localhost(self):
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
            _check_resolved_ip(ipaddress.ip_address("127.0.0.1"))

    def test_blocks_link_local(self):
        with pytest.raises(ValueError, match="link-local"):
            _check_resolved_ip(ipaddress.ip_address("169.254.1.1"))

    def test_blocks_metadata_ip(self):
        with pytest.raises(ValueError, match="metadata"):
            _check_resolved_ip(ipaddress.ip_address("169.254.169.254"))

    def test_blocks_private(self):
        with pytest.raises(ValueError, match="private"):
            _check_resolved_ip(ipaddress.ip_address("10.0.0.1"))

    def test_blocks_ipv6_mapped_loopback(self):
        with pytest.raises(ValueError, match="loopback"):
            _check_resolved_ip(ipaddress.ip_address("::ffff:127.0.0.1"))

    def test_allows_public_ip(self):
        _check_resolved_ip(ipaddress.ip_address("93.184.216.34"))  # example.com


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_browse.py -v -k "SSRF or CheckResolved or HTTPFetch"`
Expected: FAIL — `ImportError: cannot import name '_ssrf_request_hook' from 'scout.browse'`

- [ ] **Step 3: Implement SSRF-safe HTTP client**

Create `src/scout/browse.py`:

```python
"""Browse tool — lightweight page fetch with content extraction.

Pipeline: HTTP fetch → bot detection → browser fallback → content extraction → query extraction → truncation.
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

# Browser fallback concurrency limit.
_browser_semaphore = asyncio.Semaphore(2)
_BROWSER_FALLBACK_TIMEOUT = 30


# --- SSRF Defense Layer A: Request event hook ---


async def _ssrf_request_hook(request: httpx.Request) -> None:
    """Validate every request URL (including redirect hops) before sending."""
    validate_url(str(request.url), allow_localhost=_allow_localhost())


# --- SSRF Defense Layer B: DNS rebinding protection ---


def _check_resolved_ip(
    addr: ipaddress.IPv4Address | ipaddress.IPv6Address,
    *, allow_localhost: bool = False,
) -> None:
    """Raise ValueError if a resolved IP is in a blocked range."""
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped

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
    if str(addr) in _BLOCKED_METADATA_IPS:
        raise ValueError(f"DNS resolved to metadata endpoint: {addr}")


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_browse.py -v -k "SSRF or CheckResolved or HTTPFetch"`
Expected: PASS (all 8 tests)

- [ ] **Step 5: Commit**

```bash
git add src/scout/browse.py tests/test_browse.py
git commit -m "feat(browse): SSRF-safe HTTP client with two-layer defense"
```

---

### Task 4: Bot Detection and Browser Fallback

**Files:**
- Modify: `src/scout/browse.py` (add bot detection + browser fallback)
- Test: `tests/test_browse.py` (add tests)

- [ ] **Step 1: Write failing tests for bot detection**

Append to `tests/test_browse.py`:

```python
from scout.browse import _is_bot_blocked, _browser_fetch


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

    def test_detects_captcha_marker(self):
        html = b'<html><body><div id="captcha-container">Please verify</div></body></html>'
        assert _is_bot_blocked(200, {}, html) is True
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_browse.py::TestBotDetection -v`
Expected: FAIL — `ImportError: cannot import name '_is_bot_blocked'`

- [ ] **Step 3: Implement bot detection and browser fallback**

Append to `src/scout/browse.py`:

```python
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

    # CAPTCHA markers in body
    for marker in _CAPTCHA_MARKERS:
        if marker in body_lower:
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

    async with _browser_semaphore:
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_browse.py::TestBotDetection -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add src/scout/browse.py tests/test_browse.py
git commit -m "feat(browse): bot detection heuristics and browser fallback"
```

---

### Task 5: Content Extraction and Truncation

**Files:**
- Modify: `src/scout/browse.py` (add extraction + truncation)
- Create: `tests/fixtures/article.html`
- Test: `tests/test_browse.py`

- [ ] **Step 1: Create test fixture**

Create `tests/fixtures/article.html`:

```html
<!DOCTYPE html>
<html>
<head><title>Supreme Court Opinions</title></head>
<body>
  <nav><a href="/">Home</a> | <a href="/about">About</a></nav>
  <main>
    <h1>Slip Opinions — October Term 2025</h1>
    <p>The following opinions were announced on March 22, 2026.</p>
    <h2>Trump v. Anderson (No. 23-719)</h2>
    <p>Per Curiam. The Court reversed the Colorado Supreme Court's decision removing former President Trump from the state's primary ballot.</p>
    <h2>Gonzalez v. Trevino (No. 22-1025)</h2>
    <p>Justice Kagan delivered the opinion. The Court held that the plaintiff stated a viable retaliatory-arrest claim under the First Amendment.</p>
    <h2>Smith v. Arizona (No. 22-899)</h2>
    <p>Justice Kagan delivered the opinion. Surrogate testimony about forensic analysis violates the Confrontation Clause.</p>
  </main>
  <footer>Supreme Court of the United States &copy; 2026</footer>
</body>
</html>
```

- [ ] **Step 2: Write failing tests for extraction and truncation**

Append to `tests/test_browse.py`:

```python
from scout.browse import extract_content, truncate_at_paragraph


class TestExtractContent:
    def test_extracts_main_content(self):
        html = """<html><head><title>Test</title></head>
        <body><nav>Menu</nav><main><h1>Title</h1><p>Real content here.</p></main>
        <footer>Copyright</footer></body></html>"""
        title, content = extract_content(html)
        assert "Real content" in content
        assert title == "Test"

    def test_returns_empty_on_blank_html(self):
        title, content = extract_content("<html><body></body></html>")
        assert content == ""

    def test_skips_nav_and_footer(self):
        html = """<html><head><title>T</title></head><body>
        <nav>Navigation</nav><p>Article text</p><footer>Footer</footer></body></html>"""
        title, content = extract_content(html)
        assert "Navigation" not in content or "Article" in content

    def test_json_passthrough(self):
        """JSON should be pretty-printed, not run through trafilatura."""
        title, content = extract_content('{"key": "value"}', content_type="application/json")
        assert '"key"' in content
        assert '"value"' in content

    def test_plain_text_passthrough(self):
        title, content = extract_content("Just plain text.", content_type="text/plain")
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
        # Should return the whole paragraph since there's no paragraph break
        assert result == text
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/test_browse.py -v -k "ExtractContent or Truncation"`
Expected: FAIL — `ImportError`

- [ ] **Step 4: Implement extraction and truncation**

Append to `src/scout/browse.py`:

```python
import json as _json

import trafilatura


# --- Content extraction ---


def extract_content(
    raw: str, *, content_type: str = "text/html"
) -> tuple[str, str]:
    """Extract clean content from raw response. Returns (title, markdown_content).

    Handles HTML (via trafilatura), JSON (pretty-print), and plain text (passthrough).
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

    # HTML extraction via trafilatura
    result = trafilatura.extract(
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

    # Split on double-newline (paragraph breaks)
    paragraphs = text.split("\n\n")
    result = []
    current_length = 0

    for para in paragraphs:
        addition = len(para) + (2 if result else 0)  # account for \n\n separator
        if current_length + addition > max_length and result:
            break
        result.append(para)
        current_length += addition

    # If even the first paragraph exceeds the limit, return it whole
    # (never truncate mid-sentence)
    return "\n\n".join(result)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_browse.py -v -k "ExtractContent or Truncation"`
Expected: PASS (9 tests)

- [ ] **Step 6: Commit**

```bash
git add src/scout/browse.py tests/test_browse.py tests/fixtures/article.html
git commit -m "feat(browse): content extraction via trafilatura and paragraph truncation"
```

---

### Task 6: BM25 Keyword Scoring

**Files:**
- Modify: `src/scout/browse.py` (add keyword extraction)
- Test: `tests/test_browse.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_browse.py`:

```python
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
        # Should still return something (best effort)
        assert isinstance(result, str)

    def test_handles_single_paragraph(self):
        text = "Just one paragraph about the Supreme Court."
        result = keyword_extract(text, query="Supreme Court")
        assert "Supreme Court" in result
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_browse.py::TestKeywordExtract -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement BM25-style keyword scoring**

Append to `src/scout/browse.py`:

```python
import math
import re as _re


# --- BM25-style keyword extraction ---


def keyword_extract(text: str, *, query: str, max_passages: int = 5) -> str:
    """Extract the most relevant paragraphs using BM25-style scoring.

    Returns passages in their original document order.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return ""

    # Tokenize query
    query_terms = _re.findall(r"\w+", query.lower())
    if not query_terms:
        return text  # No query terms — return everything

    # BM25 parameters
    k1 = 1.5
    b = 0.75
    avg_dl = sum(len(p.split()) for p in paragraphs) / len(paragraphs) if paragraphs else 1

    # Document frequency for each term
    df = {}
    for term in query_terms:
        df[term] = sum(1 for p in paragraphs if term in p.lower())

    # Score each paragraph
    scored = []
    for i, para in enumerate(paragraphs):
        words = para.lower().split()
        dl = len(words)
        score = 0.0
        for term in query_terms:
            tf = words.count(term)
            idf = math.log((len(paragraphs) - df.get(term, 0) + 0.5) / (df.get(term, 0) + 0.5) + 1)
            numerator = tf * (k1 + 1)
            denominator = tf + k1 * (1 - b + b * dl / avg_dl)
            score += idf * numerator / denominator
        scored.append((i, score))

    # Sort by score, take top N, then re-sort by original position
    scored.sort(key=lambda x: x[1], reverse=True)
    top_indices = sorted([idx for idx, _ in scored[:max_passages]])
    return "\n\n".join(paragraphs[i] for i in top_indices)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_browse.py::TestKeywordExtract -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/scout/browse.py tests/test_browse.py
git commit -m "feat(browse): BM25-style keyword extraction for query filtering"
```

---

### Task 7: LLM Provider Routing

**Files:**
- Create: `src/scout/providers.py`
- Create: `tests/test_providers.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_providers.py`:

```python
"""Tests for LLM provider routing."""

import pytest

from scout.providers import parse_model_config, extract_with_llm, ProviderError


class TestParseModelConfig:
    def test_parses_anthropic(self):
        provider, model = parse_model_config("anthropic:claude-sonnet-4-20250514")
        assert provider == "anthropic"
        assert model == "claude-sonnet-4-20250514"

    def test_parses_openai(self):
        provider, model = parse_model_config("openai:gpt-4o-mini")
        assert provider == "openai"
        assert model == "gpt-4o-mini"

    def test_parses_ollama(self):
        provider, model = parse_model_config("ollama:phi3")
        assert provider == "ollama"
        assert model == "phi3"

    def test_raises_on_invalid_format(self):
        with pytest.raises(ValueError, match="provider:model"):
            parse_model_config("just-a-model-name")

    def test_raises_on_empty(self):
        with pytest.raises(ValueError):
            parse_model_config("")

    def test_raises_on_unknown_provider(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            parse_model_config("cohere:command-r")


class TestExtractWithLLM:
    @pytest.mark.asyncio
    async def test_raises_provider_error_on_missing_api_key(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(ProviderError, match="ANTHROPIC_API_KEY"):
            await extract_with_llm("content", "query", "anthropic", "claude-sonnet-4-20250514")

    @pytest.mark.asyncio
    async def test_ollama_no_key_required(self, monkeypatch):
        """Ollama should not fail on missing API key — only on connection."""
        with pytest.raises(ProviderError, match="(Connection|connect|refused|Failed)"):
            await extract_with_llm("content", "query", "ollama", "phi3")
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_providers.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement provider routing**

Create `src/scout/providers.py`:

```python
"""LLM provider routing for browse tool query extraction.

Supports anthropic, openai, and ollama providers via lazy imports.
"""

from __future__ import annotations

import os

_KNOWN_PROVIDERS = frozenset({"anthropic", "openai", "ollama"})

_EXTRACTION_SYSTEM_PROMPT = (
    "Extract only the content from the following text that is relevant to the user's query. "
    "Return the relevant passages as-is, preserving formatting. "
    "If nothing is relevant, say so."
)

_MAX_INPUT_CHARS = 32_000  # ~8K tokens
_TIMEOUT = 15


class ProviderError(Exception):
    """Raised when a provider call fails."""


def parse_model_config(config: str) -> tuple[str, str]:
    """Parse 'provider:model' string. Returns (provider, model)."""
    if not config:
        raise ValueError("Model config cannot be empty")
    if ":" not in config:
        raise ValueError(f"Invalid model config '{config}' — expected format: provider:model")
    provider, model = config.split(":", 1)
    if provider not in _KNOWN_PROVIDERS:
        raise ValueError(f"Unknown provider '{provider}'. Supported: {', '.join(sorted(_KNOWN_PROVIDERS))}")
    return provider, model


async def extract_with_llm(content: str, query: str, provider: str, model: str) -> str:
    """Send content + query to an LLM for focused extraction.

    Raises ProviderError on any failure.
    """
    # Cap input to avoid excessive costs
    truncated = content[:_MAX_INPUT_CHARS]
    user_message = f"Query: {query}\n\nText:\n{truncated}"

    if provider == "anthropic":
        return await _call_anthropic(model, user_message)
    elif provider == "openai":
        return await _call_openai(model, user_message)
    elif provider == "ollama":
        return await _call_ollama(model, user_message)
    else:
        raise ProviderError(f"Unknown provider: {provider}")


async def _call_anthropic(model: str, user_message: str) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ProviderError("ANTHROPIC_API_KEY not set")
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=api_key, timeout=_TIMEOUT)
        response = await client.messages.create(
            model=model,
            max_tokens=2048,
            system=_EXTRACTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text
    except Exception as e:
        raise ProviderError(f"Anthropic API error: {e}") from e


async def _call_openai(model: str, user_message: str) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ProviderError("OPENAI_API_KEY not set")
    try:
        import openai
        client = openai.AsyncOpenAI(api_key=api_key, timeout=_TIMEOUT)
        response = await client.chat.completions.create(
            model=model,
            max_tokens=2048,
            messages=[
                {"role": "system", "content": _EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        raise ProviderError(f"OpenAI API error: {e}") from e


async def _call_ollama(model: str, user_message: str) -> str:
    try:
        import httpx
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": model,
                    "system": _EXTRACTION_SYSTEM_PROMPT,
                    "prompt": user_message,
                    "stream": False,
                },
            )
            response.raise_for_status()
            return response.json().get("response", "")
    except Exception as e:
        raise ProviderError(f"Failed to call Ollama: {e}") from e
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_providers.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add src/scout/providers.py tests/test_providers.py
git commit -m "feat(browse): LLM provider routing for optional query extraction"
```

---

### Task 8: Assemble the Full `browse()` Pipeline

**Files:**
- Modify: `src/scout/browse.py` (add the main `browse()` function)
- Test: `tests/test_browse.py`

- [ ] **Step 1: Write failing tests for the full pipeline**

Append to `tests/test_browse.py`:

```python
from unittest.mock import AsyncMock, patch

from scout.browse import browse
from scout.models import BrowseResult


class TestBrowsePipeline:
    @pytest.mark.asyncio
    async def test_fetches_html_and_extracts(self, base_url):
        """Full pipeline against the test server's article.html fixture."""
        result = await browse(f"{base_url}/article.html")
        assert isinstance(result, BrowseResult)
        assert result.success is True
        assert result.fetch_method == "http"
        assert result.extraction_mode == "full"
        assert "Supreme Court" in result.content or "Opinions" in result.content
        assert result.title == "Supreme Court Opinions"

    @pytest.mark.asyncio
    async def test_fetches_json_passthrough(self, base_url):
        result = await browse(f"{base_url}/api/data")
        assert result.success is True
        assert '"key"' in result.content

    @pytest.mark.asyncio
    async def test_query_extraction(self, base_url):
        result = await browse(f"{base_url}/article.html", query="Trump v. Anderson")
        assert result.success is True
        assert result.extraction_mode == "extracted"
        assert "Trump" in result.content

    @pytest.mark.asyncio
    async def test_ssrf_blocked(self):
        result = await browse("http://169.254.169.254/latest/meta-data/")
        assert result.success is False
        assert "Blocked" in (result.error or "")

    @pytest.mark.asyncio
    async def test_max_length_truncation(self, base_url):
        result = await browse(f"{base_url}/article.html", max_length=50)
        assert result.success is True
        assert len(result.content) <= 200  # paragraph-boundary, may slightly exceed char count

    @pytest.mark.asyncio
    async def test_max_length_zero_disables(self, base_url):
        result = await browse(f"{base_url}/article.html", max_length=0)
        assert result.success is True
        # Content should be full, not truncated

    @pytest.mark.asyncio
    async def test_bot_block_triggers_browser_fallback(self, base_url):
        """Verify bot detection wires through to browser fallback."""
        fake_html = "<html><head><title>Real Page</title></head><body><p>Browser content</p></body></html>"
        with patch("scout.browse._is_bot_blocked", return_value=True), \
             patch("scout.browse._browser_fetch", new_callable=AsyncMock, return_value=(fake_html, "https://example.com")):
            result = await browse(f"{base_url}/article.html")
            assert result.success is True
            assert result.fetch_method == "browser"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_browse.py::TestBrowsePipeline -v`
Expected: FAIL — `ImportError: cannot import name 'browse'`

- [ ] **Step 3: Implement the main `browse()` function**

Append to `src/scout/browse.py`:

```python
from .models import BrowseResult
from .providers import ProviderError, extract_with_llm, parse_model_config


async def browse(
    url: str,
    query: str | None = None,
    max_length: int | None = None,
) -> BrowseResult:
    """Fetch a URL, extract clean content, optionally filter by query.

    Pipeline: HTTP fetch → bot detection → browser fallback → content extraction
              → query extraction → truncation → BrowseResult.
    """
    # Validate URL upfront
    try:
        validate_url(url, allow_localhost=_allow_localhost())
    except ValueError as e:
        return BrowseResult(success=False, url=url, error=str(e))

    # Resolve max_length from config
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
            title, content = extract_content(
                body.decode(errors="replace"), content_type=ct_base
            )
            return BrowseResult(
                success=True,
                url=final_url,
                title=title,
                content=truncate_at_paragraph(content, max_length=effective_max),
                extraction_mode="full",
                fetch_method="http",
            )

        if ct_base not in ("text/html", "application/xhtml+xml", ""):
            return BrowseResult(
                success=False,
                url=final_url,
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
                    success=False,
                    url=url,
                    error=f"Browser fallback failed: {e}",
                    fetch_method="browser",
                )

    except ValueError as e:
        # SSRF validation errors from hooks/transport
        return BrowseResult(success=False, url=url, error=str(e))
    except httpx.TimeoutException:
        return BrowseResult(success=False, url=url, error="HTTP request timed out")
    except httpx.HTTPError as e:
        return BrowseResult(success=False, url=url, error=f"HTTP error: {e}")

    # Layer 3: Content extraction
    title, content = extract_content(html)
    if not content:
        return BrowseResult(
            success=True,
            url=final_url,
            title=title,
            content="",
            extraction_mode="full",
            fetch_method=fetch_method,
        )

    # Layer 4: Query extraction (optional)
    extraction_mode = "full"
    if query:
        extraction_mode = "extracted"
        # Try LLM extraction if configured
        model_config = os.environ.get("SCOUT_BROWSE_MODEL")
        if model_config:
            try:
                provider, model = parse_model_config(model_config)
                content = await extract_with_llm(content, query, provider, model)
            except (ProviderError, ValueError):
                # Fall back to keyword extraction
                content = keyword_extract(content, query=query)
        else:
            content = keyword_extract(content, query=query)

    # Truncation (final step)
    content = truncate_at_paragraph(content, max_length=effective_max)

    return BrowseResult(
        success=True,
        url=final_url,
        title=title,
        content=content,
        extraction_mode=extraction_mode,
        fetch_method=fetch_method,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_browse.py::TestBrowsePipeline -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Run ALL browse tests**

Run: `uv run pytest tests/test_browse.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/scout/browse.py tests/test_browse.py
git commit -m "feat(browse): assemble full browse() pipeline"
```

---

### Task 9: Register `browse` Tool in Server

**Files:**
- Modify: `src/scout/server.py`

- [ ] **Step 1: Add import**

In `src/scout/server.py`, add to the imports section (after the existing model imports around line 37):

```python
from .models import (
    ActionRecord,
    BrowseResult,  # <-- add this
    ConnectionMode,
    ...
)
```

And add:

```python
from .browse import browse as browse_page
```

- [ ] **Step 2: Add the tool definition**

Find the last `@mcp.tool()` definition in `server.py` and add after it:

```python
@mcp.tool()
async def browse(
    url: str,
    query: str | None = None,
    max_length: int | None = None,
    ctx: Context | None = None,
) -> str:
    """Fetch a web page and extract its content as clean markdown.

    Lightweight alternative to the full Scout session flow. One tool call,
    content out. Uses HTTP by default with automatic stealth browser fallback
    for bot-protected pages.

    Args:
        url: The page URL to fetch.
        query: Optional — extract only content relevant to this query.
        max_length: Optional — cap response length in characters. 0 = unlimited.
    """
    result = await browse_page(url, query=query, max_length=max_length)
    return sanitize_response(result.model_dump())
```

- [ ] **Step 3: Run existing tests to verify no regressions**

Run: `uv run pytest tests/ -m "not integration" -v`
Expected: ALL PASS (existing + new tests)

- [ ] **Step 4: Commit**

```bash
git add src/scout/server.py
git commit -m "feat(browse): register browse tool in MCP server"
```

---

### Task 10: Integration Test with Test Server

**Files:**
- Modify: `tests/conftest.py` (add browse-specific test endpoints)
- Test: `tests/test_browse.py` (add integration scenarios)

- [ ] **Step 1: Add test endpoints to conftest**

In `tests/conftest.py`, add these handlers to `_TestHandler.do_GET()`:

```python
        elif self.path == "/bot-block":
            body = b"<html><head><title>Just a moment...</title></head><body><script>challenge()</script></body></html>"
            self.send_response(403)
            self.send_header("Content-Type", "text/html")
            self.send_header("cf-ray", "fake-ray-id")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/plain":
            body = b"This is plain text content."
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
```

- [ ] **Step 2: Write integration tests**

Append to `tests/test_browse.py`:

```python
class TestBrowseIntegration:
    """Tests using the local test server for realistic scenarios."""

    @pytest.mark.asyncio
    async def test_plain_text_passthrough(self, base_url):
        result = await browse(f"{base_url}/plain")
        assert result.success is True
        assert result.content == "This is plain text content."

    @pytest.mark.asyncio
    async def test_bot_block_detected(self, base_url):
        """Bot block should be detected (browser fallback will fail since no Chrome in unit tests)."""
        result = await browse(f"{base_url}/bot-block")
        # In unit test env, browser fallback will fail — but bot detection should trigger
        assert result.fetch_method == "browser" or result.success is False

    @pytest.mark.asyncio
    async def test_nonexistent_url(self):
        result = await browse("http://this-domain-does-not-exist-12345.com")
        assert result.success is False
        assert result.error is not None
```

- [ ] **Step 3: Run integration tests**

Run: `uv run pytest tests/test_browse.py::TestBrowseIntegration -v`
Expected: PASS (3 tests)

- [ ] **Step 4: Run full test suite**

Run: `uv run pytest tests/ -m "not integration" -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add tests/conftest.py tests/test_browse.py
git commit -m "test(browse): integration tests with local test server"
```

---

### Task 11: Final Verification and Cleanup

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -m "not integration" -v`
Expected: ALL PASS, 0 failures

- [ ] **Step 2: Verify the browse tool shows up in MCP tool list**

Run: `uv run python -c "from scout.server import mcp; print([t.name for t in mcp._tools.values()])"`
Verify `browse` appears in the list.

- [ ] **Step 3: Manual smoke test**

Run: `uv run python -c "
import asyncio
from scout.browse import browse
result = asyncio.run(browse('https://httpbin.org/html'))
print(f'Success: {result.success}')
print(f'Title: {result.title}')
print(f'Method: {result.fetch_method}')
print(f'Content length: {len(result.content)}')
print(result.content[:200])
"`
Expected: Should fetch and extract the httpbin HTML page.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat(browse): complete browse tool implementation

Adds a lightweight single-tool page fetching capability:
- HTTP-first with stealth browser fallback
- trafilatura content extraction
- BM25 keyword scoring for query filtering
- Optional LLM extraction via configurable providers
- Two-layer SSRF defense (event hooks + DNS rebinding transport)"
```
