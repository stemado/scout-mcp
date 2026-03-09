"""Unit tests for smart form input helpers (no browser required)."""

from unittest.mock import MagicMock

from scout.actions import _try_constrained_input, _is_submit_element


class TestTryConstrainedInput:
    """Tests for the constrained input auto-detection helper."""

    def test_returns_type_for_time_input(self):
        target = MagicMock()
        target.run_js.return_value = {"action": "injected", "type": "time"}
        assert _try_constrained_input(target, "#time", "11:45") == "time"

    def test_returns_type_for_date_input(self):
        target = MagicMock()
        target.run_js.return_value = {"action": "injected", "type": "date"}
        assert _try_constrained_input(target, "#date", "2026-03-15") == "date"

    def test_returns_none_for_text_input(self):
        target = MagicMock()
        target.run_js.return_value = {"action": "passthrough", "type": "text"}
        assert _try_constrained_input(target, "#name", "Scout") is None

    def test_returns_none_for_not_found(self):
        target = MagicMock()
        target.run_js.return_value = {"action": "not_found"}
        assert _try_constrained_input(target, "#missing", "value") is None

    def test_returns_none_on_exception(self):
        target = MagicMock()
        target.run_js.side_effect = RuntimeError("browser crash")
        assert _try_constrained_input(target, "#time", "11:45") is None

    def test_returns_none_for_unexpected_result(self):
        target = MagicMock()
        target.run_js.return_value = None
        assert _try_constrained_input(target, "#time", "11:45") is None


class TestIsSubmitElement:
    """Tests for the submit button detection helper."""

    def test_returns_true_for_submit_button(self):
        target = MagicMock()
        target.run_js.return_value = True
        assert _is_submit_element(target, "#submit-btn") is True

    def test_returns_false_for_normal_button(self):
        target = MagicMock()
        target.run_js.return_value = False
        assert _is_submit_element(target, "#noop-btn") is False

    def test_returns_false_on_exception(self):
        target = MagicMock()
        target.run_js.side_effect = RuntimeError("crash")
        assert _is_submit_element(target, "#submit-btn") is False
