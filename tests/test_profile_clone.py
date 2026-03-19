"""Tests for Chrome profile cloning."""

import json
import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scout.models import SessionInfo
from scout.session import BrowserSession


class TestSessionInfoCloneFields:
    """Verify SessionInfo includes clone fields."""

    def test_profile_cloned_defaults_to_false(self):
        info = SessionInfo(session_id="abc123")
        assert info.profile_cloned is False

    def test_clone_warnings_defaults_to_none(self):
        info = SessionInfo(session_id="abc123")
        assert info.clone_warnings is None

    def test_profile_cloned_true_appears_in_dump(self):
        info = SessionInfo(session_id="abc123", profile_cloned=True)
        dumped = info.model_dump(exclude_none=True)
        assert dumped["profile_cloned"] is True

    def test_clone_warnings_none_excluded_from_dump(self):
        info = SessionInfo(session_id="abc123")
        dumped = info.model_dump(exclude_none=True)
        assert "clone_warnings" not in dumped

    def test_clone_warnings_list_appears_in_dump(self):
        info = SessionInfo(
            session_id="abc123",
            clone_warnings=["Could not copy Login Data"],
        )
        dumped = info.model_dump(exclude_none=True)
        assert dumped["clone_warnings"] == ["Could not copy Login Data"]
