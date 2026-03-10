"""Action execution — click, type, navigate, and other browser interactions."""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from .models import (
    ActionRecord,
    ActionResult,
    ElementInspection,
    JavaScriptRecord,
    JavaScriptResult,
    ScreenshotRecord,
    ScreenshotResult,
)
from .validation import validate_url

if TYPE_CHECKING:
    from botasaurus_driver import Driver

# Load inspect element JS once at module level
_JS_DIR = os.path.join(os.path.dirname(__file__), "js")
_INSPECT_JS: str | None = None


def _get_inspect_js() -> str:
    global _INSPECT_JS
    if _INSPECT_JS is None:
        with open(os.path.join(_JS_DIR, "inspect_element.js"), encoding="utf-8") as f:
            _INSPECT_JS = f.read()
    return _INSPECT_JS


def execute_action(
    driver: Driver,
    action: str,
    selector: str | None = None,
    value: str | None = None,
    frame_context: str | None = None,
    wait_after: int = 500,
) -> tuple[ActionResult, ActionRecord]:
    """Execute a single browser action and return the result + history record.

    Args:
        driver: Active botasaurus-driver instance.
        action: One of: click, type, select, navigate, scroll, wait, press_key, hover, clear.
        selector: CSS selector for the target element (required for most actions).
        value: Context-dependent value (text to type, URL to navigate, key to press, etc.).
        frame_context: Iframe selector path, or None/'main' for top-level page.
        wait_after: Milliseconds to wait after action completes.

    Returns:
        Tuple of (ActionResult for the tool response, ActionRecord for history).
    """
    start = time.perf_counter()
    timestamp = datetime.now(timezone.utc).isoformat()

    try:
        url_before = driver.current_url
    except Exception:
        url_before = ""

    error = None
    action_desc = ""
    pre_click_fingerprint = None

    try:
        # Resolve frame context — get the target to operate on
        target = _resolve_target(driver, frame_context)

        match action:
            case "click":
                _require(selector, "selector required for click")
                if _selector_targets_iframe(selector):
                    raise ValueError(
                        f"Cannot click an <iframe> element directly (selector: {selector}). "
                        f"To interact with content inside an iframe, use the "
                        f"'frame_context' parameter with this selector, then click "
                        f"elements within the iframe."
                    )
                # Capture DOM fingerprint before click for verification
                pre_click_fingerprint = _capture_dom_fingerprint(driver)
                target.click(selector)
                action_desc = f"Clicked '{selector}'"

            case "type":
                _require(selector, "selector required for type")
                _require(value, "value required for type")
                injected_type = _try_constrained_input(target, selector, value)
                if injected_type is None:
                    # Normal text input — use keystroke simulation
                    target.type(selector, value)
                    action_desc = f"Typed into '{selector}'"
                else:
                    # Constrained input — value was set via JS injection
                    action_desc = (
                        f"Set value on '{selector}' "
                        f"(type='{injected_type}', used direct value injection)"
                    )

            case "select":
                _require(selector, "selector required for select")
                _require(value, "value required for select")
                # botasaurus-driver's select_option supports value, index, or label
                if value.isdigit():
                    target.select_option(selector, index=int(value))
                else:
                    target.select_option(selector, value=value)
                action_desc = f"Selected '{value}' in '{selector}'"

            case "navigate":
                _require(value, "value (URL) required for navigate")
                validate_url(value, allow_localhost=os.environ.get("SCOUT_ALLOW_LOCALHOST", "").lower() in ("1", "true", "yes"))
                driver.get(value)
                action_desc = f"Navigated to '{value}'"

            case "scroll":
                lowered = (value or "").strip().lower()
                if lowered == "top":
                    target.run_js("window.scrollTo(0, 0)")
                    action_desc = "Scrolled to top"
                elif lowered == "bottom":
                    target.run_js("window.scrollTo(0, document.body.scrollHeight)")
                    action_desc = "Scrolled to bottom"
                else:
                    amount = _parse_scroll_value(value)
                    target.run_js(f"window.scrollBy(0, {json.dumps(amount)})")
                    action_desc = f"Scrolled by {amount}px"

            case "wait":
                # value is always milliseconds for consistency with wait_after
                if selector:
                    wait_sec = int(value or 8000) / 1000
                    target.wait_for_element(selector, wait=wait_sec)
                    action_desc = f"Waited for element '{selector}' (timeout: {wait_sec}s)"
                elif value:
                    time.sleep(int(value) / 1000)
                    action_desc = f"Waited {value}ms"
                else:
                    time.sleep(1)
                    action_desc = "Waited 1000ms"

            case "press_key":
                _require(value, "value (key name) required for press_key")
                # Use CDP Input.dispatchKeyEvent for reliable key presses
                from botasaurus_driver import cdp
                key_map = _get_key_map()
                key_info = key_map.get(value.lower(), {"key": value, "code": f"Key{value.upper()}"})

                driver.run_cdp_command(cdp.input_.dispatch_key_event(
                    type_="keyDown",
                    key=key_info["key"],
                    code=key_info["code"],
                    windows_virtual_key_code=key_info.get("keyCode", 0),
                ))
                driver.run_cdp_command(cdp.input_.dispatch_key_event(
                    type_="keyUp",
                    key=key_info["key"],
                    code=key_info["code"],
                    windows_virtual_key_code=key_info.get("keyCode", 0),
                ))
                action_desc = f"Pressed key '{value}'"

            case "hover":
                _require(selector, "selector required for hover")
                # Get element position and dispatch mouse move (json.dumps for safe JS escaping)
                sel_js = json.dumps(selector)
                hover_js = (
                    "const el = document.querySelector(" + sel_js + ");"
                    "if (!el) return null;"
                    "const rect = el.getBoundingClientRect();"
                    "return {x: rect.x + rect.width/2, y: rect.y + rect.height/2};"
                )
                pos = driver.run_js(hover_js)
                if pos:
                    from botasaurus_driver import cdp
                    driver.run_cdp_command(cdp.input_.dispatch_mouse_event(
                        type_="mouseMoved",
                        x=pos["x"],
                        y=pos["y"],
                    ))
                    action_desc = f"Hovered over '{selector}'"
                else:
                    raise ValueError(f"Element not found for hover: {selector}")

            case "clear":
                _require(selector, "selector required for clear")
                target.clear(selector)
                action_desc = f"Cleared '{selector}'"

            case _:
                raise ValueError(f"Unknown action: {action}")

    except Exception as e:
        error = str(e)
        action_desc = action_desc or f"Failed: {action}"

    # Wait after action
    if wait_after > 0:
        time.sleep(wait_after / 1000)

    try:
        url_after = driver.current_url
    except Exception:
        url_after = url_before

    elapsed = int((time.perf_counter() - start) * 1000)

    # Post-click verification: detect clicks that had no visible effect
    warning = None
    if (
        error is None
        and action == "click"
        and pre_click_fingerprint is not None
        and url_before == url_after
    ):
        post_fingerprint = _capture_dom_fingerprint(driver)
        if post_fingerprint and post_fingerprint == pre_click_fingerprint:
            # Check if this is a submit button for a more targeted warning
            if selector and _is_submit_element(
                _resolve_target(driver, frame_context), selector
            ):
                warning = (
                    "Click on submit button had no visible DOM effect. The form "
                    "may have submitted via AJAX (check network monitoring), or "
                    "the click may not have triggered submission. If the form did "
                    "not submit, use execute_javascript with "
                    "`document.querySelector('SELECTOR').closest('form')"
                    ".requestSubmit()` to submit programmatically."
                )
            else:
                warning = (
                    "Click reported success but no DOM changes detected (URL, child "
                    "count, title, and aria-hidden count are all unchanged). The click "
                    "may not have had an effect. Consider using inspect_element to check "
                    "if the element is visible, obscured, or in a shadow DOM. Increasing "
                    "wait_after may help if the page uses async rendering."
                )

    result = ActionResult(
        success=error is None,
        action_performed=action_desc,
        url_changed=url_before != url_after,
        current_url=url_after,
        error=error,
        warning=warning,
        elapsed_ms=elapsed,
    )

    record = ActionRecord(
        action=action,
        selector=selector,
        value=value,
        frame_context=frame_context,
        success=error is None,
        url_before=url_before,
        url_after=url_after,
        timestamp=timestamp,
        error=error,
    )

    return result, record


def _resolve_target(driver: Driver, frame_context: str | None):
    """Resolve the execution target (driver or iframe handle)."""
    if not frame_context or frame_context == "main":
        return driver

    # frame_context is a CSS selector for the iframe
    # Try select_iframe first (handles both same-origin and cross-origin)
    iframe = driver.select_iframe(frame_context)
    if iframe is None:
        raise ValueError(f"Iframe not found: {frame_context}")
    return iframe


def _require(val, message: str) -> None:
    if not val:
        raise ValueError(message)


def _selector_targets_iframe(selector: str) -> bool:
    """Check if a CSS selector targets an <iframe> element (zero-cost, no browser round-trip).

    Splits on CSS combinators to extract the final simple selector, then checks
    if it starts with 'iframe' followed by end-of-string, class, id, attribute,
    or pseudo selector.  Does NOT match custom elements like 'iframe-wrapper'.
    """
    parts = re.split(r'[\s>+~]+', selector.strip())
    final = parts[-1] if parts else selector
    return bool(re.match(r'^iframe(?:$|[#.\[:(])', final, re.IGNORECASE))


def _parse_scroll_value(value: str | None) -> int:
    """Parse a scroll value string into pixels.

    Supports:
      - None or empty: default 500px
      - "up": -500px
      - "down": 500px
      - numeric string: parsed as pixels (positive = down, negative = up)

    Raises ValueError for unrecognized strings.
    """
    if not value:
        return 500
    lowered = value.strip().lower()
    if lowered == "down":
        return 500
    if lowered == "up":
        return -500
    try:
        return int(value)
    except ValueError:
        raise ValueError(
            f"Invalid scroll value: '{value}'. "
            f"Use 'up', 'down', 'top', 'bottom', or a pixel amount (e.g. '500', '-300')."
        ) from None


def _capture_dom_fingerprint(driver: Driver) -> dict | None:
    """Capture a lightweight DOM fingerprint for change detection."""
    try:
        return driver.run_js(
            "return {"
            "  childCount: document.body ? document.body.children.length : 0,"
            "  title: document.title,"
            "  ariaHiddenCount: document.querySelectorAll('[aria-hidden]').length"
            "}"
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Smart type — constrained HTML5 input auto-detection
# ---------------------------------------------------------------------------
# HTML5 date/time inputs reject keystroke simulation because browsers enforce
# format constraints via an internal state machine. This helper detects
# constrained types and uses JS value injection + event dispatch instead.
# See docs/plans/2026-02-25-smart-form-input-design.md
# ---------------------------------------------------------------------------

_CONSTRAINED_INPUT_TYPES = frozenset({"date", "time", "datetime-local", "month", "week"})

# Atomic JS: detect input type AND set value in one round-trip.
# Uses the native HTMLInputElement.value setter to bypass framework overrides
# (React, Angular, etc.), then dispatches input + change events.
# NOTE: Uses 'return' + IIFE pattern for botasaurus run_js compatibility.
_CONSTRAINED_INPUT_JS = (
    "return (function(sel, val) {"
    "  var el = document.querySelector(sel);"
    "  if (!el) return {action: 'not_found'};"
    "  var type = (el.type || '').toLowerCase();"
    "  if (%s.indexOf(type) === -1) {"
    "    return {action: 'passthrough', type: type};"
    "  }"
    "  var setter = Object.getOwnPropertyDescriptor("
    "    HTMLInputElement.prototype, 'value'"
    "  ).set;"
    "  setter.call(el, val);"
    "  el.dispatchEvent(new Event('input', {bubbles: true}));"
    "  el.dispatchEvent(new Event('change', {bubbles: true}));"
    "  return {action: 'injected', type: type};"
    "})(%s, %s)"
)


def _try_constrained_input(target, selector: str, value: str) -> str | None:
    """Attempt value injection for constrained HTML5 input types.

    Executes a single atomic JS call that detects the input type and, if
    constrained (date, time, datetime-local, month, week), sets the value
    via the native setter + event dispatch.

    Returns the input type string if injection was performed, or None if
    the input is a normal type and keystroke simulation should be used.
    Falls back to None on any error (safe degradation to original behavior).
    """
    try:
        types_js = json.dumps(sorted(_CONSTRAINED_INPUT_TYPES))
        js = _CONSTRAINED_INPUT_JS % (types_js, json.dumps(selector), json.dumps(value))
        result = target.run_js(js)
        if isinstance(result, dict) and result.get("action") == "injected":
            return result.get("type", "unknown")
    except Exception:
        logging.debug("Constrained input detection failed for %s, falling back to keystrokes", selector, exc_info=True)
    return None


# ---------------------------------------------------------------------------
# Submit element detection for enhanced click warning
# ---------------------------------------------------------------------------

_SUBMIT_CHECK_JS = (
    "return (function(sel) {"
    "  var el = document.querySelector(sel);"
    "  if (!el) return false;"
    "  var tag = el.tagName.toLowerCase();"
    "  var type = (el.type || '').toLowerCase();"
    "  if (tag === 'input' && type === 'submit') return true;"
    "  if (tag === 'button') {"
    "    var attr = el.getAttribute('type');"
    "    if (attr && attr.toLowerCase() === 'submit') return true;"
    "    if (!attr && el.closest('form')) return true;"
    "  }"
    "  return false;"
    "})(%s)"
)


def _is_submit_element(target, selector: str) -> bool:
    """Check if the given selector targets a form submit button.

    Detects <input type="submit">, <button type="submit">, and <button>
    inside a <form> (default type is submit per HTML spec).
    Returns False on any error (safe degradation).
    """
    try:
        return bool(target.run_js(_SUBMIT_CHECK_JS % json.dumps(selector)))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# CDP-direct JavaScript evaluation helpers
# ---------------------------------------------------------------------------
# Botasaurus-driver's run_js wraps scripts in block bodies that require
# explicit 'return' statements.  These helpers bypass that wrapping and use
# CDP Runtime.evaluate directly so bare expressions (e.g. "document.title")
# return their value naturally.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Empty-result guard — "surprising emptiness" heuristic
# ---------------------------------------------------------------------------
# Detects scripts whose structure suggests non-trivial computation occurred
# but CDP returned undefined/null. Fires a warning, never modifies the script.
# See docs/plans/2026-02-25-empty-result-guard-design.md
# ---------------------------------------------------------------------------

_COMPUTATION_PATTERNS = [
    re.compile(r'\.\s*querySelector(All)?\s*\('),
    re.compile(r'\.\s*getElementById\s*\('),
    re.compile(r'\.\s*getElementsBy\w+\s*\('),
    re.compile(r'\.\s*(textContent|innerText|innerHTML|value|href|src)\b'),
    re.compile(r'\.\s*(map|filter|find|reduce|flatMap)\s*\('),
    re.compile(r'\w+\s*\[.+?\]'),
    re.compile(r'\b(let|const|var)\s+\w+\s*='),
    re.compile(r'JSON\.\s*(stringify|parse)\s*\('),
    re.compile(r'\bfetch\s*\('),
    re.compile(r'\.json\s*\('),
    re.compile(r'\bawait\s+'),
]


def _seems_like_computation(script: str) -> bool:
    """Return True if script structure suggests non-trivial computation occurred.

    Used by the empty-result guard to decide whether an undefined/null result
    is *surprising* (script queried DOM, read properties, transformed collections)
    vs *expected* (script only performed side effects like console.log).
    """
    return any(pat.search(script) for pat in _COMPUTATION_PATTERNS)


def _extract_exception_text(exception_details) -> str:
    """Extract a human-readable error message from CDP ExceptionDetails."""
    if exception_details.exception and exception_details.exception.description:
        return exception_details.exception.description
    return exception_details.text


def _is_return_syntax_error(error_text: str) -> bool:
    """Check if error is a SyntaxError caused by 'return' outside function."""
    lower = error_text.lower()
    return "syntaxerror" in lower and "return" in lower


def _extract_remote_value(remote_object) -> tuple[Any, str]:
    """Convert CDP RemoteObject to (python_value, type_string)."""
    type_str = remote_object.type_

    # Handle unserializable values (NaN, Infinity, -Infinity, bigint)
    if remote_object.unserializable_value is not None:
        unser = str(remote_object.unserializable_value)
        if unser.endswith("n"):  # bigint like "42n"
            try:
                return (int(unser[:-1]), "number")
            except ValueError:
                return (unser, "string")
        # NaN, Infinity, -Infinity are not JSON-representable
        return (None, "number")

    if type_str == "undefined":
        return (None, "undefined")
    if type_str == "object" and remote_object.subtype == "null":
        return (None, "null")
    if type_str in ("string", "number", "boolean"):
        return (remote_object.value, type_str)
    if type_str == "object":
        value = remote_object.value
        if isinstance(value, list):
            return (value, "array")
        return (value, "object")
    # symbol, function, etc. — return description as string
    return (remote_object.description or str(remote_object.value), "string")


def _cdp_evaluate_direct(target, script: str) -> tuple[Any, str]:
    """Evaluate JS via CDP Runtime.evaluate on a target with run_cdp_command."""
    from botasaurus_driver import cdp

    response = target.run_cdp_command(cdp.runtime.evaluate(
        expression=script,
        return_by_value=True,
        await_promise=True,
        user_gesture=True,
        repl_mode=True,
    ))

    if not response:
        raise RuntimeError("CDP Runtime.evaluate returned no response")

    remote_object, exception_details = response

    if exception_details is not None:
        error_text = _extract_exception_text(exception_details)
        if "return" in script and _is_return_syntax_error(error_text):
            # Retry with function wrapper for backward compatibility
            wrapped = f"(() => {{ {script} }})()"
            return _cdp_evaluate_direct(target, wrapped)
        raise RuntimeError(error_text)

    return _extract_remote_value(remote_object)


def _cdp_evaluate_iframe_element(iframe_elem, script: str) -> tuple[Any, str]:
    """Evaluate JS inside a same-origin iframe using callFunctionOn.

    IframeElement cannot use run_cdp_command (raises UnavailableMethodError).
    We use Runtime.callFunctionOn targeting the iframe's document node with
    indirect eval to get natural expression return semantics.
    """
    from botasaurus_driver import cdp

    doc_core = iframe_elem.doc_elem._elem
    tab = doc_core._tab

    # Resolve the document node to get a RemoteObject with object_id
    remote_obj = tab.send(
        cdp.dom.resolve_node(backend_node_id=doc_core.backend_node_id)
    )
    if not remote_obj or not remote_obj.object_id:
        raise RuntimeError("Could not resolve iframe document for JS evaluation")

    # Indirect eval: (0, eval)() runs in global scope of the iframe context
    eval_fn = f"function() {{ return (0, eval)({json.dumps(script)}); }}"

    response = tab.send(cdp.runtime.call_function_on(
        function_declaration=eval_fn,
        object_id=remote_obj.object_id,
        return_by_value=True,
        await_promise=True,
        user_gesture=True,
    ))

    if not response:
        raise RuntimeError("CDP callFunctionOn returned no response")

    remote_object, exception_details = response

    if exception_details is not None:
        error_text = _extract_exception_text(exception_details)
        if "return" in script and _is_return_syntax_error(error_text):
            # Retry with function body for backward compatibility
            wrapped_fn = f"function() {{ {script} }}"
            response = tab.send(cdp.runtime.call_function_on(
                function_declaration=wrapped_fn,
                object_id=remote_obj.object_id,
                return_by_value=True,
                await_promise=True,
                user_gesture=True,
            ))
            if not response:
                raise RuntimeError("CDP callFunctionOn retry returned no response")
            remote_object, exception_details = response
            if exception_details is not None:
                raise RuntimeError(_extract_exception_text(exception_details))
        else:
            raise RuntimeError(error_text)

    return _extract_remote_value(remote_object)


def _cdp_evaluate(
    driver: Driver,
    script: str,
    frame_context: str | None = None,
) -> tuple[Any, str]:
    """Evaluate JS via CDP, bypassing botasaurus wrapping.

    Returns (python_value, result_type_string) tuple.
    """
    from botasaurus_driver.driver import IframeElement

    target = _resolve_target(driver, frame_context)

    if isinstance(target, IframeElement):
        return _cdp_evaluate_iframe_element(target, script)
    # Driver (main page) or IframeTab (cross-origin) — both support run_cdp_command
    return _cdp_evaluate_direct(target, script)


def run_javascript(
    driver: Driver,
    script: str,
    frame_context: str | None = None,
) -> tuple[JavaScriptResult, JavaScriptRecord]:
    """Execute arbitrary JavaScript in the page context.

    Uses CDP Runtime.evaluate directly for natural expression return semantics.
    Scripts with explicit 'return' statements also work (backward compatible).

    Args:
        driver: Active botasaurus-driver instance.
        script: JavaScript code to execute. The last expression's value is returned.
        frame_context: Iframe selector path, or None/'main' for top-level page.

    Returns:
        Tuple of (JavaScriptResult for tool response, JavaScriptRecord for history).
    """
    start = time.perf_counter()
    timestamp = datetime.now(timezone.utc).isoformat()

    try:
        result_value, result_type = _cdp_evaluate(driver, script, frame_context)
        elapsed = int((time.perf_counter() - start) * 1000)

        # Empty-result guard: warn when result is surprising
        warning = None
        if result_value is None and _seems_like_computation(script):
            warning = (
                f"Warning: result is {result_type} but script appears to perform "
                "non-trivial computation (DOM query, property read, collection "
                "operation, variable assignment). The last statement may be a loop "
                "or void expression whose completion value is undefined. Rewrite "
                "so the final expression evaluates to the intended value — e.g., "
                "end with a variable reference like `myResult;` rather than a "
                "loop or forEach."
            )

        js_result = JavaScriptResult(
            success=True,
            result=result_value,
            result_type=result_type,
            warning=warning,
            elapsed_ms=elapsed,
        )

        result_str = (
            json.dumps(result_value, default=str)
            if result_value is not None
            else result_type
        )
        record = JavaScriptRecord(
            script_preview=script[:200],
            frame_context=frame_context,
            success=True,
            result_preview=result_str[:500],
            timestamp=timestamp,
        )

        return js_result, record

    except Exception as e:
        elapsed = int((time.perf_counter() - start) * 1000)

        js_result = JavaScriptResult(
            success=False,
            error=str(e),
            elapsed_ms=elapsed,
        )

        record = JavaScriptRecord(
            script_preview=script[:200],
            frame_context=frame_context,
            success=False,
            result_preview=f"ERROR: {e}"[:500],
            timestamp=timestamp,
        )

        return js_result, record


def take_screenshot(
    driver: Driver,
    image_format: str = "png",
    quality: int | None = None,
    clip_x: float | None = None,
    clip_y: float | None = None,
    clip_width: float | None = None,
    clip_height: float | None = None,
    full_page: bool = False,
) -> tuple[ScreenshotResult, ScreenshotRecord, bytes | None]:
    """Capture a screenshot of the current page via CDP.

    Args:
        driver: Active botasaurus-driver instance.
        image_format: Image format: 'png' or 'jpeg'.
        quality: JPEG quality (1-100). Only used when image_format='jpeg'.
        clip_x, clip_y, clip_width, clip_height: Optional clip region.
        full_page: If True, capture the full scrollable page. Note: pages with
                   lazy-loaded content may still show incomplete results.

    Returns:
        Tuple of (ScreenshotResult metadata, ScreenshotRecord for history, raw image bytes or None on error).
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    clipped = all(v is not None for v in (clip_x, clip_y, clip_width, clip_height))

    if image_format not in ("png", "jpeg"):
        return (
            ScreenshotResult(success=False, format=image_format, error=f"Invalid format '{image_format}'. Must be 'png' or 'jpeg'."),
            ScreenshotRecord(format=image_format, timestamp=timestamp),
            None,
        )

    try:
        from botasaurus_driver import cdp

        # Build CDP screenshot parameters
        kwargs: dict[str, Any] = {"format_": image_format}

        if image_format == "jpeg" and quality is not None:
            kwargs["quality"] = quality

        if clipped:
            kwargs["clip"] = cdp.page.Viewport(
                x=clip_x,
                y=clip_y,
                width=clip_width,
                height=clip_height,
                scale=1,
            )

        if full_page:
            kwargs["capture_beyond_viewport"] = True

        # CDP returns base64-encoded image data
        b64_data = driver.run_cdp_command(cdp.page.capture_screenshot(**kwargs))
        raw_bytes = base64.b64decode(b64_data)

        result = ScreenshotResult(
            success=True,
            format=image_format,
            byte_size=len(raw_bytes),
            clipped=clipped,
        )

        record = ScreenshotRecord(
            format=image_format,
            clipped=clipped,
            full_page=full_page,
            timestamp=timestamp,
        )

        return result, record, raw_bytes

    except Exception as e:
        result = ScreenshotResult(
            success=False,
            format=image_format,
            error=str(e),
        )

        record = ScreenshotRecord(
            format=image_format,
            clipped=clipped,
            full_page=full_page,
            timestamp=timestamp,
        )

        return result, record, None


def inspect_element(
    driver: Driver,
    selector: str,
    frame_context: str | None = None,
    include_listeners: bool = False,
    include_children: bool = True,
) -> ElementInspection:
    """Inspect a single DOM element in detail.

    Args:
        driver: Active botasaurus-driver instance.
        selector: CSS selector of the element to inspect.
        frame_context: Iframe selector path, or None/'main' for top-level page.
        include_listeners: Whether to attempt detecting event listeners. Default: false.
        include_children: Whether to include children summary. Default: true.

    Returns:
        ElementInspection with detailed element analysis.
    """
    try:
        target = _resolve_target(driver, frame_context)

        js_template = _get_inspect_js()
        # Single-pass replacement to prevent cascading substitution
        # (avoids corruption if selector contains placeholder text)
        replacements = {
            "__SELECTOR__": json.dumps(selector),
            "__INCLUDE_LISTENERS__": json.dumps(include_listeners),
            "__INCLUDE_CHILDREN__": json.dumps(include_children),
        }
        pattern = re.compile("|".join(re.escape(k) for k in replacements))
        js_code = pattern.sub(lambda m: replacements[m.group(0)], js_template)

        raw = target.run_js(js_code)

        if isinstance(raw, str):
            data = json.loads(raw)
        elif isinstance(raw, dict):
            data = raw
        else:
            return ElementInspection(
                found=False,
                selector=selector,
                error=f"Unexpected result type from inspect JS: {type(raw)}",
            )

        return ElementInspection(
            found=data.get("found", False),
            selector=selector,
            tag=data.get("tag", ""),
            bounding_rect=data.get("bounding_rect", {}),
            computed_visibility=data.get("computed_visibility", {}),
            is_visible=data.get("is_visible", False),
            is_obscured=data.get("is_obscured", False),
            obscured_by=data.get("obscured_by"),
            in_shadow_dom=data.get("in_shadow_dom", False),
            shadow_host=data.get("shadow_host"),
            parent_chain=data.get("parent_chain", []),
            attributes=data.get("attributes", {}),
            aria=data.get("aria", {}),
            input_state=data.get("input_state", {}),
            children_summary=data.get("children_summary", {}),
            event_listeners=data.get("event_listeners", []),
        )

    except Exception as e:
        return ElementInspection(
            found=False,
            selector=selector,
            error=str(e),
        )


def _get_key_map() -> dict:
    """Map common key names to CDP key event parameters."""
    return {
        "enter": {"key": "Enter", "code": "Enter", "keyCode": 13},
        "tab": {"key": "Tab", "code": "Tab", "keyCode": 9},
        "escape": {"key": "Escape", "code": "Escape", "keyCode": 27},
        "space": {"key": " ", "code": "Space", "keyCode": 32},
        "backspace": {"key": "Backspace", "code": "Backspace", "keyCode": 8},
        "delete": {"key": "Delete", "code": "Delete", "keyCode": 46},
        "arrowup": {"key": "ArrowUp", "code": "ArrowUp", "keyCode": 38},
        "arrowdown": {"key": "ArrowDown", "code": "ArrowDown", "keyCode": 40},
        "arrowleft": {"key": "ArrowLeft", "code": "ArrowLeft", "keyCode": 37},
        "arrowright": {"key": "ArrowRight", "code": "ArrowRight", "keyCode": 39},
        "home": {"key": "Home", "code": "Home", "keyCode": 36},
        "end": {"key": "End", "code": "End", "keyCode": 35},
        "pageup": {"key": "PageUp", "code": "PageUp", "keyCode": 33},
        "pagedown": {"key": "PageDown", "code": "PageDown", "keyCode": 34},
    }
