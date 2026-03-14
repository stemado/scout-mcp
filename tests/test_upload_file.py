"""Unit tests for upload_file action (no browser required)."""

from unittest.mock import MagicMock

from scout.actions import execute_action


class TestUploadFileAction:
    """Tests for the upload_file action branch."""

    def test_upload_file_calls_target_upload(self, tmp_path):
        """upload_file calls target.upload_file(selector, resolved_path)."""
        test_file = tmp_path / "report.pdf"
        test_file.write_text("fake pdf content")

        driver = MagicMock()
        driver.current_url = "http://example.com"

        result, record = execute_action(
            driver, "upload_file", selector="input[type=file]",
            value=str(test_file), wait_after=0,
        )

        assert result.success is True
        assert "report.pdf" in result.action_performed
        assert record.action == "upload_file"
        driver.upload_file.assert_called_once_with(
            "input[type=file]", str(test_file.resolve()),
        )

    def test_upload_file_requires_selector(self):
        """upload_file without a selector returns error."""
        driver = MagicMock()
        driver.current_url = "http://example.com"

        result, record = execute_action(
            driver, "upload_file", selector=None,
            value="/some/file.pdf", wait_after=0,
        )

        assert result.success is False
        assert "selector required" in result.error.lower()

    def test_upload_file_requires_value(self):
        """upload_file without a value (file path) returns error."""
        driver = MagicMock()
        driver.current_url = "http://example.com"

        result, record = execute_action(
            driver, "upload_file", selector="input[type=file]",
            value=None, wait_after=0,
        )

        assert result.success is False
        assert "file path required" in result.error.lower()

    def test_upload_file_rejects_nonexistent_file(self):
        """upload_file with nonexistent file returns error."""
        driver = MagicMock()
        driver.current_url = "http://example.com"

        result, record = execute_action(
            driver, "upload_file", selector="input[type=file]",
            value="/nonexistent/file.pdf", wait_after=0,
        )

        assert result.success is False
        assert "not found" in result.error.lower()

    def test_upload_file_rejects_directory(self, tmp_path):
        """upload_file with a directory path returns error."""
        driver = MagicMock()
        driver.current_url = "http://example.com"

        result, record = execute_action(
            driver, "upload_file", selector="input[type=file]",
            value=str(tmp_path), wait_after=0,
        )

        assert result.success is False
        assert "not a regular file" in result.error.lower()

    def test_upload_file_does_not_call_driver_before_validation(self):
        """upload_file fails fast on bad path without hitting the browser."""
        driver = MagicMock()
        driver.current_url = "http://example.com"

        result, record = execute_action(
            driver, "upload_file", selector="input[type=file]",
            value="/nonexistent/file.pdf", wait_after=0,
        )

        assert result.success is False
        driver.upload_file.assert_not_called()

    def test_upload_file_handles_driver_error(self, tmp_path):
        """upload_file returns error when target.upload_file raises."""
        test_file = tmp_path / "report.pdf"
        test_file.write_text("content")

        driver = MagicMock()
        driver.current_url = "http://example.com"
        driver.upload_file.side_effect = Exception("Element not found: input[type=file]")

        result, record = execute_action(
            driver, "upload_file", selector="input[type=file]",
            value=str(test_file), wait_after=0,
        )

        assert result.success is False
        assert "Element not found" in result.error
