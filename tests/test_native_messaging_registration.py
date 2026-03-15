"""Tests for Native Messaging host registration."""

import json
import os
import platform
import sys
from unittest.mock import patch

import pytest

from scout.native_messaging import ensure_native_messaging_host, NM_HOST_NAME


class TestRegistrationSkipsWithoutExtensionId:
    def test_skips_when_no_extension_id(self, tmp_path, monkeypatch):
        monkeypatch.delenv("SCOUT_EXTENSION_ID", raising=False)
        result = ensure_native_messaging_host()
        assert result is False


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
