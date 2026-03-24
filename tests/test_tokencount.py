"""Tests for token counting utility and session history integration."""

import json

from scout.tokencount import count_tokens
from scout.history import SessionHistoryTracker


class TestCountTokens:
    def test_counts_simple_string(self):
        tokens = count_tokens("hello world")
        assert tokens > 0

    def test_empty_string_zero_tokens(self):
        assert count_tokens("") == 0

    def test_json_payload(self):
        data = json.dumps({"page_metadata": {"url": "https://example.com", "title": "Test"}})
        tokens = count_tokens(data)
        # A short JSON payload should be a modest number of tokens
        assert 5 < tokens < 200

    def test_longer_text_more_tokens(self):
        short = count_tokens("hello")
        long = count_tokens("hello " * 100)
        assert long > short


class TestHistoryTokenTracking:
    def test_record_response_tokens(self):
        tracker = SessionHistoryTracker("test123")
        tokens = tracker.record_response_tokens("scout_page", '{"url": "https://example.com"}')
        assert tokens > 0
        assert len(tracker.token_usage) == 1
        assert tracker.token_usage[0].tool == "scout_page"
        assert tracker.token_usage[0].tokens == tokens
        assert tracker._total_tokens == tokens

    def test_token_summary_aggregates(self):
        tracker = SessionHistoryTracker("test123")
        tracker.record_response_tokens("scout_page", "short response")
        tracker.record_response_tokens("scout_page", "another short response")
        tracker.record_response_tokens("find_elements", "element data here")

        summary = tracker.get_token_summary()
        assert summary.total_responses == 3
        assert summary.total_tokens > 0
        assert "scout_page" in summary.by_tool
        assert "find_elements" in summary.by_tool

    def test_record_image_tokens(self):
        tracker = SessionHistoryTracker("test123")
        tracker.record_image_tokens("take_screenshot_image", 1600, 50000)
        assert len(tracker.token_usage) == 1
        assert tracker.token_usage[0].tokens == 1600
        assert tracker._total_tokens == 1600

    def test_full_history_includes_token_data(self):
        tracker = SessionHistoryTracker("test123")
        tracker.record_response_tokens("scout_page", "test response data")
        history = tracker.get_full_history()
        assert len(history.token_usage) == 1
        assert history.token_summary is not None
        assert history.token_summary.total_tokens > 0
        assert history.token_summary.total_responses == 1

    def test_chars_tracked(self):
        tracker = SessionHistoryTracker("test123")
        text = "some response text"
        tracker.record_response_tokens("scout_page", text)
        assert tracker.token_usage[0].chars == len(text)

    def test_by_tool_accumulates(self):
        tracker = SessionHistoryTracker("test123")
        tracker.record_response_tokens("scout_page", "response 1")
        t1 = tracker.token_usage[0].tokens
        tracker.record_response_tokens("scout_page", "response 2")
        t2 = tracker.token_usage[1].tokens
        summary = tracker.get_token_summary()
        assert summary.by_tool["scout_page"] == t1 + t2
