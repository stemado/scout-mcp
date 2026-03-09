"""Tests for Windows Task Scheduler backend."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from scout.scheduler import ScheduleInfo
from scout.scheduler.windows import WindowsScheduler


class TestWindowsPlatformName:
    def test_platform_name(self):
        scheduler = WindowsScheduler()
        assert scheduler.platform_name == "Windows"


class TestRunSchtasks:
    """Verify the subprocess wrapper sets MSYS_NO_PATHCONV."""

    @patch("scout.scheduler.windows.subprocess.run")
    def test_sets_msys_no_pathconv(self, mock_run):
        """Git Bash mangles /flags without MSYS_NO_PATHCONV=1."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        scheduler = WindowsScheduler()
        scheduler._run_schtasks("/query", "/fo", "LIST")

        call_kwargs = mock_run.call_args
        env = call_kwargs.kwargs.get("env") or call_kwargs[1].get("env", {})
        assert env.get("MSYS_NO_PATHCONV") == "1"

    @patch("scout.scheduler.windows.subprocess.run")
    def test_passes_args_to_schtasks_exe(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        scheduler = WindowsScheduler()
        scheduler._run_schtasks("/create", "/tn", "\\SCOUT\\Test", "/sc", "DAILY")

        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "schtasks.exe"
        assert "/create" in cmd
        assert "\\SCOUT\\Test" in cmd


class TestGenerateRunScript:
    """Verify .bat wrapper generation."""

    def test_creates_bat_file(self, tmp_path):
        workflow_dir = tmp_path / "workflows" / "enrollment"
        workflow_dir.mkdir(parents=True)
        (workflow_dir / "enrollment.py").write_text("print('hello')")

        scheduler = WindowsScheduler()
        result = scheduler.generate_run_script(str(workflow_dir), "enrollment.py")
        assert result.exists()
        assert result.suffix == ".bat"

    def test_bat_content_has_cd_and_run(self, tmp_path):
        workflow_dir = tmp_path / "workflows" / "enrollment"
        workflow_dir.mkdir(parents=True)
        (workflow_dir / "enrollment.py").write_text("print('hello')")

        scheduler = WindowsScheduler()
        result = scheduler.generate_run_script(str(workflow_dir), "enrollment.py")
        content = result.read_text()

        assert "@echo off" in content
        assert f'cd /d "{workflow_dir}"' in content
        assert "enrollment.py" in content


class TestCreateSchedule:
    """Verify schtasks /create command construction."""

    @patch("scout.scheduler.windows.subprocess.run")
    def test_daily_schedule(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="SUCCESS", stderr="")
        scheduler = WindowsScheduler()
        result = scheduler.create(
            name="enrollment",
            run_script=r"D:\workflows\enrollment\run.bat",
            schedule="DAILY",
            time="06:45",
        )
        assert result is True
        cmd_args = mock_run.call_args[0][0]
        assert "schtasks.exe" in cmd_args[0]
        assert "/create" in cmd_args
        assert "\\SCOUT\\enrollment" in cmd_args
        assert "DAILY" in cmd_args
        assert "06:45" in cmd_args
        assert "/f" in cmd_args

    @patch("scout.scheduler.windows.subprocess.run")
    def test_weekly_schedule_with_days(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="SUCCESS", stderr="")
        scheduler = WindowsScheduler()
        scheduler.create(
            name="report",
            run_script=r"D:\workflows\report\run.bat",
            schedule="WEEKLY",
            time="08:00",
            days="MON,WED,FRI",
        )
        cmd_args = mock_run.call_args[0][0]
        assert "WEEKLY" in cmd_args
        assert "/d" in cmd_args
        assert "MON,WED,FRI" in cmd_args

    @patch("scout.scheduler.windows.subprocess.run")
    def test_returns_false_on_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="ERROR")
        scheduler = WindowsScheduler()
        result = scheduler.create(
            name="broken",
            run_script=r"D:\run.bat",
            schedule="DAILY",
            time="08:00",
        )
        assert result is False


class TestDeleteSchedule:
    @patch("scout.scheduler.windows.subprocess.run")
    def test_delete_uses_force_flag(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="SUCCESS", stderr="")
        scheduler = WindowsScheduler()
        scheduler.delete("enrollment")
        cmd_args = mock_run.call_args[0][0]
        assert "/delete" in cmd_args
        assert "\\SCOUT\\enrollment" in cmd_args
        assert "/f" in cmd_args

    @patch("scout.scheduler.windows.subprocess.run")
    def test_delete_returns_false_on_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="ERROR")
        scheduler = WindowsScheduler()
        assert scheduler.delete("nonexistent") is False


SAMPLE_CSV_OUTPUT = (
    '"SDOHERTY","\\SCOUT\\enrollment","2/28/2026 6:45:00 AM","Ready",'
    '"Interactive only","11/30/1999 12:00:00 AM","267011",'
    '"ANTFARMLLC\\sdoherty",'
    '"D:\\workflows\\enrollment\\run.bat","N/A","N/A","Enabled",'
    '"Disabled","Stop On Battery Mode, No Start On Batteries",'
    '"sdoherty","Disabled","72:00:00",'
    '"Scheduling data is not available in this format.",'
    '"Daily ","6:45:00 AM","2/28/2026","N/A","Every 1 day(s)",'
    '"N/A","Disabled","Disabled","Disabled","Disabled"'
)


class TestQuerySchedule:
    @patch("scout.scheduler.windows.subprocess.run")
    def test_parses_csv_output(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout=SAMPLE_CSV_OUTPUT, stderr=""
        )
        scheduler = WindowsScheduler()
        info = scheduler.query("enrollment")
        assert info is not None
        assert info.name == "enrollment"
        assert info.status == "Ready"
        assert info.schedule_type == "Daily"
        assert "6:45" in info.start_time

    @patch("scout.scheduler.windows.subprocess.run")
    def test_returns_none_on_not_found(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="ERROR")
        scheduler = WindowsScheduler()
        assert scheduler.query("nonexistent") is None


SAMPLE_LIST_CSV = (
    '"SDOHERTY","\\SCOUT\\enrollment","2/28/2026 6:45:00 AM","Ready",'
    '"Interactive only","11/30/1999 12:00:00 AM","267011",'
    '"ANTFARMLLC\\sdoherty",'
    '"D:\\workflows\\enrollment\\run.bat","N/A","N/A","Enabled",'
    '"Disabled","Stop On Battery Mode, No Start On Batteries",'
    '"sdoherty","Disabled","72:00:00",'
    '"Scheduling data is not available in this format.",'
    '"Daily ","6:45:00 AM","2/28/2026","N/A","Every 1 day(s)",'
    '"N/A","Disabled","Disabled","Disabled","Disabled"\n'
    '"SDOHERTY","\\SCOUT\\report","3/1/2026 8:00:00 AM","Ready",'
    '"Interactive only","11/30/1999 12:00:00 AM","267011",'
    '"ANTFARMLLC\\sdoherty",'
    '"D:\\workflows\\report\\run.bat","N/A","N/A","Enabled",'
    '"Disabled","Stop On Battery Mode, No Start On Batteries",'
    '"sdoherty","Disabled","72:00:00",'
    '"Scheduling data is not available in this format.",'
    '"Weekly ","8:00:00 AM","2/28/2026","N/A","MON, WED, FRI",'
    '"N/A","Disabled","Disabled","Disabled","Disabled"'
)


class TestListSchedules:
    @patch("scout.scheduler.windows.subprocess.run")
    def test_lists_all_scout_tasks(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout=SAMPLE_LIST_CSV, stderr=""
        )
        scheduler = WindowsScheduler()
        tasks = scheduler.list_all()
        assert len(tasks) == 2
        assert tasks[0].name == "enrollment"
        assert tasks[1].name == "report"

    @patch("scout.scheduler.windows.subprocess.run")
    def test_returns_empty_on_no_tasks(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="ERROR")
        scheduler = WindowsScheduler()
        assert scheduler.list_all() == []
