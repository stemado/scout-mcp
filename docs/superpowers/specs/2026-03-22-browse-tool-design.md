# Browse Tool Design Spec

**Date:** 2026-03-22
**Status:** Approved
**Author:** Claude + sdoherty

## Problem

Scout's full toolkit (20 MCP tools) adds ~4K tokens of overhead for simple page lookups. When an AI client just needs to read a web page — e.g., "What's the latest Supreme Court decision?" — the launch→scout→close cycle requires 3 tool calls and returns structured DOM data (element selectors, iframe maps) when the user wanted readable content.

Claude Code's built-in `WebFetch` tool handles this cheaply (~2K tokens round trip), but Scout users shouldn't need to know about external tools. Scout should offer its own lightweight option that leverages its stealth browser as a competitive advantage.

## Solution

A single `browse` MCP tool that fetches a URL, extracts clean content, and optionally filters by a query — all in one tool call.

### Design Principles

- **One tool call, content out** — no sessions, no multi-step flows
- **HTTP-first, browser fallback** — fast by default, stealth when needed
- **Zero config works, premium config is better** — keyword scoring out of the box, LLM extraction opt-in
- **Session-independent side-channel** — usable mid-Scout-session without disturbing the active browser

## Tool Interface

```python
@mcp.tool()
async def browse(
    url: str,                      # Required — the page to fetch
    query: str | None = None,      # Optional — extract only relevant content
    max_length: int | None = None  # Optional — cap response length in chars
) -> BrowseResult:
    ...
```

### BrowseResult Model

```python
class BrowseResult(BaseModel):
    success: bool       # Whether the fetch and extraction succeeded
    url: str            # Final URL (after redirects)
    title: str          # Page title
    content: str        # Clean markdown (full or extracted)
    extraction_mode: str  # "full" or "extracted"
    fetch_method: str   # "http" or "browser"
    error: str | None = None  # Error message if success is False
```

### Example Call

```
browse(
    url="https://supremecourt.gov/opinions/slipopinion/25",
    query="latest decision"
)
```

Returns ~100-300 tokens of focused content instead of ~4K tokens of DOM structure.

## Internal Pipeline

Four layers, executed in sequence:

### Layer 0 — Content-Type Detection

Before fetching, and after receiving the response:

- **JSON responses** (`application/json`): Pretty-print and return directly, skip trafilatura
- **Plain text** (`text/plain`): Return as-is, skip trafilatura
- **HTML** (`text/html`): Proceed through the normal pipeline
- **PDF/binary/unsupported**: Return error with `success=False` and a descriptive message

### Layer 1 — HTTP Fast Path

- `httpx` async GET with browser-like headers (User-Agent, Accept, Accept-Language)
- Follow redirects (httpx default limit of 20)
- SSRF protection via Scout's existing `validation.py` URL checks (IPv6 normalization, localhost blocking)
- **SSRF validation is applied to the final URL after redirect resolution**, not just the initial URL — a redirect chain could bounce to internal IPs

### Layer 2 — Stealth Browser Fallback

Triggered when the HTTP response looks like a bot block:

- Cloudflare/Akamai challenge page signatures
- Near-empty body with heavy `<script>` tags and JS redirects
- 403/429 with challenge headers (e.g., `cf-ray`, `x-amzn-captcha`)
- CAPTCHA markers in HTML

Detection heuristics are implementation details defined in `browse.py`, with minimum coverage for: Cloudflare challenge pages (e.g., `<title>Just a moment...</title>`), Akamai Bot Manager, and generic JS-redirect-only pages (minimal body, heavy `<script>` content).

When triggered:

- Spins up a **transient** headless botasaurus-driver instance
- Browser fallback timeout: 30 seconds (independent of HTTP timeout)
- Browser teardown uses `try/finally` to guarantee cleanup on any exception
- **Concurrency limit**: max 2 simultaneous browser fallbacks (async semaphore) to prevent Chrome process storms
- Navigates to URL, waits for JS rendering, captures fully-rendered DOM
- Tears down the browser immediately after
- **Never touches an active Scout session** — this is a completely separate Chrome instance
- If the browser fallback also fails (e.g., hard CAPTCHA), return error with `success=False` — do not retry

### Layer 3 — Content Extraction (always runs)

- `trafilatura` extracts main content from raw HTML
- Strips navigation, footers, ads, scripts, sidebars, cookie banners
- Converts to clean markdown preserving document structure (headings, lists, links, tables)
- If `max_length` is `None`, uses `SCOUT_BROWSE_MAX_LENGTH` (default 5000 chars). Pass `max_length=0` to disable truncation.
- Truncation happens at paragraph boundaries (never mid-sentence)

### Layer 4 — Query Extraction (only when `query` is provided)

Two modes:

**Default mode (no config needed):**
- BM25-style keyword scoring using a lightweight custom implementation (no additional dependencies)
- Ranks each paragraph by relevance to the query
- Returns top-N most relevant passages in document order

**Premium mode (when `SCOUT_BROWSE_MODEL` is configured):**
- Sends extracted content + query to a configured LLM endpoint via `providers.py`
- LLM returns only the content that answers the query
- On LLM failure (timeout, rate limit, error), falls back to keyword scoring with a warning in the response
- Generic provider interface supporting multiple backends

### Provider Interface (`providers.py`)

```python
async def extract_with_llm(content: str, query: str, provider: str, model: str) -> str:
    """Send content + query to an LLM for focused extraction.

    Raises ProviderError on failure (caller falls back to keyword scoring).
    """
```

- System prompt: "Extract only the content from the following text that is relevant to the user's query. Return the relevant passages as-is, preserving formatting. If nothing is relevant, say so."
- Input is capped at ~8K tokens to avoid excessive costs
- Timeout: 15 seconds per provider call

## Configuration

Three optional environment variables:

| Variable | Format | Default | Purpose |
|----------|--------|---------|---------|
| `SCOUT_BROWSE_MODEL` | `provider:model` | *(none — uses keyword scoring)* | LLM for query extraction |
| `SCOUT_BROWSE_TIMEOUT` | seconds | `10` | HTTP fetch timeout |
| `SCOUT_BROWSE_MAX_LENGTH` | chars | `5000` | Default content length cap |

### Provider Format

```
SCOUT_BROWSE_MODEL=anthropic:claude-sonnet-4-20250514
SCOUT_BROWSE_MODEL=openai:gpt-4o-mini
SCOUT_BROWSE_MODEL=ollama:phi3
```

API keys follow standard conventions:
- `anthropic` provider → reads `ANTHROPIC_API_KEY`
- `openai` provider → reads `OPENAI_API_KEY`
- `ollama` provider → no key needed (local)

SDKs are lazy-imported — only loaded when that provider is actually configured. Not hard dependencies.

## Mid-Session Use Case

The primary differentiator from WebFetch: `browse` works as a **side-channel during active Scout sessions**.

Example flow:

```
1. Scout session active → browser on Reddit thread
2. Claude needs today's Supreme Court ruling for a comment
3. Claude calls browse(url="...", query="latest ruling")
   └─ HTTP fetch (fast, ~200ms)
   └─ trafilatura cleans content
   └─ Keyword scoring extracts relevant passage
   └─ Returns: case name, date, summary
4. Claude has the info in its context
5. Claude calls execute_action_tool(session_id, "type", "Based on today's ruling...")
   └─ Types into the Reddit comment box via the EXISTING Scout session
```

The Scout browser stays parked on Reddit the entire time. `browse` operates on a completely separate channel. Claude bridges the two through its natural multi-tool reasoning.

This works because MCP tool calls are stateless and independent. A Scout session persists server-side between calls, but Claude is free to call any other tool in between.

## Codebase Changes

### New Files

| File | Purpose |
|------|---------|
| `src/scout/browse.py` | Core pipeline: fetch → detect → fallback → clean → extract |
| `src/scout/providers.py` | Thin LLM provider routing (anthropic, openai, ollama) |
| `tests/test_browse.py` | Unit tests for all pipeline layers |

### Modified Files

| File | Change |
|------|--------|
| `src/scout/server.py` | Add `@mcp.tool() browse()` definition (~40 lines) |
| `src/scout/models.py` | Add `BrowseResult` Pydantic model (tool uses inline params, no request model needed) |
| `pyproject.toml` | Add `trafilatura` dependency (note: `httpx` is already present) |

### Unchanged Files

- `session.py` — browse is session-independent
- `scout.py` — page reconnaissance is a separate concern
- `actions.py` — no browser interactions
- `network.py` — no CDP monitoring needed
- `validation.py` — reused via import, no modifications

## Token Economics

| Approach | Tool Calls | Overhead | Content Tokens |
|----------|-----------|----------|----------------|
| Scout (current) | 3 (launch+scout+close) | ~4K | DOM structure, not readable |
| WebFetch (built-in) | 1 | ~2K | Pre-digested by secondary model |
| **browse (this spec)** | **1** | **~200** | **Clean markdown or focused extract** |

## Security

- All `browse()` output passes through Scout's `sanitize_response()` pipeline before returning to the AI client, consistent with every other Scout tool. Registered secret values are scrubbed.
- SSRF validation on both initial URL and final URL after redirect resolution
- Browser fallback concurrency limited to prevent resource exhaustion

## Dependencies

- `httpx` — already a dependency, no addition needed
- `trafilatura` — content extraction library, mature and battle-tested
- `anthropic` / `openai` SDKs — lazy imports, only loaded when that provider is configured. Not hard dependencies.
