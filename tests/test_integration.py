"""Integration test — exercises the full scout + filter pipeline without MCP.

Requires a running browser (botasaurus-driver), so skip in CI.
Run manually: uv run pytest tests/test_integration.py -v -s
"""

import json
import pytest
from scout.scout import scout_page, build_element_summary, filter_elements
from scout.session import BrowserSession
from scout.history import SessionHistoryTracker

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def session():
    """Launch a real browser session for testing."""
    s = BrowserSession(headless=True)
    s.launch("https://news.ycombinator.com")
    yield s
    s.close()


def test_scout_returns_report(session):
    """Scout produces a valid ScoutReport with elements."""
    report = scout_page(session.driver)
    assert report.page_metadata.url
    assert report.page_metadata.title
    assert len(report.interactive_elements) > 0
    print(f"\n  Elements found: {len(report.interactive_elements)}")


def test_summary_is_compact(session):
    """Element summary is much smaller than full element list."""
    report = scout_page(session.driver)
    summary = build_element_summary(report.interactive_elements)

    summary_json = json.dumps(summary.model_dump(exclude_none=True))
    full_json = json.dumps(report.model_dump(exclude_none=True))

    print(f"\n  Full report: {len(full_json):,} chars")
    print(f"  Summary only: {len(summary_json):,} chars")
    print(f"  Reduction: {(1 - len(summary_json) / len(full_json)) * 100:.1f}%")

    # Summary should be < 5% the size of the full report
    assert len(summary_json) < len(full_json) * 0.05


def test_summary_mode_output(session):
    """Simulate what scout_page_tool returns in summary mode."""
    report = scout_page(session.driver)
    element_summary = build_element_summary(report.interactive_elements)

    # This is what the MCP tool returns in summary mode
    output = {
        "page_metadata": report.page_metadata.model_dump(exclude_none=True),
        "iframe_map": [f.model_dump(exclude_none=True) for f in report.iframe_map],
        "shadow_dom_boundaries": [s.model_dump(exclude_none=True) for s in report.shadow_dom_boundaries],
        "element_summary": element_summary.model_dump(exclude_none=True),
        "page_summary": report.page_summary,
    }

    output_json = json.dumps(output)
    full_json = json.dumps(report.model_dump(exclude_none=True))

    print(f"\n  Summary mode output: {len(output_json):,} chars ({len(output_json) // 4} est. tokens)")
    print(f"  Full mode output: {len(full_json):,} chars ({len(full_json) // 4} est. tokens)")
    print(f"  element_summary: {json.dumps(element_summary.model_dump(exclude_none=True), indent=2)}")

    # Summary mode should be < 10% of full mode
    assert len(output_json) < len(full_json) * 0.10


def test_find_elements_query(session):
    """find_elements with query returns targeted results."""
    report = scout_page(session.driver)
    session.cache_elements(report.interactive_elements)

    # HN has a "login" link
    matched = filter_elements(report.interactive_elements, query="login")
    print(f"\n  Matched 'login': {len(matched)} elements")
    for el in matched:
        print(f"    - {el.tag} | text='{el.text}' | selector='{el.selector}'")
    assert len(matched) >= 1


def test_find_elements_by_type(session):
    """find_elements with element_types filter works."""
    report = scout_page(session.driver)

    # Use a high max_results to avoid cap masking the filter
    links = filter_elements(report.interactive_elements, element_types=["a"], max_results=500)
    all_els = filter_elements(report.interactive_elements, visible_only=False, max_results=500)

    print(f"\n  Links: {len(links)} / {len(all_els)} total")
    assert len(links) <= len(all_els)
    assert all(el.tag == "a" for el in links)
    # HN has mostly links, but at least 1 input — so types filter should exclude something
    inputs = filter_elements(report.interactive_elements, element_types=["input"], max_results=500)
    print(f"  Inputs: {len(inputs)}")
    assert len(links) + len(inputs) <= len(all_els)


def test_empty_attributes_stripped(session):
    """Attributes with empty values should not appear in element data."""
    report = scout_page(session.driver)

    # Check a sample of elements for empty string attributes
    empty_count = 0
    total_attrs = 0
    for el in report.interactive_elements[:50]:
        for key, val in el.attributes.items():
            total_attrs += 1
            if val == "":
                empty_count += 1

    print(f"\n  Empty attrs: {empty_count} / {total_attrs} total")
    # With our JS change, there should be zero empty string attributes
    assert empty_count == 0, f"Found {empty_count} empty attribute values — JS stripping not working"


def test_history_stores_summary(session):
    """History records summary-level scouts, not full element lists."""
    tracker = SessionHistoryTracker("test-session")
    report = scout_page(session.driver)

    tracker.record_scout(report)
    history = tracker.get_full_history()

    scout_record = history.scouts[0]
    record_json = json.dumps(scout_record.model_dump(exclude_none=True))
    full_json = json.dumps(report.model_dump(exclude_none=True))

    print(f"\n  History scout record: {len(record_json):,} chars")
    print(f"  Full scout report: {len(full_json):,} chars")

    # History record should be tiny compared to full report
    assert len(record_json) < len(full_json) * 0.05
    # Should not contain interactive_elements
    assert "interactive_elements" not in record_json
