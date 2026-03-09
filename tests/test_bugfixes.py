"""Unit tests for Issue #1 bugfixes — iframe click guard, scroll aliases.

These are pure-Python unit tests that do NOT require a real browser.
Run: uv run pytest tests/test_bugfixes.py -v
"""

from unittest.mock import MagicMock

import pytest

from scout.actions import _parse_scroll_value, _selector_targets_iframe, execute_action


# ---------------------------------------------------------------------------
# Fix 1: _selector_targets_iframe
# ---------------------------------------------------------------------------


class TestSelectorTargetsIframe:
    """Zero-cost regex check that detects iframe selectors."""

    def test_bare_iframe(self):
        assert _selector_targets_iframe("iframe") is True

    def test_iframe_with_attribute(self):
        assert _selector_targets_iframe('iframe[src*="membership.io"]') is True

    def test_iframe_with_id(self):
        assert _selector_targets_iframe("iframe#content") is True

    def test_iframe_with_class(self):
        assert _selector_targets_iframe("iframe.main-frame") is True

    def test_iframe_nested_child(self):
        assert _selector_targets_iframe("div > iframe") is True

    def test_iframe_descendant(self):
        assert _selector_targets_iframe(".wrapper iframe[src='foo']") is True

    def test_iframe_sibling(self):
        assert _selector_targets_iframe("div + iframe") is True

    def test_iframe_general_sibling(self):
        assert _selector_targets_iframe("div ~ iframe") is True

    def test_iframe_case_insensitive(self):
        assert _selector_targets_iframe("IFRAME#content") is True
        assert _selector_targets_iframe("IFrame[src='x']") is True

    def test_iframe_with_pseudo(self):
        assert _selector_targets_iframe("iframe:first-child") is True

    def test_not_iframe_button(self):
        assert _selector_targets_iframe("#click-btn") is False

    def test_not_iframe_wrapper(self):
        """Custom element 'iframe-wrapper' is NOT an iframe tag."""
        assert _selector_targets_iframe("iframe-wrapper") is False

    def test_not_iframe_class_only(self):
        assert _selector_targets_iframe(".iframe-class") is False

    def test_not_iframe_data_attr(self):
        assert _selector_targets_iframe("[data-iframe='true']") is False

    def test_not_iframe_id(self):
        assert _selector_targets_iframe("#iframe") is False

    def test_click_iframe_returns_error(self):
        """execute_action returns an error when clicking an iframe selector."""
        mock_driver = MagicMock()
        mock_driver.current_url = "http://example.com"
        result, record = execute_action(
            mock_driver,
            "click",
            selector='iframe[src*="membership.io"]',
            wait_after=0,
        )
        assert result.success is False
        assert "frame_context" in result.error
        assert "Cannot click" in result.error


# ---------------------------------------------------------------------------
# Fix 2: _parse_scroll_value
# ---------------------------------------------------------------------------


class TestParseScrollValue:
    """Scroll value parser supporting aliases and pixel amounts."""

    def test_down(self):
        assert _parse_scroll_value("down") == 500

    def test_up(self):
        assert _parse_scroll_value("up") == -500

    def test_down_case_insensitive(self):
        assert _parse_scroll_value("Down") == 500
        assert _parse_scroll_value("DOWN") == 500

    def test_up_case_insensitive(self):
        assert _parse_scroll_value("Up") == -500

    def test_numeric_positive(self):
        assert _parse_scroll_value("300") == 300

    def test_numeric_negative(self):
        assert _parse_scroll_value("-200") == -200

    def test_none_default(self):
        assert _parse_scroll_value(None) == 500

    def test_empty_default(self):
        assert _parse_scroll_value("") == 500

    def test_whitespace_stripped(self):
        assert _parse_scroll_value("  down  ") == 500

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="Invalid scroll value"):
            _parse_scroll_value("sideways")


class TestScrollAction:
    """execute_action scroll with string aliases and frame context."""

    def _mock_driver(self):
        driver = MagicMock()
        driver.current_url = "http://example.com"
        return driver

    def test_scroll_down_string(self):
        driver = self._mock_driver()
        result, _ = execute_action(driver, "scroll", value="down", wait_after=0)
        assert result.success is True
        driver.run_js.assert_called_once()
        call_arg = driver.run_js.call_args[0][0]
        assert "scrollBy" in call_arg
        assert "500" in call_arg

    def test_scroll_up_string(self):
        driver = self._mock_driver()
        result, _ = execute_action(driver, "scroll", value="up", wait_after=0)
        assert result.success is True
        call_arg = driver.run_js.call_args[0][0]
        assert "scrollBy" in call_arg
        assert "-500" in call_arg

    def test_scroll_top(self):
        driver = self._mock_driver()
        result, _ = execute_action(driver, "scroll", value="top", wait_after=0)
        assert result.success is True
        call_arg = driver.run_js.call_args[0][0]
        assert "scrollTo(0, 0)" in call_arg
        assert "top" in result.action_performed.lower()

    def test_scroll_bottom(self):
        driver = self._mock_driver()
        result, _ = execute_action(driver, "scroll", value="bottom", wait_after=0)
        assert result.success is True
        call_arg = driver.run_js.call_args[0][0]
        assert "scrollTo" in call_arg
        assert "scrollHeight" in call_arg
        assert "bottom" in result.action_performed.lower()

    def test_scroll_uses_target_not_driver(self):
        """Scroll with frame_context uses target.run_js, not driver.run_js."""
        driver = self._mock_driver()
        mock_iframe = MagicMock()
        driver.select_iframe.return_value = mock_iframe

        result, _ = execute_action(
            driver, "scroll", value="300",
            frame_context="iframe#content", wait_after=0,
        )
        assert result.success is True
        mock_iframe.run_js.assert_called_once()
        driver.run_js.assert_not_called()
