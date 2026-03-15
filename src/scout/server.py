"""Scout MCP Server — Browser automation with anti-detection."""

from __future__ import annotations

import asyncio
import atexit
import os
import re
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Literal

import base64
import json

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession
from mcp.types import CallToolResult, ImageContent, TextContent

from .actions import execute_action, inspect_element, run_javascript, take_screenshot
from .models import (
    ActionRecord,
    ConnectionMode,
    DownloadEvent,
    ExtensionStatus,
    FillSecretResult,
    MonitorResult,
    ProcessResult,
    RecordingRecord,
    RecordingResult,
    ScoutReport,
    SessionCloseResult,
    SessionHistory,
    SessionInfo,
)
from .sanitize import sanitize_response
from .scout import build_element_summary, filter_elements, scout_page
from .security import (
    log_security_event,
    read_security_log,
    scan_and_warn,
    scrub_network_events,
)
from .security.navigation_guard import extract_registered_domain
from .session import BrowserSession
from .otp import poll_for_otp

# --- Numeric safety bounds ---

MAX_WAIT_MS = 60_000        # 1 minute
MAX_TIMEOUT_MS = 300_000    # 5 minutes
MAX_JS_TIMEOUT_S = 120      # 2 minutes — JS execution safety cap
MAX_RESULTS = 500           # Scout JS caps at 500 elements

# --- Session ID format ---

_SESSION_ID_RE = re.compile(r"^[0-9a-f]{12}$")
_SCHEDULE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")

# --- Application Context (lifespan-managed state) ---


@dataclass
class AppContext:
    """Holds all browser sessions across the server's lifetime."""

    sessions: dict[str, BrowserSession] = field(default_factory=dict)
    max_sessions: int = 1
    _launch_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _env_vars: dict[str, str] | None = field(default=None)
    _extension_relay: object | None = field(default=None)  # ExtensionRelay when active


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Initialize on startup, clean up all sessions on shutdown."""
    ctx = AppContext()

    def _cleanup_sync():
        """Emergency cleanup for atexit handler."""
        for session in list(ctx.sessions.values()):
            try:
                session.close()
            except Exception:
                pass

    atexit.register(_cleanup_sync)

    try:
        yield ctx
    finally:
        atexit.unregister(_cleanup_sync)
        for session in list(ctx.sessions.values()):
            try:
                await asyncio.to_thread(session.close)
            except Exception:
                pass
        # Clean up extension relay server
        if ctx._extension_relay is not None:
            try:
                await ctx._extension_relay.stop()
            except Exception:
                pass
            ctx._extension_relay = None


# --- MCP Server Instance ---

mcp = FastMCP("scout-mcp-server", lifespan=app_lifespan)


def _get_ctx(ctx: Context) -> AppContext:
    return ctx.request_context.lifespan_context


def _get_session(app_ctx: AppContext, session_id: str) -> BrowserSession:
    if not _SESSION_ID_RE.match(session_id):
        raise ValueError("Invalid session ID format: expected 12 hex characters.")
    session = app_ctx.sessions.get(session_id)
    if session is None:
        raise ValueError(f"No active session with id '{session_id}'. Use launch_session first.")
    if not session.is_active:
        raise ValueError(f"Session '{session_id}' is no longer active.")
    return session


def _get_env_vars(app_ctx: AppContext) -> dict[str, str]:
    """Lazy-load .env file on first use.

    The cache is permanent for the server's lifetime. Changes to .env
    require a server restart to take effect.
    """
    if app_ctx._env_vars is None:
        from .secrets import load_env_vars
        app_ctx._env_vars = load_env_vars()
    return app_ctx._env_vars


# --- Tool: launch_session ---


@mcp.tool()
async def launch_session(
    url: str | None = None,
    headless: bool = False,
    proxy: str | None = None,
    download_dir: str = "./downloads",
    connection_mode: str = "launch",
    allowed_domains: list[str] | None = None,
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """Launch a new browser session via Botasaurus with anti-detection enabled.

    The browser stays alive across all subsequent tool calls until close_session is called.
    Optionally navigate to an initial URL.

    Args:
        url: Initial URL to navigate to after launch. If omitted, opens a blank page.
        headless: Run browser in headless mode. Default: false (headed, for observation).
        proxy: Optional proxy URL (e.g., 'http://user:pass@host:port').
               WARNING: Using a proxy triggers botasaurus-driver's proxy authentication
               subsystem, which imports javascript-fixes — a package that runs
               'npm install' at import time without a lockfile. Only use proxy in
               trusted environments where Node.js is installed.
        download_dir: Directory for downloaded files. Default: './downloads'.
        connection_mode: How to connect to Chrome. 'launch' (default) starts a new
                         browser instance. 'extension' connects to your existing
                         Chrome via the Scout extension, preserving logged-in sessions.
        allowed_domains: Optional list of domains allowed for fill_secret credential
                         typing and cross-origin navigation (extension mode).
                         Example: ['example.com', 'login.example.com'].
                         If omitted, fill_secret works on any domain (with a warning).
    """
    app_ctx = _get_ctx(ctx)

    # Validate connection_mode
    try:
        mode = ConnectionMode(connection_mode)
    except ValueError:
        return {"error": f"Invalid connection_mode: '{connection_mode}'. Use 'launch' or 'extension'."}

    async with app_ctx._launch_lock:
        if len(app_ctx.sessions) >= app_ctx.max_sessions:
            active_ids = list(app_ctx.sessions.keys())
            return {
                "error": f"Maximum sessions ({app_ctx.max_sessions}) reached. "
                f"Close session '{active_ids[0]}' first.",
                "active_sessions": active_ids,
            }

        session = BrowserSession(
            headless=headless,
            proxy=proxy,
            download_dir=download_dir,
            connection_mode=mode,
            allowed_domains=allowed_domains,
        )

        if mode == ConnectionMode.EXTENSION:
            from .extension_relay import ExtensionRelay

            # Start the WebSocket relay server if not already running
            if app_ctx._extension_relay is None:
                relay = ExtensionRelay()
                await relay.start()
                app_ctx._extension_relay = relay
            else:
                relay = app_ctx._extension_relay

            session.set_extension_relay(relay)
            relay._security_counter = session.security_counter

            # Initialize navigation guard for extension mode
            if url:
                from .security.navigation_guard import NavigationGuard
                session._navigation_guard = NavigationGuard(
                    origin_url=url,
                    allowed_domains=allowed_domains,
                    session_id=session.session_id,
                    security_counter=session.security_counter,
                )

            await ctx.info(
                f"Waiting for Scout extension to connect on ws://localhost:9222/scout-extension..."
            )
        else:
            await ctx.info(f"Launching browser session {session.session_id}...")

        info: SessionInfo = await asyncio.to_thread(session.launch, url)
        app_ctx.sessions[session.session_id] = session

    await ctx.info(f"Session {session.session_id} active at {info.current_url}")

    return info.model_dump(exclude_none=True)


# --- Tool: check_extension ---


@mcp.tool()
async def check_extension(
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """Check the status of the Scout Chrome extension connection.

    Returns the extension connection status: whether the relay server is running,
    whether the extension is connected, and installation instructions if needed.
    """
    app_ctx = _get_ctx(ctx)
    relay = app_ctx._extension_relay

    if relay is None:
        return ExtensionStatus(
            status="not_running",
            message="Extension relay server is not running. "
                    "Use launch_session with connection_mode='extension' to start it.",
            install_instructions=(
                "1. Open chrome://extensions in Chrome\n"
                "2. Enable 'Developer mode' (top right toggle)\n"
                "3. Click 'Load unpacked' and select the extension/ directory from the Scout repo\n"
                "4. Click the Scout MCP Bridge icon in the toolbar and toggle Active\n"
                "5. Use launch_session(connection_mode='extension') to connect"
            ),
        ).model_dump(exclude_none=True)

    if relay.is_connected:
        return ExtensionStatus(
            status="connected",
            message=f"Extension connected. Tab URL: {relay.tab_url}",
        ).model_dump(exclude_none=True)

    return ExtensionStatus(
        status="waiting",
        message="Relay server running but extension not connected. "
                "Open Chrome and activate the Scout MCP Bridge extension.",
    ).model_dump(exclude_none=True)


# --- Tool: scout_page ---


@mcp.tool()
async def scout_page_tool(
    session_id: str,
    focus_frame: str | None = None,
    detail_level: Literal["summary", "full"] = "summary",
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """Perform deep reconnaissance on the current page state.

    Returns a structural overview of the page: metadata, iframe hierarchy,
    shadow DOM boundaries, and element counts. Use find_elements to search
    for specific interactive elements by text, type, or selector.

    Args:
        session_id: Active session ID from launch_session.
        focus_frame: Optional iframe CSS selector to scout instead of the full page.
        detail_level: 'summary' (default) returns compact overview with element counts.
                      'full' returns all interactive elements (large response).
    """
    app_ctx = _get_ctx(ctx)
    session = _get_session(app_ctx, session_id)

    await ctx.info("Scouting page...")
    report: ScoutReport = await asyncio.to_thread(
        scout_page, session.driver, focus_frame
    )

    # Cache elements for find_elements queries
    session.cache_elements(report.interactive_elements)

    # Record in history (always stores summary-level)
    session.history.record_scout(report)

    await ctx.info(f"Scout complete: {report.page_summary}")

    page_url = report.page_metadata.url

    if detail_level == "full":
        data = report.model_dump(exclude_none=True)
        response = sanitize_response(data, secrets=session._secret_values)
        return scan_and_warn(response, data, page_url, session.session_id, session.security_counter)

    # Summary mode: return structure + counts, no element list
    element_summary = build_element_summary(report.interactive_elements)
    data = {
        "page_metadata": report.page_metadata.model_dump(exclude_none=True),
        "iframe_map": [f.model_dump(exclude_none=True) for f in report.iframe_map],
        "shadow_dom_boundaries": [s.model_dump(exclude_none=True) for s in report.shadow_dom_boundaries],
        "element_summary": element_summary.model_dump(exclude_none=True),
        "page_summary": report.page_summary,
    }
    response = sanitize_response(data, secrets=session._secret_values)
    return scan_and_warn(response, data, page_url, session.session_id, session.security_counter)


# --- Tool: find_elements ---


@mcp.tool()
async def find_elements(
    session_id: str,
    query: str | None = None,
    element_types: list[str] | None = None,
    visible_only: bool = True,
    frame_context: str | None = None,
    max_results: int = 25,
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """Search for specific interactive elements on the current page.

    Returns matching elements with selectors, text, and attributes.
    Call scout_page_tool first to cache the page structure, then use this
    tool to find specific elements by text, type, or CSS selector.

    Args:
        session_id: Active session ID.
        query: Text or selector to search for (case-insensitive substring match).
               Matches against element text, selector, id, name, aria-label, placeholder, href.
        element_types: Filter by tag name, e.g. ['button', 'input', 'a'].
        visible_only: Only return visible elements. Default: true.
        frame_context: Limit search to a specific iframe (use selector from scout report).
        max_results: Maximum elements to return. Default: 25.
    """
    max_results = min(max(max_results, 1), MAX_RESULTS)
    app_ctx = _get_ctx(ctx)
    session = _get_session(app_ctx, session_id)

    # Use cached elements or re-scout if cache is empty
    elements = session.get_cached_elements()
    if elements is None:
        await ctx.info("No cached elements — scouting page first...")
        report: ScoutReport = await asyncio.to_thread(
            scout_page, session.driver, None
        )
        elements = report.interactive_elements
        session.cache_elements(elements)
        session.history.record_scout(report)

    matched = filter_elements(
        elements,
        query=query,
        element_types=element_types,
        visible_only=visible_only,
        frame_context=frame_context,
        max_results=max_results,
    )

    # Record in history
    session.history.record_find_elements(query, element_types, len(matched))

    # Strip default/empty fields from each element for compact output
    stripped = []
    for el in matched:
        d = el.model_dump(exclude_none=True)
        # Strip true booleans that are default
        if d.get("visible") is True:
            del d["visible"]
        if d.get("enabled") is True:
            del d["enabled"]
        if d.get("in_shadow_dom") is False:
            del d["in_shadow_dom"]
        # Strip empty text
        if not d.get("text"):
            d.pop("text", None)
        # Strip empty attributes dict
        if not d.get("attributes"):
            d.pop("attributes", None)
        # Strip default frame_context
        if d.get("frame_context") == "main":
            del d["frame_context"]
        stripped.append(d)

    await ctx.info(f"Found {len(matched)} element(s) matching query")

    data = {
        "matched": len(matched),
        "total_on_page": len(elements),
        "elements": stripped,
    }
    page_url = ""
    try:
        page_url = await asyncio.to_thread(lambda: session.driver.current_url)
    except Exception:
        pass
    response = sanitize_response(data, secrets=session._secret_values)
    return scan_and_warn(response, data, page_url, session.session_id, session.security_counter)


# --- Tool: execute_action ---


@mcp.tool()
async def execute_action_tool(
    session_id: str,
    action: Literal["click", "type", "select", "navigate", "scroll", "wait", "press_key", "hover", "clear", "upload_file"],
    selector: str | None = None,
    value: str | None = None,
    frame_context: str | None = None,
    wait_after: int = 500,
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """Perform a single interaction in the live browser session.

    Supports clicking, typing, selecting, navigating, scrolling, and waiting.
    Always scout after executing an action to observe the result.

    Args:
        session_id: Active session ID.
        action: The action to perform.
        selector: CSS selector of the target element. Required for click, type, select, hover, clear, upload_file.
        value: Text to type, option to select, URL to navigate to, key to press, wait duration, or file path to upload.
        frame_context: Iframe selector path for the target element. Use 'main' or omit for top-level.
        wait_after: Milliseconds to wait after action completes. Default: 500.
    """
    wait_after = min(max(wait_after, 0), MAX_WAIT_MS)
    app_ctx = _get_ctx(ctx)
    session = _get_session(app_ctx, session_id)

    await ctx.info(f"Executing {action}...")
    result, record = await asyncio.to_thread(
        execute_action,
        session.driver,
        action,
        selector,
        value,
        frame_context,
        wait_after,
    )

    # Record in history
    session.history.record_action(record)
    if result.url_changed:
        session.history.record_navigation(result.current_url)

    # Invalidate element cache (DOM may have changed)
    session.invalidate_element_cache()

    if result.success:
        await ctx.info(f"Action complete: {result.action_performed}")
    else:
        await ctx.warning(f"Action failed: {result.error}")

    return sanitize_response(result.model_dump(exclude_none=True), secrets=session._secret_values)


# --- Tool: fill_secret ---


@mcp.tool()
async def fill_secret(
    session_id: str,
    env_var: str,
    selector: str,
    frame_context: str | None = None,
    clear_first: bool = True,
    wait_after: int = 500,
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """Type a secret value from .env into a form field without exposing it in the conversation.

    The server reads the value from the .env file and types it directly into the
    target element. The actual value never appears in tool parameters or responses.

    Args:
        session_id: Active session ID.
        env_var: Name of the environment variable in .env (e.g., 'APP_PASSWORD').
        selector: CSS selector of the target input field.
        frame_context: Iframe selector path for the target element. Use 'main' or omit for top-level.
        clear_first: Clear the field before typing. Default: true.
        wait_after: Milliseconds to wait after typing. Default: 500.
    """
    import time
    from datetime import datetime, timezone

    from .actions import _resolve_target

    wait_after = min(max(wait_after, 0), MAX_WAIT_MS)
    app_ctx = _get_ctx(ctx)
    session = _get_session(app_ctx, session_id)

    start = time.perf_counter()
    timestamp = datetime.now(timezone.utc).isoformat()

    # --- Security: domain scoping ---
    domain_warning: str | None = None
    try:
        current_url = await asyncio.to_thread(lambda: session.driver.current_url)
    except Exception:
        current_url = ""

    if session._allowed_domains is not None:
        current_domain = extract_registered_domain(current_url)
        allowed_set = {d.lower() for d in session._allowed_domains}
        if current_domain.lower() not in allowed_set:
            error_msg = (
                f"fill_secret refused: current domain '{current_domain}' is not in the "
                f"session's allowed_domains list. Allowed: {session._allowed_domains}. "
                f"Use launch_session with allowed_domains to authorize additional domains."
            )
            log_security_event(
                session_id=session.session_id,
                event_type="credential_refused",
                severity="critical",
                url=current_url,
                detail={
                    "env_var": env_var,
                    "current_domain": current_domain,
                    "allowed_domains": session._allowed_domains,
                },
            )
            session.security_counter.increment("credential_refused")
            return FillSecretResult(
                success=False, env_var=env_var, selector=selector,
                error=error_msg,
            ).model_dump(exclude_none=True)
    else:
        domain_warning = (
            "[SECURITY] No domain scope set for this session. Consider using "
            "allowed_domains in launch_session to restrict credential usage."
        )

    # Load the secret value server-side from .env
    scrub_warning: str | None = None
    try:
        env_vars = _get_env_vars(app_ctx)
        if env_var not in env_vars:
            raise KeyError(env_var)
        secret_value = env_vars[env_var]
        scrub_warning = session.register_secret(secret_value)
    except KeyError:
        return FillSecretResult(
            success=False, env_var=env_var, selector=selector,
            error=f"Variable '{env_var}' not found in .env file.",
        ).model_dump(exclude_none=True)
    except Exception as e:
        return FillSecretResult(
            success=False, env_var=env_var, selector=selector,
            error=str(e),
        ).model_dump(exclude_none=True)

    # Get URL before action
    try:
        url_before = await asyncio.to_thread(lambda: session.driver.current_url)
    except Exception:
        url_before = ""

    # Type the value into the field
    error = None
    try:
        target = await asyncio.to_thread(_resolve_target, session.driver, frame_context)
        if clear_first:
            await asyncio.to_thread(target.clear, selector)
        await asyncio.to_thread(target.type, selector, secret_value)
    except Exception as e:
        error = str(e)

    if wait_after > 0:
        await asyncio.sleep(wait_after / 1000)

    # Get URL after action
    try:
        url_after = await asyncio.to_thread(lambda: session.driver.current_url)
    except Exception:
        url_after = url_before

    elapsed = int((time.perf_counter() - start) * 1000)

    # Record in history with reference, NOT the actual value
    record = ActionRecord(
        action="type",
        selector=selector,
        value=f"${{{env_var}}}",
        frame_context=frame_context,
        success=error is None,
        url_before=url_before,
        url_after=url_after,
        timestamp=timestamp,
        error=error,
    )
    session.history.record_action(record)
    if url_before != url_after:
        session.history.record_navigation(url_after)
    session.invalidate_element_cache()

    # Combine warnings
    combined_warning = scrub_warning
    if domain_warning:
        combined_warning = f"{domain_warning}\n{scrub_warning}" if scrub_warning else domain_warning

    result = FillSecretResult(
        success=error is None,
        env_var=env_var,
        selector=selector,
        chars_typed=len(secret_value) if error is None else 0,
        url_changed=url_before != url_after,
        current_url=url_after,
        error=error,
        warning=combined_warning,
        elapsed_ms=elapsed,
    )

    if result.success:
        await ctx.info(f"Secret '{env_var}' typed into '{selector}' ({result.chars_typed} chars)")
    else:
        await ctx.warning(f"fill_secret failed: {error}")

    return sanitize_response(result.model_dump(exclude_none=True), secrets=session._secret_values)


# --- Tool: execute_javascript ---


@mcp.tool()
async def execute_javascript(
    session_id: str,
    script: str,
    frame_context: str | None = None,
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """Execute arbitrary JavaScript in the page context and return the result.

    Use this to debug click failures, read shadow DOM content, dispatch custom
    events, extract data, or perform any DOM operation not covered by other tools.

    Args:
        session_id: Active session ID.
        script: JavaScript code to execute. The last expression is returned as the result.
               Scripts with explicit 'return' statements also work for backward compatibility.
        frame_context: Iframe selector path for execution context. Use 'main' or omit for top-level.
    """
    app_ctx = _get_ctx(ctx)
    session = _get_session(app_ctx, session_id)

    await ctx.info("Executing JavaScript...")
    try:
        result, record = await asyncio.wait_for(
            asyncio.to_thread(run_javascript, session.driver, script, frame_context),
            timeout=MAX_JS_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        # The thread may continue running — asyncio cannot kill threads.
        # But we unblock the server and return an error to the client.
        await ctx.warning(f"JS execution timed out after {MAX_JS_TIMEOUT_S}s")
        return sanitize_response({
            "success": False,
            "error": f"Execution timed out after {MAX_JS_TIMEOUT_S}s. "
                     "The script may still be running in the browser.",
            "elapsed_ms": MAX_JS_TIMEOUT_S * 1000,
        }, secrets=session._secret_values)

    session.history.record_javascript(record)

    # JS can modify the DOM arbitrarily, so invalidate cached elements
    session.invalidate_element_cache()

    if result.success:
        await ctx.info(f"JS executed: {result.result_type} result")
    else:
        await ctx.warning(f"JS execution failed: {result.error}")

    # --- Security: scope disclosure ---
    current_url = ""
    try:
        current_url = await asyncio.to_thread(lambda: session.driver.current_url)
    except Exception:
        pass
    from urllib.parse import urlparse
    parsed = urlparse(current_url)
    origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else current_url

    scope_block = (
        "\n[JS EXECUTION SCOPE]\n"
        f"Ran in page context of: {current_url}\n"
        "localStorage accessible: yes\n"
        "sessionStorage accessible: yes\n"
        "HttpOnly cookies: not accessible\n"
        "Cross-origin iframes: not accessible\n"
        f"Network requests: permitted to {origin} and any CORS-permitted origins\n"
        "[END SCOPE]\n"
    )

    response = sanitize_response(result.model_dump(exclude_none=True), secrets=session._secret_values)
    return scope_block + response


# --- Tool: take_screenshot ---


@mcp.tool()
async def take_screenshot_tool(
    session_id: str,
    format: Literal["png", "jpeg"] = "png",
    quality: int | None = None,
    clip_x: float | None = None,
    clip_y: float | None = None,
    clip_width: float | None = None,
    clip_height: float | None = None,
    full_page: bool = False,
    return_image: bool = True,
    ctx: Context[ServerSession, AppContext] = None,
) -> CallToolResult:
    """Capture a screenshot of the current page. The screenshot is always saved to disk.

    By default, also returns the image inline so Claude can see it (~1,600 tokens
    at typical browser resolution). Set return_image=false when capturing screenshots
    as file artifacts that don't need visual analysis — the file_path in the JSON
    response is sufficient to reference or copy the file.

    Args:
        session_id: Active session ID.
        format: Image format: 'png' or 'jpeg'. Default: 'png'.
        quality: JPEG quality (1-100). Only used when format='jpeg'.
        clip_x: Left coordinate of clip region (viewport pixels).
        clip_y: Top coordinate of clip region (viewport pixels).
        clip_width: Width of clip region.
        clip_height: Height of clip region.
        full_page: Capture the full scrollable page, not just viewport. Default: false.
                   Note: pages with lazy-loaded content may still show incomplete results.
        return_image: Return image inline for visual inspection. Default: true.
                      Set to false when collecting screenshots as file artifacts
                      to save ~1,600 tokens per screenshot.
    """
    app_ctx = _get_ctx(ctx)
    session = _get_session(app_ctx, session_id)

    await ctx.info("Taking screenshot...")
    result, record, raw_bytes = await asyncio.to_thread(
        take_screenshot,
        session.driver,
        image_format=format,
        quality=quality,
        clip_x=clip_x,
        clip_y=clip_y,
        clip_width=clip_width,
        clip_height=clip_height,
        full_page=full_page,
    )

    session.history.record_screenshot(record)

    if not result.success or raw_bytes is None:
        await ctx.warning(f"Screenshot failed: {result.error}")
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(result.model_dump(exclude_none=True)))],
            isError=True,
        )

    await ctx.info(f"Screenshot captured: {result.byte_size} bytes ({format})")

    # Save screenshot to base download_dir (not session subdir).
    # Downloads use per-session subdirs because DownloadManager tracks transfer state.
    # Screenshots are fire-and-forget artifacts — the user wants them in one flat
    # directory for easy discovery. Auto-increment handles filename collisions.
    # See tests/test_screenshot_save.py for unit tests of this algorithm.
    from datetime import datetime

    ext = "jpg" if format == "jpeg" else format
    timestamp_str = datetime.now().strftime("%H%M%S")
    base = f"screenshot_{timestamp_str}"
    save_path = os.path.join(session.download_dir, f"{base}.{ext}")
    counter = 1
    while os.path.exists(save_path):
        save_path = os.path.join(session.download_dir, f"{base}_{counter}.{ext}")
        counter += 1
    try:
        os.makedirs(session.download_dir, exist_ok=True)
        with open(save_path, "wb") as f:
            f.write(raw_bytes)
        result.file_path = save_path
        await ctx.info(f"Screenshot saved to: {save_path}")
    except Exception as e:
        await ctx.warning(f"Failed to save screenshot to disk: {e}")

    # Return metadata as text; optionally include image inline for visual display
    content = [TextContent(type="text", text=json.dumps(result.model_dump(exclude_none=True)))]
    if return_image:
        mime = f"image/{format}"
        content.append(ImageContent(type="image", data=base64.b64encode(raw_bytes).decode(), mimeType=mime))
    return CallToolResult(content=content)


# --- Tool: inspect_element ---


@mcp.tool()
async def inspect_element_tool(
    session_id: str,
    selector: str,
    frame_context: str | None = None,
    include_listeners: bool = False,
    include_children: bool = True,
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """Inspect a single DOM element in detail — visibility, position, shadow DOM, overlays, and more.

    Use this to diagnose why a click didn't work, check if an element is obscured by
    an overlay, verify shadow DOM context, or examine element state before interacting.

    Args:
        session_id: Active session ID.
        selector: CSS selector of the element to inspect.
        frame_context: Iframe selector path. Use 'main' or omit for top-level.
        include_listeners: Detect inline event handlers (onclick, etc.). Default: false.
        include_children: Include child element summary. Default: true.
    """
    app_ctx = _get_ctx(ctx)
    session = _get_session(app_ctx, session_id)

    await ctx.info(f"Inspecting element: {selector}")
    inspection = await asyncio.to_thread(
        inspect_element,
        session.driver,
        selector,
        frame_context,
        include_listeners,
        include_children,
    )

    if inspection.found:
        status = "visible" if inspection.is_visible else "hidden"
        if inspection.is_obscured:
            status += f", obscured by {inspection.obscured_by}"
        await ctx.info(f"Element found: <{inspection.tag}> ({status})")
    else:
        await ctx.warning(f"Element not found: {selector}")

    data = inspection.model_dump(exclude_none=True)
    page_url = ""
    try:
        page_url = await asyncio.to_thread(lambda: session.driver.current_url)
    except Exception:
        pass
    response = sanitize_response(data, secrets=session._secret_values)
    return scan_and_warn(response, data, page_url, session.session_id, session.security_counter)


# --- Tool: process_download ---


@mcp.tool()
async def process_download(
    session_id: str,
    source_format: str = "auto",
    target_format: str = "csv",
    target_filename: str | None = None,
    target_directory: str | None = None,
    guid: str | None = None,
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """Process a downloaded file: convert format, rename, and move to destination.

    Call this after a download completes.
    Handles format conversion (e.g., SpreadsheetML 2003 XML to CSV), filename
    pattern application, and file delivery to a target directory.

    Args:
        session_id: Active session ID.
        source_format: Source file format. Use "auto" to detect from file contents.
                       Known formats: spreadsheetml_2003, xls_binary, xlsx, csv.
        target_format: Target format to convert to (e.g., "csv"). Default: "csv".
        target_filename: Filename pattern with tokens: {MM}, {dd}, {yyyy}, {HH}, {mm}, {suggested}.
                         Example: "Complete Enrollments Report {MM}.{dd}.{yyyy}.csv"
        target_directory: Destination directory. UNC paths supported (e.g., \\\\server\\share\\path).
        guid: Specific download GUID to process. If omitted, processes the most recent completed download.
    """
    app_ctx = _get_ctx(ctx)
    session = _get_session(app_ctx, session_id)

    await ctx.info("Processing download...")
    result = await asyncio.to_thread(
        session.download_manager.process_download,
        guid=guid,
        source_format=source_format,
        target_format=target_format,
        target_filename=target_filename,
        target_directory=target_directory,
    )

    if result.success:
        await ctx.info(f"Download processed: {result.final_path}")
    else:
        await ctx.warning(f"Processing failed: {result.error}")

    return sanitize_response(result.model_dump(exclude_none=True), secrets=session._secret_values)


# --- Tool: get_session_history ---


@mcp.tool()
async def get_session_history(
    session_id: str,
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """Return the complete structured history of a browser session.

    Includes every action taken, every scout report (summarized), every network event
    captured, and the sequence of URLs visited. Use this data to compose botasaurus-driver scripts.

    Args:
        session_id: Active session ID.
    """
    app_ctx = _get_ctx(ctx)
    session = _get_session(app_ctx, session_id)

    history: SessionHistory = session.history.get_full_history()
    await ctx.info(
        f"Session history: {len(history.actions)} actions, "
        f"{len(history.scouts)} scouts, {len(history.network_events)} network events"
    )
    data = history.model_dump(exclude_none=True)
    data["security_summary"] = session.security_counter.summary()
    return sanitize_response(data, secrets=session._secret_values)


# --- Tool: monitor_network ---


@mcp.tool()
async def monitor_network(
    session_id: str,
    command: Literal["start", "stop", "query", "wait_for_download"],
    url_pattern: str | None = None,
    timeout_ms: int = 30000,
    capture_response_body: bool = False,
    limit: int = 100,
    offset: int = 0,
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """Control network monitoring for the current session.

    Start monitoring before performing actions that trigger API calls or downloads,
    then query to see what was captured.

    Args:
        session_id: Active session ID.
        command: start: begin capturing. stop: stop. query: return captured events. wait_for_download: block until download.
        url_pattern: Optional regex pattern to filter captured requests by URL.
        timeout_ms: For wait_for_download: maximum wait time. Default: 30000.
        capture_response_body: Whether to capture response bodies (adds overhead). Default: false.
        limit: Maximum number of events to return in a query response. Default: 100.
        offset: Number of matching events to skip before returning results. Default: 0.
    """
    timeout_ms = min(max(timeout_ms, 0), MAX_TIMEOUT_MS)
    app_ctx = _get_ctx(ctx)
    session = _get_session(app_ctx, session_id)
    monitor = session.network_monitor

    match command:
        case "start":
            await ctx.info("Starting network monitoring...")
            await asyncio.to_thread(
                monitor.start, session.driver, url_pattern, capture_response_body
            )
            return MonitorResult(
                monitoring_active=True,
                total_captured=len(monitor.events),
            ).model_dump(exclude_none=True)

        case "stop":
            monitor.stop()
            await ctx.info("Network monitoring stopped.")
            return MonitorResult(
                monitoring_active=False,
                total_captured=len(monitor.events),
            ).model_dump(exclude_none=True)

        case "query":
            # Record new events in session history using a monotonic cursor
            # (len() would break after FIFO eviction plateaus at MAX_NETWORK_EVENTS)
            all_events = await asyncio.to_thread(monitor.query_all)
            cursor = session.history._network_sync_cursor
            for event in all_events[cursor:]:
                session.history.record_network_event(event)
            session.history._network_sync_cursor = len(all_events)
            # Get matching events with pagination for the tool response
            all_matching = await asyncio.to_thread(monitor.query_all, url_pattern)
            total_matched = len(all_matching)
            paginated = all_matching[offset:] if offset > 0 else all_matching
            events = paginated[:limit] if limit > 0 else paginated

            # --- Security: POST body scrubbing ---
            env_keys: set[str] | None = None
            env_values: dict[str, str] | None = None
            try:
                env_data = _get_env_vars(app_ctx)
                env_keys = set(env_data.keys())
                env_values = env_data
            except Exception:
                pass

            monitor_data = MonitorResult(
                events=events,
                total_captured=monitor.total_count,
                total_matched=total_matched,
                monitoring_active=monitor.monitoring,
            ).model_dump(exclude_none=True)

            # Scrub POST bodies in the events
            if monitor_data.get("events"):
                scrubbed_events, scrubbed_count = scrub_network_events(
                    monitor_data["events"],
                    env_keys=env_keys,
                    env_values=env_values,
                    session_id=session.session_id,
                    security_counter=session.security_counter,
                )
                monitor_data["events"] = scrubbed_events
                if scrubbed_count > 0:
                    monitor_data["scrubbed_fields"] = scrubbed_count

            return sanitize_response(monitor_data, secrets=session._secret_values)

        case "wait_for_download":
            await ctx.info(f"Waiting for download (timeout: {timeout_ms}ms)...")
            download_event = await asyncio.to_thread(
                session.download_manager.wait_for_download, timeout_ms
            )
            if download_event:
                return sanitize_response(
                    download_event.model_dump(exclude_none=True),
                    secrets=session._secret_values,
                )
            # Fallback to network monitor's header-based detection
            download_events = await asyncio.to_thread(monitor.wait_for_download, timeout_ms)
            return sanitize_response(MonitorResult(
                events=download_events,
                total_captured=len(monitor.events),
                monitoring_active=monitor.monitoring,
            ).model_dump(exclude_none=True), secrets=session._secret_values)

        case _:
            return {"error": f"Unknown command: {command}"}


# --- Tool: record_video ---


@mcp.tool()
async def record_video(
    session_id: str,
    command: Literal["start", "stop", "status"],
    max_width: int = 1920,
    max_height: int = 1080,
    quality: int = 95,
    target_fps: int = 15,
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """Control video recording for the current browser session.

    Records the browser screen using CDP screencast and encodes to MP4.
    Requires ffmpeg for video encoding: install imageio-ffmpeg (pip install 'imageio-ffmpeg')
    or have ffmpeg on your system PATH. Without it, raw JPEG frames are saved instead.

    Args:
        session_id: Active session ID.
        command: start: begin recording. stop: stop and encode video. status: check recording state.
        max_width: Maximum video width in pixels. Default: 1920.
        max_height: Maximum video height in pixels. Default: 1080.
        quality: JPEG frame quality (1-100). Default: 95.
        target_fps: Target frames per second (approximate). Default: 15.
    """
    max_width = min(max(max_width, 320), 1920)
    max_height = min(max(max_height, 240), 1080)
    quality = min(max(quality, 1), 100)
    target_fps = min(max(target_fps, 1), 30)

    app_ctx = _get_ctx(ctx)
    session = _get_session(app_ctx, session_id)
    monitor = session.screencast_monitor

    match command:
        case "start":
            await ctx.info(f"Starting video recording ({max_width}x{max_height} @ {target_fps}fps)...")
            await asyncio.to_thread(
                monitor.start, session.driver, max_width, max_height, quality, target_fps
            )
            return RecordingResult(
                recording_active=True,
                started_at=monitor._started_at,
                target_fps=target_fps,
                resolution=f"{max_width}x{max_height}",
            ).model_dump(exclude_none=True)

        case "stop":
            await ctx.info("Stopping recording and encoding video...")
            result = await asyncio.to_thread(monitor.stop)

            # Record in session history
            from datetime import datetime, timezone
            record = RecordingRecord(
                started_at=monitor._started_at or "",
                stopped_at=monitor._stopped_at or "",
                duration_seconds=result["duration_seconds"],
                frame_count=result["frame_count"],
                video_path=result.get("video_path"),
                encoded=result["encoded"],
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            session.history.record_recording(record)

            recording_result = RecordingResult(
                recording_active=False,
                video_path=result.get("video_path"),
                frames_dir=result.get("frames_dir"),
                frame_count=result["frame_count"],
                duration_seconds=result["duration_seconds"],
                encoded=result["encoded"],
                encode_warning=result.get("encode_warning"),
            )

            if result["encoded"]:
                await ctx.info(
                    f"Video saved: {result['video_path']} "
                    f"({result['frame_count']} frames, {result['duration_seconds']}s)"
                )
            else:
                warning = result.get("encode_warning") or result.get("error") or "Encoding unavailable"
                await ctx.warning(warning)

            return recording_result.model_dump(exclude_none=True)

        case "status":
            status = monitor.status()
            return RecordingResult(
                recording_active=status["recording"],
                frame_count=status["frame_count"],
                started_at=status["started_at"],
                elapsed_seconds=status["elapsed_seconds"],
                target_fps=status["target_fps"],
                resolution=status["resolution"],
            ).model_dump(exclude_none=True)

        case _:
            return {"error": f"Unknown command: {command}"}


# --- Tool: close_session ---


@mcp.tool()
async def close_session(
    session_id: str,
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """Close the browser session and release all resources.

    Always call this when automation exploration is complete.

    Args:
        session_id: Session ID to close.
    """
    app_ctx = _get_ctx(ctx)
    session = _get_session(app_ctx, session_id)

    await ctx.info(f"Closing session {session_id}...")
    result: SessionCloseResult = await asyncio.to_thread(session.close)
    del app_ctx.sessions[session_id]

    await ctx.info(
        f"Session closed. Duration: {result.session_duration_seconds}s, "
        f"Actions: {result.total_actions_performed}, Scouts: {result.total_scouts_performed}"
    )
    return result.model_dump(exclude_none=True)


# --- Tool: get_2fa_code ---


@mcp.tool()
async def get_2fa_code(
    app_keyword: str,
    code_pattern: str = r"\d{6}",
    timeout: int = 60,
    ctx: Context[ServerSession, AppContext] = None,
) -> str:
    """Fetch a 2FA OTP code from Twilio SMS — call this AFTER clicking 'Send Code'.

    Polls the Twilio Messages API until a new SMS matching app_keyword arrives,
    then extracts and returns the OTP code. Twilio credentials are read from
    .env and never exposed in tool responses.

    Call this tool AFTER triggering the 2FA send in the browser. The baseline
    inbox state is captured at call time; Twilio delivery latency (2-10s) gives
    sufficient buffer before the first poll.

    Args:
        app_keyword: Case-insensitive keyword to match in the SMS body.
                     Use the site name, e.g. 'paycom', 'chase', 'google'.
        code_pattern: Regex to extract the OTP. Default: 6-digit number.
                      Override for 8-digit or alphanumeric codes.
        timeout: Seconds to wait for the code before giving up. Default: 60.

    Required .env entries:
        TWILIO_ACCOUNT_SID  — Twilio Account SID
        TWILIO_AUTH_TOKEN   — Twilio Auth Token
        TWILIO_PHONE_NUMBER — Digits-only recipient number (e.g. 14155551234)
    """
    app_ctx = _get_ctx(ctx)

    try:
        env_vars = _get_env_vars(app_ctx)
        account_sid = env_vars["TWILIO_ACCOUNT_SID"]
        auth_token = env_vars["TWILIO_AUTH_TOKEN"]
        phone_number = env_vars["TWILIO_PHONE_NUMBER"]
    except KeyError as exc:
        raise ValueError(
            f"Missing Twilio credential: {exc}. "
            "Add TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER to your .env file."
        ) from exc

    return await poll_for_otp(
        account_sid=account_sid,
        auth_token=auth_token,
        phone_number=phone_number,
        app_keyword=app_keyword,
        code_pattern=code_pattern,
        timeout=float(timeout),
    )


# --- Scheduling Tools ---

from .scheduler import UnsupportedPlatformError, get_scheduler

_VALID_SCHEDULES = {"DAILY", "WEEKLY", "ONCE"}


@mcp.tool()
async def schedule_create(
    name: str,
    workflow_dir: str,
    schedule: str,
    time: str,
    days: str | None = None,
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """Create or update a scheduled task for an exported SCOUT workflow.

    Generates a platform-appropriate run script and registers the schedule with the
    OS task scheduler (Windows Task Scheduler, macOS launchd, or Linux cron).

    Args:
        name: Workflow name. Must match <name>.py inside workflow_dir.
        workflow_dir: Absolute path to the workflow directory (e.g., 'D:/Projects/app/workflows/enrollment').
        schedule: Frequency — one of DAILY, WEEKLY, ONCE.
        time: Time to run in HH:MM 24-hour format (e.g., '06:45', '14:00').
        days: Comma-separated day names for WEEKLY schedules (e.g., 'MON,WED,FRI').
              Required when schedule is WEEKLY.
    """
    from pathlib import Path

    # Validate name format (prevent path traversal in task scheduler namespaces)
    if not _SCHEDULE_NAME_RE.match(name):
        return {
            "error": "Invalid task name. Use only letters, numbers, hyphens, and underscores (1-64 chars, must start with alphanumeric)."
        }

    # Validate schedule parameter
    schedule_upper = schedule.upper()
    if schedule_upper not in _VALID_SCHEDULES:
        return {
            "error": f"Invalid schedule '{schedule}'. Must be one of: {', '.join(sorted(_VALID_SCHEDULES))}."
        }

    try:
        scheduler = get_scheduler()
    except UnsupportedPlatformError as e:
        return {"error": str(e)}

    # Verify workflow exists (using absolute path from caller)
    workflow_path = Path(workflow_dir)
    workflow_script = workflow_path / f"{name}.py"
    if not workflow_script.exists():
        return {
            "error": f"No exported workflow found at '{workflow_script}'. "
            f"Run /export {name} first to generate the script."
        }

    await ctx.info(f"Creating schedule for '{name}' on {scheduler.platform_name}...")

    # Generate platform-appropriate run script
    run_script = await asyncio.to_thread(
        scheduler.generate_run_script, str(workflow_path.resolve()), f"{name}.py"
    )

    # Create the scheduled task
    success = await asyncio.to_thread(
        scheduler.create, name, str(run_script), schedule_upper, time, days
    )

    if not success:
        return {"error": f"Failed to create schedule on {scheduler.platform_name}."}

    # Verify by querying
    info = await asyncio.to_thread(scheduler.query, name)
    if info:
        await ctx.info(f"Scheduled '{name}' ({schedule_upper} at {time}) on {scheduler.platform_name}")
        return {
            "success": True,
            "platform": scheduler.platform_name,
            "schedule": info.model_dump(),
        }

    return {"success": True, "platform": scheduler.platform_name}


@mcp.tool()
async def schedule_list(
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """List all SCOUT scheduled tasks on this machine.

    Returns all tasks registered with the OS task scheduler (Windows Task Scheduler,
    macOS launchd, or Linux cron) under the SCOUT namespace.
    """
    try:
        scheduler = get_scheduler()
    except UnsupportedPlatformError as e:
        return {"error": str(e)}

    await ctx.info(f"Listing schedules on {scheduler.platform_name}...")
    tasks = await asyncio.to_thread(scheduler.list_all)

    await ctx.info(f"Found {len(tasks)} scheduled task(s)")
    return {
        "platform": scheduler.platform_name,
        "count": len(tasks),
        "tasks": [t.model_dump() for t in tasks],
    }


@mcp.tool()
async def schedule_delete(
    name: str,
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """Delete a scheduled task from the OS task scheduler.

    Removes the task from Windows Task Scheduler, macOS launchd, or Linux cron.
    Does not delete the workflow files — only the schedule.

    Args:
        name: Name of the scheduled task to delete.
    """
    if not _SCHEDULE_NAME_RE.match(name):
        return {"error": "Invalid task name format."}

    try:
        scheduler = get_scheduler()
    except UnsupportedPlatformError as e:
        return {"error": str(e)}

    await ctx.info(f"Deleting schedule '{name}' on {scheduler.platform_name}...")
    success = await asyncio.to_thread(scheduler.delete, name)

    if success:
        await ctx.info(f"Schedule '{name}' deleted")
        return {"success": True, "platform": scheduler.platform_name}
    else:
        return {
            "error": f"Failed to delete '{name}'. It may not exist.",
            "platform": scheduler.platform_name,
        }


# --- Tool: get_security_log ---


@mcp.tool()
async def get_security_log(
    session_id: str | None = None,
    severity: str | None = None,
    limit: int = 50,
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """Return recent security events from the Scout security log.

    Useful for auditing a session before exporting a workflow — if a session
    had injection attempts, that should inform whether the workflow is trustworthy.

    Args:
        session_id: Filter to events from this session only.
        severity: Filter by severity level: 'info', 'warning', or 'critical'.
        limit: Maximum number of events to return. Default: 50.
    """
    limit = min(max(limit, 1), 500)
    events = read_security_log(
        session_id=session_id,
        severity=severity,
        limit=limit,
    )

    await ctx.info(f"Security log: {len(events)} event(s)")
    return {
        "events": events,
        "total_returned": len(events),
        "filters": {
            "session_id": session_id,
            "severity": severity,
            "limit": limit,
        },
    }


# --- Tool: allow_navigation ---


@mcp.tool()
async def allow_navigation(
    session_id: str,
    url: str,
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """Permit a single cross-origin navigation that was blocked by the navigation guard.

    Only needed in extension mode when allowed_domains is set and the agent
    navigates to an unlisted domain. The guard never auto-permits — this
    tool requires explicit agent invocation.

    Args:
        session_id: Active session ID.
        url: The URL to permit navigation to.
    """
    app_ctx = _get_ctx(ctx)
    session = _get_session(app_ctx, session_id)

    guard = session._navigation_guard
    if guard is None:
        return {
            "success": True,
            "message": "No navigation guard active for this session (launch mode or no allowed_domains set).",
        }

    guard.permit_url(url)
    await ctx.info(f"Navigation permitted to: {url}")
    return {
        "success": True,
        "permitted_url": url,
        "message": f"Navigation to '{url}' has been permitted. Retry the navigation.",
    }


# --- Entry Point ---


def main():
    """Run the MCP server via stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
