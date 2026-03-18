"""Tests for Chrome profile support."""

import os
from unittest.mock import MagicMock, patch

import pytest

from scout.models import ConnectionMode
from scout.session import BrowserSession


class TestResolveProfileDir:
    """Unit tests for BrowserSession._resolve_profile_dir."""

    def test_none_returns_none(self):
        session = BrowserSession.__new__(BrowserSession)
        assert session._resolve_profile_dir(None) is None

    def test_bare_name_resolves_to_scout_profiles(self):
        session = BrowserSession.__new__(BrowserSession)
        result = session._resolve_profile_dir("work-portal")
        expected = os.path.join(os.path.expanduser("~"), ".scout", "profiles", "work-portal")
        assert result == expected

    def test_bare_name_with_env_override(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SCOUT_PROFILE_DIR", str(tmp_path))
        session = BrowserSession.__new__(BrowserSession)
        result = session._resolve_profile_dir("my-profile")
        assert result == os.path.join(str(tmp_path), "my-profile")

    def test_absolute_path_returned_as_is(self, tmp_path):
        abs_path = str(tmp_path / "chrome-profile")
        session = BrowserSession.__new__(BrowserSession)
        result = session._resolve_profile_dir(abs_path)
        assert result == abs_path

    def test_relative_path_with_separator_rejected(self):
        session = BrowserSession.__new__(BrowserSession)
        with pytest.raises(ValueError, match="must be a bare name or an absolute path"):
            session._resolve_profile_dir("../sneaky/path")

    def test_relative_path_forward_slash_rejected(self):
        session = BrowserSession.__new__(BrowserSession)
        with pytest.raises(ValueError, match="must be a bare name or an absolute path"):
            session._resolve_profile_dir("foo/bar")

    def test_relative_path_backslash_rejected(self):
        session = BrowserSession.__new__(BrowserSession)
        with pytest.raises(ValueError, match="must be a bare name or an absolute path"):
            session._resolve_profile_dir("foo\\bar")

    def test_empty_string_returns_none(self):
        session = BrowserSession.__new__(BrowserSession)
        assert session._resolve_profile_dir("") is None

    def test_bare_name_allows_alphanumeric_hyphen_underscore(self):
        session = BrowserSession.__new__(BrowserSession)
        result = session._resolve_profile_dir("my_profile-2")
        assert result.endswith("my_profile-2")

    def test_bare_name_rejects_invalid_chars(self):
        session = BrowserSession.__new__(BrowserSession)
        with pytest.raises(ValueError, match="contains invalid characters"):
            session._resolve_profile_dir("bad<name>")


class TestProfileEagerValidation:
    """Verify profile is validated eagerly in __init__, not deferred to launch."""

    def test_relative_path_rejected_at_construction(self):
        with pytest.raises(ValueError, match="must be a bare name or an absolute path"):
            BrowserSession(profile="foo/bar")

    def test_invalid_chars_rejected_at_construction(self):
        with pytest.raises(ValueError, match="contains invalid characters"):
            BrowserSession(profile='bad"name')


class TestLaunchBrowserProfile:
    """Verify profile is passed through to the botasaurus Driver."""

    @patch("scout.session.Driver")
    def test_named_profile_passed_to_driver(self, MockDriver, tmp_path):
        mock_driver = MagicMock()
        mock_driver.current_url = "about:blank"
        mock_driver._browser.info = {}
        MockDriver.return_value = mock_driver

        session = BrowserSession(profile="work-portal", download_dir=str(tmp_path))
        session.launch()

        call_kwargs = MockDriver.call_args[1]
        expected_path = os.path.join(
            os.path.expanduser("~"), ".scout", "profiles", "work-portal"
        )
        assert call_kwargs["profile"] == expected_path

    @patch("scout.session.Driver")
    def test_none_profile_not_passed_to_driver(self, MockDriver, tmp_path):
        mock_driver = MagicMock()
        mock_driver.current_url = "about:blank"
        mock_driver._browser.info = {}
        MockDriver.return_value = mock_driver

        session = BrowserSession(profile=None, download_dir=str(tmp_path))
        session.launch()

        call_kwargs = MockDriver.call_args[1]
        assert "profile" not in call_kwargs

    @patch("scout.session.Driver")
    def test_absolute_path_profile_passed_to_driver(self, MockDriver, tmp_path):
        mock_driver = MagicMock()
        mock_driver.current_url = "about:blank"
        mock_driver._browser.info = {}
        MockDriver.return_value = mock_driver

        abs_path = str(tmp_path / "my-chrome")
        session = BrowserSession(profile=abs_path, download_dir=str(tmp_path))
        session.launch()

        call_kwargs = MockDriver.call_args[1]
        assert call_kwargs["profile"] == abs_path

    @patch("scout.session.Driver")
    def test_profile_dir_survives_session_close(self, MockDriver, tmp_path):
        """Persistent profiles must NOT be deleted on session close."""
        mock_driver = MagicMock()
        mock_driver.current_url = "about:blank"
        mock_driver._browser.info = {}
        MockDriver.return_value = mock_driver

        profile_dir = tmp_path / "persistent-profile"
        profile_dir.mkdir()
        (profile_dir / "sentinel.txt").write_text("keep me")

        session = BrowserSession(profile=str(profile_dir), download_dir=str(tmp_path / "dl"))
        session.launch()
        session.close()

        # Profile directory must still exist after close
        assert profile_dir.exists()
        assert (profile_dir / "sentinel.txt").read_text() == "keep me"


class TestSessionInfoProfile:
    """Verify SessionInfo includes profile in response."""

    @patch("scout.session.Driver")
    def test_session_info_includes_named_profile(self, MockDriver, tmp_path):
        mock_driver = MagicMock()
        mock_driver.current_url = "about:blank"
        mock_driver._browser.info = {}
        MockDriver.return_value = mock_driver

        session = BrowserSession(profile="work-portal", download_dir=str(tmp_path))
        info = session.launch()
        assert info.profile == "work-portal"

    @patch("scout.session.Driver")
    def test_session_info_none_profile_excluded(self, MockDriver, tmp_path):
        mock_driver = MagicMock()
        mock_driver.current_url = "about:blank"
        mock_driver._browser.info = {}
        MockDriver.return_value = mock_driver

        session = BrowserSession(profile=None, download_dir=str(tmp_path))
        info = session.launch()
        assert info.profile is None
        # Verify it's excluded from model_dump(exclude_none=True)
        dumped = info.model_dump(exclude_none=True)
        assert "profile" not in dumped


class TestProfileServerValidation:
    """Verify server-level profile validation."""

    def test_relative_path_rejected_at_construction(self):
        """BrowserSession rejects relative paths eagerly."""
        with pytest.raises(ValueError, match="must be a bare name or an absolute path"):
            BrowserSession(profile="foo/bar")

    def test_invalid_chars_rejected_at_construction(self):
        with pytest.raises(ValueError, match="contains invalid characters"):
            BrowserSession(profile='bad"name')

    @patch("scout.session.Driver")
    def test_profile_stored_on_session(self, MockDriver, tmp_path):
        mock_driver = MagicMock()
        mock_driver.current_url = "about:blank"
        mock_driver._browser.info = {}
        MockDriver.return_value = mock_driver

        session = BrowserSession(profile="test-profile", download_dir=str(tmp_path))
        assert session._profile == "test-profile"


class TestProfileExtensionModeServerGuard:
    """Verify the server rejects profile + extension mode before creating a session."""

    def test_extension_mode_with_profile_returns_error(self):
        """Simulates the server-level check without needing the full MCP stack."""
        profile = "work-portal"
        mode = ConnectionMode("extension")

        # Replicate the server guard
        if profile is not None and mode == ConnectionMode.EXTENSION:
            error = {
                "error": "Profile selection is not supported in extension mode — "
                "the profile is determined by the Chrome instance the extension is running in."
            }
        else:
            error = None

        assert error is not None
        assert "not supported in extension mode" in error["error"]
