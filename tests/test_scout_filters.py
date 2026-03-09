"""Tests for element summary generation and query/filter logic."""

from scout.models import InteractiveElement
from scout.scout import build_element_summary, filter_elements


def _make_element(
    tag="button", type_="button", selector="#btn", text="Click",
    frame_context="main", visible=True, enabled=True,
    in_shadow_dom=False, shadow_host=None, attributes=None,
):
    return InteractiveElement(
        tag=tag, type=type_, selector=selector, text=text,
        frame_context=frame_context, visible=visible, enabled=enabled,
        in_shadow_dom=in_shadow_dom, shadow_host=shadow_host,
        attributes=attributes or {},
    )


class TestBuildElementSummary:
    def test_empty_list(self):
        summary = build_element_summary([])
        assert summary.total == 0
        assert summary.visible == 0
        assert summary.by_type == {}
        assert summary.by_frame == {}

    def test_counts_by_type(self):
        elements = [
            _make_element(tag="button", type_="button"),
            _make_element(tag="button", type_="submit"),
            _make_element(tag="input", type_="text"),
            _make_element(tag="a", type_="a"),
        ]
        summary = build_element_summary(elements)
        assert summary.total == 4
        assert summary.by_type["button"] == 2
        assert summary.by_type["input"] == 1
        assert summary.by_type["a"] == 1

    def test_counts_by_frame(self):
        elements = [
            _make_element(frame_context="main"),
            _make_element(frame_context="main"),
            _make_element(frame_context="iframe#content"),
        ]
        summary = build_element_summary(elements)
        assert summary.by_frame["main"] == 2
        assert summary.by_frame["iframe#content"] == 1

    def test_visible_count(self):
        elements = [
            _make_element(visible=True),
            _make_element(visible=False),
            _make_element(visible=True),
        ]
        summary = build_element_summary(elements)
        assert summary.visible == 2


class TestFilterElements:
    def test_no_filters_returns_all_visible(self):
        elements = [_make_element(text="A"), _make_element(text="B")]
        result = filter_elements(elements)
        assert len(result) == 2

    def test_query_matches_text(self):
        elements = [
            _make_element(text="Login"),
            _make_element(text="Submit"),
            _make_element(text="Log Out"),
        ]
        result = filter_elements(elements, query="log")
        assert len(result) == 2
        assert result[0].text == "Login"
        assert result[1].text == "Log Out"

    def test_query_matches_id_attribute(self):
        elements = [
            _make_element(text="Go", attributes={"id": "login-btn"}),
            _make_element(text="Go", attributes={"id": "submit-btn"}),
        ]
        result = filter_elements(elements, query="login")
        assert len(result) == 1

    def test_query_matches_aria_label(self):
        elements = [
            _make_element(text="", attributes={"aria_label": "Close dialog"}),
            _make_element(text="OK"),
        ]
        result = filter_elements(elements, query="close")
        assert len(result) == 1

    def test_query_matches_placeholder(self):
        elements = [
            _make_element(tag="input", text="", attributes={"placeholder": "Enter email"}),
        ]
        result = filter_elements(elements, query="email")
        assert len(result) == 1

    def test_query_matches_selector(self):
        elements = [
            _make_element(selector="#login-form > button"),
            _make_element(selector="#nav > a"),
        ]
        result = filter_elements(elements, query="#login-form")
        assert len(result) == 1

    def test_element_types_filter(self):
        elements = [
            _make_element(tag="button"),
            _make_element(tag="input"),
            _make_element(tag="a"),
        ]
        result = filter_elements(elements, element_types=["button", "a"])
        assert len(result) == 2

    def test_visible_only(self):
        elements = [
            _make_element(visible=True),
            _make_element(visible=False),
        ]
        result = filter_elements(elements, visible_only=True)
        assert len(result) == 1

    def test_visible_only_false(self):
        elements = [
            _make_element(visible=True),
            _make_element(visible=False),
        ]
        result = filter_elements(elements, visible_only=False)
        assert len(result) == 2

    def test_frame_context_filter(self):
        elements = [
            _make_element(frame_context="main"),
            _make_element(frame_context="iframe#sidebar"),
        ]
        result = filter_elements(elements, frame_context="iframe#sidebar")
        assert len(result) == 1

    def test_max_results(self):
        elements = [_make_element(text=f"Btn {i}") for i in range(50)]
        result = filter_elements(elements, max_results=10)
        assert len(result) == 10

    def test_combined_filters(self):
        elements = [
            _make_element(tag="button", text="Login", visible=True, frame_context="main"),
            _make_element(tag="button", text="Login", visible=False, frame_context="main"),
            _make_element(tag="input", text="Username", visible=True, frame_context="main"),
            _make_element(tag="button", text="Login", visible=True, frame_context="iframe#modal"),
        ]
        result = filter_elements(
            elements, query="login", element_types=["button"],
            visible_only=True, frame_context="main",
        )
        assert len(result) == 1
        assert result[0].text == "Login"
        assert result[0].visible is True
