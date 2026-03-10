"""Tests for input validation utilities."""

import pytest

from scout.validation import validate_directory_path, validate_regex_pattern, validate_url


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
