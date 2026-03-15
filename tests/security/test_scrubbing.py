"""Tests for POST body scrubbing in network monitor responses."""

import pytest

from scout.security.scrubbing import scrub_network_events, scrub_post_body


class TestScrubPostBody:
    """Test individual POST body scrubbing patterns."""

    def test_scrub_url_encoded_password(self):
        body = "username=admin&password=secret123&submit=true"
        scrubbed, count = scrub_post_body(body)
        assert "secret123" not in scrubbed
        assert "password=[REDACTED]" in scrubbed
        assert "username=admin" in scrubbed
        assert count >= 1

    def test_scrub_url_encoded_token(self):
        body = "token=abc123def456&action=login"
        scrubbed, count = scrub_post_body(body)
        assert "abc123def456" not in scrubbed
        assert "token=[REDACTED]" in scrubbed
        assert count >= 1

    def test_scrub_url_encoded_api_key(self):
        body = "api_key=sk_live_12345&data=hello"
        scrubbed, count = scrub_post_body(body)
        assert "sk_live_12345" not in scrubbed
        assert count >= 1

    def test_scrub_json_password(self):
        body = '{"username": "admin", "password": "secret123"}'
        scrubbed, count = scrub_post_body(body)
        assert "secret123" not in scrubbed
        assert '"password": "[REDACTED]"' in scrubbed
        assert count >= 1

    def test_scrub_json_token(self):
        body = '{"token": "eyJhbGciOiJIUzI1NiJ9"}'
        scrubbed, count = scrub_post_body(body)
        assert "eyJhbGciOiJIUzI1NiJ9" not in scrubbed
        assert count >= 1

    def test_scrub_json_client_secret(self):
        body = '{"client_secret": "mysecretvalue", "client_id": "myid"}'
        scrubbed, count = scrub_post_body(body)
        assert "mysecretvalue" not in scrubbed
        assert "myid" in scrubbed
        assert count >= 1

    def test_scrub_env_key_match(self):
        body = "CUSTOM_KEY=customvalue&other=data"
        scrubbed, count = scrub_post_body(body, env_keys={"CUSTOM_KEY"})
        assert "customvalue" not in scrubbed
        assert count >= 1

    def test_scrub_env_value_match(self):
        body = "data=some_text_with_mysecrettoken_in_it"
        scrubbed, count = scrub_post_body(
            body, env_values={"API_TOKEN": "mysecrettoken"}
        )
        assert "mysecrettoken" not in scrubbed
        assert count >= 1

    def test_no_scrubbing_on_clean_body(self):
        body = "name=John&city=NYC&age=30"
        scrubbed, count = scrub_post_body(body)
        assert scrubbed == body
        assert count == 0

    def test_none_body(self):
        scrubbed, count = scrub_post_body(None)
        assert scrubbed is None
        assert count == 0

    def test_empty_body(self):
        scrubbed, count = scrub_post_body("")
        assert scrubbed == ""
        assert count == 0

    def test_preserves_structure(self):
        """Keys should remain, only values redacted."""
        body = '{"password": "secret", "username": "admin"}'
        scrubbed, count = scrub_post_body(body)
        assert '"password"' in scrubbed
        assert '"username"' in scrubbed
        assert '"admin"' in scrubbed

    def test_multiple_sensitive_fields(self):
        body = "password=abc&token=def&api_key=ghi"
        scrubbed, count = scrub_post_body(body)
        assert "abc" not in scrubbed
        assert "def" not in scrubbed
        assert "ghi" not in scrubbed
        assert count >= 3

    def test_short_env_value_not_scrubbed(self):
        """Values < 4 chars should not be scrubbed to avoid false positives."""
        body = "data=abc"
        scrubbed, count = scrub_post_body(body, env_values={"KEY": "abc"})
        # Short values are skipped
        assert count == 0


class TestScrubNetworkEvents:
    """Test scrubbing across network event lists."""

    def test_scrubs_events_with_response_body(self):
        events = [
            {
                "url": "http://example.com/api/login",
                "method": "POST",
                "response_body": '{"password": "secret123"}',
            },
            {
                "url": "http://example.com/api/data",
                "method": "GET",
                "response_body": '{"data": "clean"}',
            },
        ]
        scrubbed, total = scrub_network_events(events)
        assert "secret123" not in scrubbed[0]["response_body"]
        assert "clean" in scrubbed[1]["response_body"]
        assert total >= 1

    def test_events_without_body_unchanged(self):
        events = [
            {"url": "http://example.com", "method": "GET"},
        ]
        scrubbed, total = scrub_network_events(events)
        assert total == 0
        assert scrubbed[0] == events[0]
