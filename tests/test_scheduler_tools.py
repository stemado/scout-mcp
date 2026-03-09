"""Tests for MCP scheduling tools in server.py."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scout.scheduler import ScheduleInfo


def _run(coro):
    """Run an async coroutine synchronously for testing."""
    return asyncio.run(coro)


def _make_ctx():
    """Create a mock MCP context with async info method."""
    ctx = MagicMock()
    ctx.info = AsyncMock()
    return ctx


def _make_schedule_info(**overrides):
    """Create a ScheduleInfo with sensible defaults."""
    defaults = {
        "name": "enrollment",
        "task_name": "SCOUT/enrollment",
        "status": "Ready",
        "schedule_type": "Daily",
        "start_time": "06:45",
        "next_run": "2026-03-01 06:45",
        "task_to_run": "/path/to/run.sh",
        "days": "",
    }
    defaults.update(overrides)
    return ScheduleInfo(**defaults)


class TestScheduleCreate:
    def test_rejects_invalid_schedule(self):
        from scout.server import schedule_create

        ctx = _make_ctx()
        result = _run(schedule_create(
            name="test",
            workflow_dir="/some/path",
            schedule="BIWEEKLY",
            time="08:00",
            ctx=ctx,
        ))
        assert "error" in result
        assert "BIWEEKLY" in result["error"]

    def test_normalizes_schedule_to_uppercase(self, tmp_path):
        from scout.server import schedule_create

        workflow_dir = tmp_path / "enrollment"
        workflow_dir.mkdir()
        (workflow_dir / "enrollment.py").write_text("print('hi')")

        ctx = _make_ctx()
        mock_scheduler = MagicMock()
        mock_scheduler.platform_name = "Windows"
        mock_scheduler.generate_run_script.return_value = tmp_path / "run.bat"
        mock_scheduler.create.return_value = True
        mock_scheduler.query.return_value = _make_schedule_info()

        with patch("scout.server.get_scheduler", return_value=mock_scheduler):
            result = _run(schedule_create(
                name="enrollment",
                workflow_dir=str(workflow_dir),
                schedule="daily",  # lowercase
                time="06:45",
                ctx=ctx,
            ))

        assert result.get("success") is True
        # Verify scheduler.create was called with uppercase
        mock_scheduler.create.assert_called_once()
        call_args = mock_scheduler.create.call_args
        assert call_args[0][2] == "DAILY"

    def test_returns_error_when_workflow_missing(self, tmp_path):
        from scout.server import schedule_create

        ctx = _make_ctx()
        mock_scheduler = MagicMock()
        mock_scheduler.platform_name = "Windows"

        with patch("scout.server.get_scheduler", return_value=mock_scheduler):
            result = _run(schedule_create(
                name="nonexistent",
                workflow_dir=str(tmp_path / "nonexistent"),
                schedule="DAILY",
                time="08:00",
                ctx=ctx,
            ))

        assert "error" in result
        assert "No exported workflow" in result["error"]

    def test_returns_error_on_unsupported_platform(self):
        from scout.scheduler.base import UnsupportedPlatformError
        from scout.server import schedule_create

        ctx = _make_ctx()

        with patch("scout.server.get_scheduler", side_effect=UnsupportedPlatformError("freebsd")):
            result = _run(schedule_create(
                name="test",
                workflow_dir="/some/path",
                schedule="DAILY",
                time="08:00",
                ctx=ctx,
            ))

        assert "error" in result
        assert "freebsd" in result["error"]

    def test_success_returns_schedule_info(self, tmp_path):
        from scout.server import schedule_create

        workflow_dir = tmp_path / "enrollment"
        workflow_dir.mkdir()
        (workflow_dir / "enrollment.py").write_text("print('hi')")

        ctx = _make_ctx()
        mock_scheduler = MagicMock()
        mock_scheduler.platform_name = "Windows"
        mock_scheduler.generate_run_script.return_value = tmp_path / "run.bat"
        mock_scheduler.create.return_value = True
        info = _make_schedule_info()
        mock_scheduler.query.return_value = info

        with patch("scout.server.get_scheduler", return_value=mock_scheduler):
            result = _run(schedule_create(
                name="enrollment",
                workflow_dir=str(workflow_dir),
                schedule="DAILY",
                time="06:45",
                ctx=ctx,
            ))

        assert result["success"] is True
        assert result["platform"] == "Windows"
        assert result["schedule"]["name"] == "enrollment"


class TestScheduleList:
    def test_returns_task_list(self):
        from scout.server import schedule_list

        ctx = _make_ctx()
        mock_scheduler = MagicMock()
        mock_scheduler.platform_name = "Linux"
        mock_scheduler.list_all.return_value = [
            _make_schedule_info(name="enrollment"),
            _make_schedule_info(name="report", schedule_type="Weekly"),
        ]

        with patch("scout.server.get_scheduler", return_value=mock_scheduler):
            result = _run(schedule_list(ctx=ctx))

        assert result["count"] == 2
        assert result["platform"] == "Linux"
        assert len(result["tasks"]) == 2

    def test_returns_empty_when_no_tasks(self):
        from scout.server import schedule_list

        ctx = _make_ctx()
        mock_scheduler = MagicMock()
        mock_scheduler.platform_name = "macOS"
        mock_scheduler.list_all.return_value = []

        with patch("scout.server.get_scheduler", return_value=mock_scheduler):
            result = _run(schedule_list(ctx=ctx))

        assert result["count"] == 0
        assert result["tasks"] == []


class TestScheduleDelete:
    def test_successful_delete(self):
        from scout.server import schedule_delete

        ctx = _make_ctx()
        mock_scheduler = MagicMock()
        mock_scheduler.platform_name = "Windows"
        mock_scheduler.delete.return_value = True

        with patch("scout.server.get_scheduler", return_value=mock_scheduler):
            result = _run(schedule_delete(name="enrollment", ctx=ctx))

        assert result["success"] is True

    def test_delete_nonexistent_returns_error(self):
        from scout.server import schedule_delete

        ctx = _make_ctx()
        mock_scheduler = MagicMock()
        mock_scheduler.platform_name = "Windows"
        mock_scheduler.delete.return_value = False

        with patch("scout.server.get_scheduler", return_value=mock_scheduler):
            result = _run(schedule_delete(name="nonexistent", ctx=ctx))

        assert "error" in result
        assert "nonexistent" in result["error"]
