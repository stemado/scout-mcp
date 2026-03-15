"""Tests for Native Messaging host registration."""

import json
import os
import platform
import sys
from unittest.mock import MagicMock, patch

import pytest

from scout.native_messaging import (
    DEFAULT_EXTENSION_ID,
    ensure_native_messaging_host,
    NM_HOST_NAME,
)


@pytest.fixture(autouse=True)
def _mock_winreg(monkeypatch):
    """Prevent tests from writing to the real Windows registry.

    Without this, ensure_native_messaging_host() calls winreg.CreateKey()
    on Windows, polluting HKCU with test data (stale paths, fake extension IDs).
    """
    if platform.system() != "Windows":
        yield
        return

    fake_key = MagicMock()
    fake_key.__enter__ = MagicMock(return_value=fake_key)
    fake_key.__exit__ = MagicMock(return_value=False)

    monkeypatch.setattr("winreg.CreateKey", MagicMock(return_value=fake_key))
    monkeypatch.setattr("winreg.SetValueEx", MagicMock())
    yield


class TestDefaultExtensionId:
    def test_uses_default_when_env_not_set(self, tmp_path, monkeypatch):
        monkeypatch.delenv("SCOUT_EXTENSION_ID", raising=False)
        monkeypatch.setattr(
            "scout.native_messaging._scout_data_dir", lambda: str(tmp_path / ".scout")
        )
        monkeypatch.setattr(
            "scout.native_messaging._nm_manifest_dir", lambda: str(tmp_path / "nm")
        )

        result = ensure_native_messaging_host()
        assert result is True

        manifest_path = tmp_path / "nm" / f"{NM_HOST_NAME}.json"
        manifest = json.loads(manifest_path.read_text())
        assert f"chrome-extension://{DEFAULT_EXTENSION_ID}/" in manifest["allowed_origins"]

    def test_env_overrides_default(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SCOUT_EXTENSION_ID", "custom_id_override")
        monkeypatch.setattr(
            "scout.native_messaging._scout_data_dir", lambda: str(tmp_path / ".scout")
        )
        monkeypatch.setattr(
            "scout.native_messaging._nm_manifest_dir", lambda: str(tmp_path / "nm")
        )

        ensure_native_messaging_host()

        manifest_path = tmp_path / "nm" / f"{NM_HOST_NAME}.json"
        manifest = json.loads(manifest_path.read_text())
        assert "chrome-extension://custom_id_override/" in manifest["allowed_origins"]


class TestRegistrationWritesFiles:
    def test_writes_nm_host_script(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SCOUT_EXTENSION_ID", "abcdef1234567890")
        monkeypatch.setattr(
            "scout.native_messaging._scout_data_dir", lambda: str(tmp_path / ".scout")
        )
        monkeypatch.setattr(
            "scout.native_messaging._nm_manifest_dir", lambda: str(tmp_path / "nm")
        )

        result = ensure_native_messaging_host()
        assert result is True

        nm_dir = tmp_path / ".scout" / "native-messaging"
        assert (nm_dir / "scout_nm_host.py").exists()

        if platform.system() == "Windows":
            bat_file = nm_dir / "scout_nm_host.bat"
            assert bat_file.exists()
            content = bat_file.read_text()
            assert sys.executable in content

    def test_writes_manifest_with_extension_id(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SCOUT_EXTENSION_ID", "testextensionid123")
        monkeypatch.setattr(
            "scout.native_messaging._scout_data_dir", lambda: str(tmp_path / ".scout")
        )
        monkeypatch.setattr(
            "scout.native_messaging._nm_manifest_dir", lambda: str(tmp_path / "nm")
        )

        ensure_native_messaging_host()

        manifest_path = tmp_path / "nm" / f"{NM_HOST_NAME}.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text())
        assert manifest["name"] == NM_HOST_NAME
        assert manifest["type"] == "stdio"
        assert "chrome-extension://testextensionid123/" in manifest["allowed_origins"]

    def test_manifest_path_is_absolute(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SCOUT_EXTENSION_ID", "abc123")
        monkeypatch.setattr(
            "scout.native_messaging._scout_data_dir", lambda: str(tmp_path / ".scout")
        )
        monkeypatch.setattr(
            "scout.native_messaging._nm_manifest_dir", lambda: str(tmp_path / "nm")
        )

        ensure_native_messaging_host()

        manifest_path = tmp_path / "nm" / f"{NM_HOST_NAME}.json"
        manifest = json.loads(manifest_path.read_text())
        assert os.path.isabs(manifest["path"])


class TestCustomNMPath:
    def test_uses_scout_chrome_nm_path_env(self, tmp_path, monkeypatch):
        custom_dir = tmp_path / "custom-nm"
        monkeypatch.setenv("SCOUT_EXTENSION_ID", "abc123")
        monkeypatch.setenv("SCOUT_CHROME_NM_PATH", str(custom_dir))
        monkeypatch.setattr(
            "scout.native_messaging._scout_data_dir", lambda: str(tmp_path / ".scout")
        )

        ensure_native_messaging_host()

        manifest_path = custom_dir / f"{NM_HOST_NAME}.json"
        assert manifest_path.exists()


class TestWindowsRegistryIntegration:
    @pytest.mark.skipif(platform.system() != "Windows", reason="Windows-only")
    def test_creates_registry_key_with_manifest_path(self, tmp_path, monkeypatch):
        """Verify winreg.CreateKey and SetValueEx are called with correct args."""
        import winreg

        monkeypatch.setenv("SCOUT_EXTENSION_ID", "ext123")
        monkeypatch.setattr(
            "scout.native_messaging._scout_data_dir", lambda: str(tmp_path / ".scout")
        )
        monkeypatch.setattr(
            "scout.native_messaging._nm_manifest_dir", lambda: str(tmp_path / "nm")
        )

        ensure_native_messaging_host()

        expected_key = f"Software\\Google\\Chrome\\NativeMessagingHosts\\{NM_HOST_NAME}"
        expected_path = str(tmp_path / "nm" / f"{NM_HOST_NAME}.json")

        winreg.CreateKey.assert_called_once_with(
            winreg.HKEY_CURRENT_USER, expected_key
        )
        winreg.SetValueEx.assert_called_once_with(
            winreg.CreateKey.return_value.__enter__.return_value,
            "", 0, winreg.REG_SZ, expected_path,
        )
