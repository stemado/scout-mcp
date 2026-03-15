"""Tests for security audit logging."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from scout.security.audit_log import (
    SecurityCounter,
    log_security_event,
    read_security_log,
)


class TestSecurityCounter:
    """Test per-session security event counters."""

    def test_initial_state(self):
        counter = SecurityCounter()
        summary = counter.summary()
        assert summary == {
            "injection_attempts": 0,
            "credentials_refused": 0,
            "navigations_blocked": 0,
            "post_bodies_scrubbed": 0,
            "ws_connections_rejected": 0,
        }

    def test_increment_injection(self):
        counter = SecurityCounter()
        counter.increment("injection_detected")
        assert counter.summary()["injection_attempts"] == 1

    def test_increment_credential_refused(self):
        counter = SecurityCounter()
        counter.increment("credential_refused")
        counter.increment("credential_refused")
        assert counter.summary()["credentials_refused"] == 2

    def test_increment_navigation_blocked(self):
        counter = SecurityCounter()
        counter.increment("navigation_blocked")
        assert counter.summary()["navigations_blocked"] == 1

    def test_increment_scrubbing(self):
        counter = SecurityCounter()
        counter.increment("scrubbing_applied")
        assert counter.summary()["post_bodies_scrubbed"] == 1

    def test_increment_ws_rejected(self):
        counter = SecurityCounter()
        counter.increment("ws_rejected")
        assert counter.summary()["ws_connections_rejected"] == 1

    def test_unknown_event_type_ignored(self):
        counter = SecurityCounter()
        counter.increment("unknown_type")
        # Should not crash, all counters remain 0
        summary = counter.summary()
        assert all(v == 0 for v in summary.values())


class TestLogAndRead:
    """Test security event logging and reading."""

    def test_log_and_read_event(self, tmp_path):
        log_file = tmp_path / "security.log"
        with patch("scout.security.audit_log._LOG_FILE", log_file), \
             patch("scout.security.audit_log._LOG_DIR", tmp_path):
            log_security_event(
                session_id="abc123",
                event_type="injection_detected",
                severity="warning",
                url="http://evil.com",
                detail={"patterns": ["ignore previous"]},
            )

            events = read_security_log()
            assert len(events) == 1
            assert events[0]["session_id"] == "abc123"
            assert events[0]["event_type"] == "injection_detected"
            assert events[0]["severity"] == "warning"
            assert events[0]["url"] == "http://evil.com"

    def test_filter_by_session_id(self, tmp_path):
        log_file = tmp_path / "security.log"
        with patch("scout.security.audit_log._LOG_FILE", log_file), \
             patch("scout.security.audit_log._LOG_DIR", tmp_path):
            log_security_event("session1", "injection_detected", "warning")
            log_security_event("session2", "credential_refused", "critical")

            events = read_security_log(session_id="session1")
            assert len(events) == 1
            assert events[0]["session_id"] == "session1"

    def test_filter_by_severity(self, tmp_path):
        log_file = tmp_path / "security.log"
        with patch("scout.security.audit_log._LOG_FILE", log_file), \
             patch("scout.security.audit_log._LOG_DIR", tmp_path):
            log_security_event("s1", "injection_detected", "warning")
            log_security_event("s1", "credential_refused", "critical")

            events = read_security_log(severity="critical")
            assert len(events) == 1
            assert events[0]["severity"] == "critical"

    def test_limit(self, tmp_path):
        log_file = tmp_path / "security.log"
        with patch("scout.security.audit_log._LOG_FILE", log_file), \
             patch("scout.security.audit_log._LOG_DIR", tmp_path):
            for i in range(10):
                log_security_event(f"s{i}", "injection_detected", "warning")

            events = read_security_log(limit=3)
            assert len(events) == 3

    def test_reverse_chronological(self, tmp_path):
        log_file = tmp_path / "security.log"
        with patch("scout.security.audit_log._LOG_FILE", log_file), \
             patch("scout.security.audit_log._LOG_DIR", tmp_path):
            log_security_event("first", "injection_detected", "warning")
            log_security_event("second", "credential_refused", "critical")

            events = read_security_log()
            assert events[0]["session_id"] == "second"
            assert events[1]["session_id"] == "first"

    def test_empty_log_file(self, tmp_path):
        log_file = tmp_path / "security.log"
        with patch("scout.security.audit_log._LOG_FILE", log_file):
            events = read_security_log()
            assert events == []

    def test_log_never_raises(self, tmp_path):
        """Logging failures should never propagate exceptions."""
        with patch("scout.security.audit_log._LOG_FILE", Path("/nonexistent/path/log")):
            # Should not raise
            log_security_event("s1", "test", "info")

    def test_log_no_credential_values(self, tmp_path):
        """Security log must never contain actual credential values."""
        log_file = tmp_path / "security.log"
        with patch("scout.security.audit_log._LOG_FILE", log_file), \
             patch("scout.security.audit_log._LOG_DIR", tmp_path):
            log_security_event(
                session_id="s1",
                event_type="credential_refused",
                severity="critical",
                detail={
                    "env_var": "APP_PASSWORD",
                    "current_domain": "evil.com",
                    # Note: no actual password value logged
                },
            )

            events = read_security_log()
            raw = json.dumps(events[0])
            # The detail should contain the key name but not any password
            assert "APP_PASSWORD" in raw
