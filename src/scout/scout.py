"""Page reconnaissance — injects JavaScript to collect structured DOM intelligence."""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

from .models import (
    ElementSummary,
    IframeInfo,
    InteractiveElement,
    PageMetadata,
    ScoutReport,
    ShadowDomBoundary,
)

if TYPE_CHECKING:
    from botasaurus_driver import Driver

# Load the scout JS once at module level
_JS_DIR = os.path.join(os.path.dirname(__file__), "js")
_SCOUT_JS: str | None = None


def _get_scout_js() -> str:
    global _SCOUT_JS
    if _SCOUT_JS is None:
        with open(os.path.join(_JS_DIR, "scout_page.js"), encoding="utf-8") as f:
            _SCOUT_JS = f.read()
    return _SCOUT_JS


def scout_page(
    driver: Driver,
    focus_frame: str | None = None,
) -> ScoutReport:
    """Inject reconnaissance JS and parse the structured report.

    Args:
        driver: Active botasaurus-driver instance.
        focus_frame: Optional CSS selector of a specific iframe to scout instead of the full page.

    Returns:
        ScoutReport with complete page intelligence.
    """
    js_code = _get_scout_js()

    try:
        if focus_frame:
            # Scout inside a specific iframe
            iframe = driver.select_iframe(focus_frame)
            if iframe is None:
                return _error_report(f"Iframe not found: {focus_frame}", driver)
            raw = iframe.run_js(js_code)
        else:
            raw = driver.run_js(js_code)
    except Exception as e:
        return _error_report(f"Scout JS execution failed: {e}", driver)

    return _parse_report(raw, driver)


def _parse_report(raw: str | dict, driver: Driver) -> ScoutReport:
    """Parse the JSON output from scout JS into a ScoutReport model."""
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return _error_report(f"Scout JS returned invalid JSON: {raw[:200]}", driver)
    elif isinstance(raw, dict):
        data = raw
    else:
        return _error_report(f"Unexpected scout result type: {type(raw)}", driver)

    # Parse page metadata
    meta_raw = data.get("page_metadata", {})
    page_metadata = PageMetadata(
        url=meta_raw.get("url", ""),
        title=meta_raw.get("title", ""),
        load_state=meta_raw.get("load_state", "unknown"),
    )

    # Parse iframes
    iframes = []
    for item in data.get("iframe_map", []):
        iframes.append(IframeInfo(
            selector=item.get("selector", ""),
            src=item.get("src", ""),
            depth=item.get("depth", 0),
            cross_origin=item.get("cross_origin", False),
            accessible=item.get("accessible", False),
            children=item.get("children", []),
        ))

    # Parse shadow DOM boundaries
    shadows = []
    for item in data.get("shadow_dom_boundaries", []):
        shadows.append(ShadowDomBoundary(
            host_selector=item.get("host_selector", ""),
            mode=item.get("mode", "open"),
            frame_context=item.get("frame_context", "main"),
            child_interactive_count=item.get("child_interactive_count", 0),
        ))

    # Parse interactive elements
    elements = []
    for item in data.get("interactive_elements", []):
        elements.append(InteractiveElement(
            tag=item.get("tag", ""),
            type=item.get("type", ""),
            selector=item.get("selector", ""),
            text=item.get("text", ""),
            frame_context=item.get("frame_context", "main"),
            in_shadow_dom=item.get("in_shadow_dom", False),
            shadow_host=item.get("shadow_host"),
            attributes=item.get("attributes", {}),
            visible=item.get("visible", True),
            enabled=item.get("enabled", True),
        ))

    return ScoutReport(
        page_metadata=page_metadata,
        iframe_map=iframes,
        shadow_dom_boundaries=shadows,
        interactive_elements=elements,
        page_summary=data.get("page_summary", ""),
    )


def build_element_summary(elements: list[InteractiveElement]) -> ElementSummary:
    """Build an aggregated summary from a list of interactive elements."""
    by_type: dict[str, int] = {}
    by_frame: dict[str, int] = {}
    visible = 0

    for el in elements:
        by_type[el.tag] = by_type.get(el.tag, 0) + 1
        by_frame[el.frame_context] = by_frame.get(el.frame_context, 0) + 1
        if el.visible:
            visible += 1

    return ElementSummary(
        total=len(elements),
        visible=visible,
        by_type=by_type,
        by_frame=by_frame,
    )


def filter_elements(
    elements: list[InteractiveElement],
    query: str | None = None,
    element_types: list[str] | None = None,
    visible_only: bool = True,
    frame_context: str | None = None,
    max_results: int = 25,
) -> list[InteractiveElement]:
    """Filter interactive elements by query, type, visibility, and frame.

    Args:
        elements: Full list of interactive elements from a scout.
        query: Case-insensitive substring match against text, selector, and key attributes.
        element_types: Filter to only these tag names (e.g., ["button", "input"]).
        visible_only: If True, exclude hidden elements.
        frame_context: If set, only return elements in this frame.
        max_results: Maximum number of elements to return.
    """
    results = elements

    if visible_only:
        results = [el for el in results if el.visible]

    if element_types:
        type_set = {t.lower() for t in element_types}
        results = [el for el in results if el.tag.lower() in type_set]

    if frame_context:
        results = [el for el in results if el.frame_context == frame_context]

    if query:
        q = query.lower()
        filtered = []
        for el in results:
            searchable = [
                el.text,
                el.selector,
                el.attributes.get("id", ""),
                el.attributes.get("name", ""),
                el.attributes.get("aria_label", ""),
                el.attributes.get("placeholder", ""),
                el.attributes.get("href", ""),
            ]
            if any(q in field.lower() for field in searchable if field):
                filtered.append(el)
        results = filtered

    return results[:max_results]


def _error_report(message: str, driver: Driver) -> ScoutReport:
    """Create a minimal ScoutReport with an error message."""
    url = ""
    title = ""
    try:
        url = driver.current_url
        title = driver.title
    except Exception:
        pass

    return ScoutReport(
        page_metadata=PageMetadata(url=url, title=title, load_state="error"),
        page_summary=f"Scout error: {message}",
    )
