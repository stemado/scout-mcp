"""Tests for input validation utilities."""

import os

import pytest

from scout.validation import (
    validate_directory_path,
    validate_file_path,
    validate_regex_pattern,
    validate_url,
)


# --- URL validation ---


class TestValidateUrl:
    def test_blocks_file_scheme(self):
        with pytest.raises(ValueError, match="Only http and https"):
            validate_url("file:///etc/passwd")

    def test_blocks_chrome_scheme(self):
        with pytest.raises(ValueError, match="Only http and https"):
            validate_url("chrome://settings")

    def test_blocks_javascript_scheme(self):
        with pytest.raises(ValueError, match="Only http and https"):
            validate_url("javascript:alert(1)")

    def test_blocks_data_scheme(self):
        with pytest.raises(ValueError, match="Only http and https"):
            validate_url("data:text/html,<h1>hi</h1>")

    def test_blocks_cloud_metadata(self):
        with pytest.raises(ValueError, match="Blocked URL host"):
            validate_url("http://169.254.169.254/latest/meta-data/")

    def test_blocks_link_local_range(self):
        with pytest.raises(ValueError, match="Blocked URL host"):
            validate_url("http://169.254.42.42/some/path")

    def test_blocks_localhost(self):
        with pytest.raises(ValueError, match="Blocked URL host"):
            validate_url("http://127.0.0.1:9222/json")

    def test_blocks_localhost_name(self):
        with pytest.raises(ValueError, match="Blocked URL host"):
            validate_url("http://localhost:8080/admin")

    def test_blocks_ftp_scheme(self):
        with pytest.raises(ValueError, match="Only http and https"):
            validate_url("ftp://example.com/file")

    def test_blocks_gopher_scheme(self):
        with pytest.raises(ValueError, match="Only http and https"):
            validate_url("gopher://example.com")

    def test_blocks_ipv6_mapped_metadata(self):
        with pytest.raises(ValueError, match="Blocked URL host"):
            validate_url("http://[::ffff:169.254.169.254]/latest/meta-data/")

    def test_blocks_ipv6_mapped_loopback(self):
        with pytest.raises(ValueError, match="Blocked URL host"):
            validate_url("http://[::ffff:127.0.0.1]:8080/admin")

    def test_blocks_ipv6_loopback(self):
        with pytest.raises(ValueError, match="Blocked URL host"):
            validate_url("http://[::1]:8080/admin")

    def test_allows_http(self):
        validate_url("http://example.com")

    def test_allows_https(self):
        validate_url("https://example.com/path?q=1")

    def test_allows_empty(self):
        validate_url("")

    def test_allows_none_equivalent(self):
        validate_url("")


class TestValidateUrlLocalhostPort:
    """Port-scoped localhost access via allow_localhost_port parameter."""

    def test_allows_localhost_on_matching_port(self):
        validate_url("http://localhost:3000/app", allow_localhost_port=3000)

    def test_blocks_localhost_on_different_port(self):
        with pytest.raises(ValueError, match="Blocked URL host"):
            validate_url("http://localhost:6379", allow_localhost_port=3000)

    def test_blocks_localhost_with_no_parameter(self):
        with pytest.raises(ValueError, match="Blocked URL host"):
            validate_url("http://localhost:3000")

    def test_allows_127001_on_matching_port(self):
        validate_url("http://127.0.0.1:3000/path", allow_localhost_port=3000)

    def test_blocks_127001_on_different_port(self):
        with pytest.raises(ValueError, match="Blocked URL host"):
            validate_url("http://127.0.0.1:9200", allow_localhost_port=3000)

    def test_allows_ipv6_loopback_on_matching_port(self):
        validate_url("http://[::1]:3000/", allow_localhost_port=3000)

    def test_blocks_ipv6_loopback_on_different_port(self):
        with pytest.raises(ValueError, match="Blocked URL host"):
            validate_url("http://[::1]:6379", allow_localhost_port=3000)

    def test_allows_implicit_port_80_for_http(self):
        validate_url("http://localhost", allow_localhost_port=80)

    def test_allows_implicit_port_443_for_https(self):
        validate_url("https://localhost", allow_localhost_port=443)

    def test_allows_explicit_port_80_for_http(self):
        validate_url("http://localhost:80/path", allow_localhost_port=80)

    def test_blocks_implicit_port_when_different(self):
        with pytest.raises(ValueError, match="Blocked URL host"):
            validate_url("http://localhost", allow_localhost_port=3000)

    def test_env_var_overrides_port_restriction(self, monkeypatch):
        monkeypatch.setenv("SCOUT_ALLOW_LOCALHOST", "1")
        # allow_localhost=True (from env var) should permit any port
        validate_url("http://localhost:6379", allow_localhost=True, allow_localhost_port=3000)

    def test_cloud_metadata_blocked_with_any_flags(self):
        with pytest.raises(ValueError, match="Blocked URL host"):
            validate_url("http://169.254.169.254/latest/meta-data/", allow_localhost_port=80)

    def test_rejects_port_zero(self):
        with pytest.raises(ValueError, match="allow_localhost_port must be 1-65535"):
            validate_url("http://localhost:3000", allow_localhost_port=0)

    def test_rejects_negative_port(self):
        with pytest.raises(ValueError, match="allow_localhost_port must be 1-65535"):
            validate_url("http://localhost:3000", allow_localhost_port=-1)

    def test_rejects_port_above_65535(self):
        with pytest.raises(ValueError, match="allow_localhost_port must be 1-65535"):
            validate_url("http://localhost:3000", allow_localhost_port=70000)

    def test_non_localhost_url_unaffected(self):
        validate_url("http://example.com:3000", allow_localhost_port=3000)

    def test_non_localhost_url_still_works_without_port(self):
        validate_url("http://example.com")

    def test_allows_ipv6_mapped_ipv4_loopback_on_matching_port(self):
        validate_url("http://[::ffff:127.0.0.1]:3000/", allow_localhost_port=3000)

    def test_blocks_ipv6_mapped_ipv4_loopback_on_different_port(self):
        with pytest.raises(ValueError, match="Blocked URL host"):
            validate_url("http://[::ffff:127.0.0.1]:6379", allow_localhost_port=3000)

    def test_allows_all_ports_with_allow_localhost_true(self):
        validate_url("http://localhost:6379", allow_localhost=True)


# --- Directory path validation ---


class TestValidateDirectoryPath:
    def test_blocks_unix_absolute(self):
        with pytest.raises(ValueError, match="must be a relative path"):
            validate_directory_path("/etc/cron.d")

    def test_blocks_windows_absolute(self):
        with pytest.raises(ValueError, match="must be a relative path"):
            validate_directory_path("C:\\Windows\\Temp")

    def test_blocks_unc_path(self):
        with pytest.raises(ValueError, match="must be a relative path"):
            validate_directory_path("\\\\attacker.com\\share")

    def test_blocks_parent_traversal(self):
        with pytest.raises(ValueError, match="must not traverse"):
            validate_directory_path("../../sensitive")

    def test_blocks_deep_parent_traversal(self):
        with pytest.raises(ValueError, match="must not traverse"):
            validate_directory_path("../../../etc")

    def test_allows_relative(self):
        validate_directory_path("./downloads")

    def test_allows_simple_name(self):
        validate_directory_path("downloads")

    def test_allows_nested_relative(self):
        validate_directory_path("output/session-1/downloads")

    def test_allows_empty(self):
        validate_directory_path("")


# --- Regex pattern validation ---


class TestValidateRegexPattern:
    def test_blocks_long_pattern(self):
        with pytest.raises(ValueError, match="too long"):
            validate_regex_pattern("a" * 501)

    def test_blocks_invalid_regex(self):
        with pytest.raises(ValueError, match="Invalid regex"):
            validate_regex_pattern("[invalid")

    def test_allows_simple_pattern(self):
        result = validate_regex_pattern(r"/api/.*\.json")
        assert result is not None

    def test_returns_compiled_pattern(self):
        result = validate_regex_pattern(r"test\d+")
        assert result.search("test123") is not None

    def test_allows_max_length(self):
        result = validate_regex_pattern("a" * 500)
        assert result is not None


# --- File path validation ---


class TestValidateFilePath:
    def test_accepts_existing_file(self, tmp_path):
        f = tmp_path / "test.pdf"
        f.write_text("fake pdf")
        validate_file_path(str(f))  # should not raise

    def test_rejects_nonexistent_file(self):
        with pytest.raises(ValueError, match="File not found"):
            validate_file_path("/nonexistent/path/file.txt")

    def test_rejects_directory(self, tmp_path):
        with pytest.raises(ValueError, match="not a regular file"):
            validate_file_path(str(tmp_path))

    def test_rejects_empty_path(self):
        with pytest.raises(ValueError, match="File path required"):
            validate_file_path("")

    def test_rejects_none_path(self):
        with pytest.raises(ValueError, match="File path required"):
            validate_file_path(None)


class TestExecuteActionNavigateLocalhostPort:
    """Verify execute_action threads allow_localhost_port to validate_url for navigate.

    These tests unset SCOUT_ALLOW_LOCALHOST (set by conftest) so the
    port-scoped localhost logic is actually exercised.
    """

    def test_navigate_blocks_localhost_without_port(self):
        """Navigate to localhost is blocked when allow_localhost_port is None."""
        from unittest.mock import MagicMock, patch
        from scout.actions import execute_action

        driver = MagicMock()
        driver.current_url = "about:blank"
        with patch.dict(os.environ, {"SCOUT_ALLOW_LOCALHOST": ""}):
            result, _record = execute_action(driver, "navigate", value="http://localhost:3000")
        assert not result.success
        assert "Blocked URL host" in result.error

    def test_navigate_allows_localhost_with_matching_port(self):
        """Navigate to localhost succeeds when allow_localhost_port matches."""
        from unittest.mock import MagicMock, patch
        from scout.actions import execute_action

        driver = MagicMock()
        driver.current_url = "http://localhost:3000"
        with patch.dict(os.environ, {"SCOUT_ALLOW_LOCALHOST": ""}):
            result, _record = execute_action(
                driver, "navigate", value="http://localhost:3000", allow_localhost_port=3000
            )
        assert result.success
        driver.get.assert_called_once_with("http://localhost:3000")

    def test_navigate_blocks_localhost_with_wrong_port(self):
        """Navigate to localhost:6379 is blocked when allow_localhost_port=3000."""
        from unittest.mock import MagicMock, patch
        from scout.actions import execute_action

        driver = MagicMock()
        driver.current_url = "about:blank"
        with patch.dict(os.environ, {"SCOUT_ALLOW_LOCALHOST": ""}):
            result, _record = execute_action(
                driver, "navigate", value="http://localhost:6379", allow_localhost_port=3000
            )
        assert not result.success
        assert "Blocked URL host" in result.error
