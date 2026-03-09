"""Tests for macOS LaunchAgents scheduler backend."""

from __future__ import annotations

import plistlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scout.scheduler import ScheduleInfo
from scout.scheduler.macos import MacOSScheduler


class TestMacOSPlatformName:
    def test_platform_name(self):
        scheduler = MacOSScheduler()
        assert scheduler.platform_name == "macOS"


class TestGenerateRunScript:
    """Verify .sh wrapper generation."""

    def test_creates_sh_file(self, tmp_path):
        workflow_dir = tmp_path / "workflows" / "enrollment"
        workflow_dir.mkdir(parents=True)

        scheduler = MacOSScheduler()
        result = scheduler.generate_run_script(str(workflow_dir), "enrollment.py")
        assert result.exists()
        assert result.suffix == ".sh"
        assert result.name == "run.sh"

    def test_sh_content_has_shebang_cd_and_python3(self, tmp_path):
        workflow_dir = tmp_path / "workflows" / "enrollment"
        workflow_dir.mkdir(parents=True)

        scheduler = MacOSScheduler()
        result = scheduler.generate_run_script(str(workflow_dir), "enrollment.py")
        content = result.read_text()

        assert content.startswith("#!/bin/bash\n")
        assert f'cd "{workflow_dir}"' in content
        assert "python3 enrollment.py" in content

    @pytest.mark.skipif(sys.platform == "win32", reason="NTFS ignores chmod")
    def test_sh_file_is_executable(self, tmp_path):
        workflow_dir = tmp_path / "workflows" / "enrollment"
        workflow_dir.mkdir(parents=True)

        scheduler = MacOSScheduler()
        result = scheduler.generate_run_script(str(workflow_dir), "enrollment.py")
        import stat
        assert result.stat().st_mode & stat.S_IXUSR


class TestPlistGeneration:
    """Verify .plist XML generation for launchd."""

    def test_daily_schedule_plist(self, tmp_path):
        scheduler = MacOSScheduler()
        plist_path = scheduler._generate_plist(
            name="enrollment",
            run_script=str(tmp_path / "run.sh"),
            workflow_dir=str(tmp_path),
            schedule="DAILY",
            time="06:45",
            plist_dir=tmp_path,
        )
        assert plist_path.exists()
        assert plist_path.name == "com.scout.enrollment.plist"

        with open(plist_path, "rb") as f:
            plist = plistlib.load(f)

        assert plist["Label"] == "com.scout.enrollment"
        assert str(tmp_path / "run.sh") in plist["ProgramArguments"]
        assert plist["StartCalendarInterval"]["Hour"] == 6
        assert plist["StartCalendarInterval"]["Minute"] == 45

    def test_weekly_schedule_plist(self, tmp_path):
        scheduler = MacOSScheduler()
        plist_path = scheduler._generate_plist(
            name="report",
            run_script=str(tmp_path / "run.sh"),
            workflow_dir=str(tmp_path),
            schedule="WEEKLY",
            time="08:00",
            days="MON,WED,FRI",
            plist_dir=tmp_path,
        )

        with open(plist_path, "rb") as f:
            plist = plistlib.load(f)

        intervals = plist["StartCalendarInterval"]
        assert isinstance(intervals, list)
        assert len(intervals) == 3
        weekdays = [i["Weekday"] for i in intervals]
        assert 1 in weekdays  # Monday
        assert 3 in weekdays  # Wednesday
        assert 5 in weekdays  # Friday

    def test_weekdays_schedule_plist(self, tmp_path):
        scheduler = MacOSScheduler()
        plist_path = scheduler._generate_plist(
            name="weekday-task",
            run_script=str(tmp_path / "run.sh"),
            workflow_dir=str(tmp_path),
            schedule="WEEKLY",
            time="09:00",
            days="MON,TUE,WED,THU,FRI",
            plist_dir=tmp_path,
        )

        with open(plist_path, "rb") as f:
            plist = plistlib.load(f)

        intervals = plist["StartCalendarInterval"]
        assert len(intervals) == 5

    def test_once_schedule_includes_date_fields(self, tmp_path):
        """ONCE schedule must include Day and Month to avoid firing daily."""
        scheduler = MacOSScheduler()
        plist_path = scheduler._generate_plist(
            name="one-time",
            run_script=str(tmp_path / "run.sh"),
            workflow_dir=str(tmp_path),
            schedule="ONCE",
            time="14:00",
            plist_dir=tmp_path,
        )

        with open(plist_path, "rb") as f:
            plist = plistlib.load(f)

        interval = plist["StartCalendarInterval"]
        assert interval["Hour"] == 14
        assert interval["Minute"] == 0
        # Must have Day and Month to avoid firing daily
        assert "Day" in interval
        assert "Month" in interval

    def test_plist_has_stdout_stderr_paths(self, tmp_path):
        scheduler = MacOSScheduler()
        plist_path = scheduler._generate_plist(
            name="enrollment",
            run_script=str(tmp_path / "run.sh"),
            workflow_dir=str(tmp_path),
            schedule="DAILY",
            time="06:45",
            plist_dir=tmp_path,
        )

        with open(plist_path, "rb") as f:
            plist = plistlib.load(f)

        assert "StandardOutPath" in plist
        assert "StandardErrorPath" in plist
        assert plist["StandardOutPath"].endswith("scout.log")
        assert plist["StandardErrorPath"].endswith("scout.err")


class TestPlistToScheduleInfo:
    """Verify parsing is pure — no subprocess calls."""

    def test_daily_plist_parsing(self):
        scheduler = MacOSScheduler()
        plist = {
            "Label": "com.scout.enrollment",
            "ProgramArguments": ["/path/to/run.sh"],
            "WorkingDirectory": "/path/to",
            "StartCalendarInterval": {"Hour": 6, "Minute": 45},
        }
        info = scheduler._plist_to_schedule_info("enrollment", plist, status="Loaded")
        assert info is not None
        assert info.name == "enrollment"
        assert info.schedule_type == "Daily"
        assert info.start_time == "06:45"
        assert info.status == "Loaded"

    def test_weekly_plist_parsing(self):
        scheduler = MacOSScheduler()
        plist = {
            "Label": "com.scout.report",
            "ProgramArguments": ["/path/to/run.sh"],
            "StartCalendarInterval": [
                {"Weekday": 1, "Hour": 8, "Minute": 0},
                {"Weekday": 3, "Hour": 8, "Minute": 0},
            ],
        }
        info = scheduler._plist_to_schedule_info("report", plist, status="Loaded")
        assert info is not None
        assert info.schedule_type == "Weekly"
        assert "MON" in info.days
        assert "WED" in info.days

    def test_default_status_is_unknown(self):
        scheduler = MacOSScheduler()
        plist = {
            "Label": "com.scout.test",
            "ProgramArguments": ["/path/to/run.sh"],
            "StartCalendarInterval": {"Hour": 8, "Minute": 0},
        }
        info = scheduler._plist_to_schedule_info("test", plist)
        assert info.status == "Unknown"


class TestCreateSchedule:
    @patch("scout.scheduler.macos.subprocess.run")
    def test_create_calls_launchctl_load(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        scheduler = MacOSScheduler()

        with patch.object(scheduler, "_plist_dir", return_value=tmp_path):
            result = scheduler.create(
                name="enrollment",
                run_script=str(tmp_path / "run.sh"),
                schedule="DAILY",
                time="06:45",
            )

        assert result is True
        load_calls = [c for c in mock_run.call_args_list
                      if "load" in str(c)]
        assert len(load_calls) >= 1

    @patch("scout.scheduler.macos.subprocess.run")
    def test_create_returns_false_on_failure(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="ERROR")
        scheduler = MacOSScheduler()

        with patch.object(scheduler, "_plist_dir", return_value=tmp_path):
            result = scheduler.create(
                name="broken",
                run_script=str(tmp_path / "run.sh"),
                schedule="DAILY",
                time="08:00",
            )
        assert result is False


class TestDeleteSchedule:
    @patch("scout.scheduler.macos.subprocess.run")
    def test_delete_calls_launchctl_unload(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        scheduler = MacOSScheduler()
        plist_path = tmp_path / "com.scout.enrollment.plist"
        plist_path.write_text("")

        with patch.object(scheduler, "_plist_dir", return_value=tmp_path):
            result = scheduler.delete("enrollment")

        assert result is True
        unload_calls = [c for c in mock_run.call_args_list
                        if "unload" in str(c)]
        assert len(unload_calls) >= 1

    @patch("scout.scheduler.macos.subprocess.run")
    def test_delete_removes_plist_on_success(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        scheduler = MacOSScheduler()
        plist_path = tmp_path / "com.scout.enrollment.plist"
        plist_path.write_text("")

        with patch.object(scheduler, "_plist_dir", return_value=tmp_path):
            scheduler.delete("enrollment")

        assert not plist_path.exists()

    @patch("scout.scheduler.macos.subprocess.run")
    def test_delete_keeps_plist_on_unload_failure(self, mock_run, tmp_path):
        """Fix for review issue 7: don't delete plist if unload fails."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="ERROR")
        scheduler = MacOSScheduler()
        plist_path = tmp_path / "com.scout.enrollment.plist"
        plist_path.write_text("")

        with patch.object(scheduler, "_plist_dir", return_value=tmp_path):
            result = scheduler.delete("enrollment")

        assert result is False
        assert plist_path.exists()  # plist preserved when unload fails


class TestQuerySchedule:
    def test_query_reads_plist_file(self, tmp_path):
        scheduler = MacOSScheduler()
        plist_data = {
            "Label": "com.scout.enrollment",
            "ProgramArguments": [str(tmp_path / "run.sh")],
            "WorkingDirectory": str(tmp_path),
            "StartCalendarInterval": {"Hour": 6, "Minute": 45},
            "StandardOutPath": str(tmp_path / "scout.log"),
            "StandardErrorPath": str(tmp_path / "scout.err"),
        }
        plist_path = tmp_path / "com.scout.enrollment.plist"
        with open(plist_path, "wb") as f:
            plistlib.dump(plist_data, f)

        with patch.object(scheduler, "_plist_dir", return_value=tmp_path):
            with patch("scout.scheduler.macos.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
                info = scheduler.query("enrollment")

        assert info is not None
        assert info.name == "enrollment"
        assert info.schedule_type == "Daily"
        assert "6:45" in info.start_time or "06:45" in info.start_time

    def test_query_returns_none_when_plist_missing(self, tmp_path):
        scheduler = MacOSScheduler()
        with patch.object(scheduler, "_plist_dir", return_value=tmp_path):
            info = scheduler.query("nonexistent")
        assert info is None


class TestListSchedules:
    def test_lists_all_scout_plists(self, tmp_path):
        scheduler = MacOSScheduler()

        for name, hour in [("enrollment", 6), ("report", 8)]:
            plist_data = {
                "Label": f"com.scout.{name}",
                "ProgramArguments": [str(tmp_path / "run.sh")],
                "WorkingDirectory": str(tmp_path),
                "StartCalendarInterval": {"Hour": hour, "Minute": 0},
                "StandardOutPath": str(tmp_path / "scout.log"),
                "StandardErrorPath": str(tmp_path / "scout.err"),
            }
            plist_path = tmp_path / f"com.scout.{name}.plist"
            with open(plist_path, "wb") as f:
                plistlib.dump(plist_data, f)

        with patch.object(scheduler, "_plist_dir", return_value=tmp_path):
            with patch("scout.scheduler.macos.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
                tasks = scheduler.list_all()

        assert len(tasks) == 2
        names = [t.name for t in tasks]
        assert "enrollment" in names
        assert "report" in names

    def test_returns_empty_when_no_plists(self, tmp_path):
        scheduler = MacOSScheduler()
        with patch.object(scheduler, "_plist_dir", return_value=tmp_path):
            tasks = scheduler.list_all()
        assert tasks == []
