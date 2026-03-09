"""macOS LaunchAgents scheduler backend — wraps launchctl + .plist files.

Tasks are stored as LaunchAgent plists at ~/Library/LaunchAgents/com.scout.<name>.plist.
User-level only (no root/sudo required).
"""

from __future__ import annotations

import plistlib
import subprocess
from datetime import date
from pathlib import Path

from .base import BaseScheduler, ScheduleInfo

_LABEL_PREFIX = "com.scout"

# launchd uses 0=Sunday, 1=Monday, ..., 6=Saturday
_DAY_MAP = {
    "SUN": 0, "MON": 1, "TUE": 2, "WED": 3,
    "THU": 4, "FRI": 5, "SAT": 6,
}

_REVERSE_DAY_MAP = {v: k for k, v in _DAY_MAP.items()}


class MacOSScheduler(BaseScheduler):
    """macOS LaunchAgents scheduler backend using launchctl."""

    @property
    def platform_name(self) -> str:
        return "macOS"

    def _plist_dir(self) -> Path:
        """Return the LaunchAgents directory."""
        return Path.home() / "Library" / "LaunchAgents"

    def _plist_path(self, name: str) -> Path:
        """Return the plist file path for a given task name."""
        return self._plist_dir() / f"{_LABEL_PREFIX}.{name}.plist"

    def _label(self, name: str) -> str:
        """Return the launchd label for a given task name."""
        return f"{_LABEL_PREFIX}.{name}"

    def generate_run_script(self, workflow_dir: str, script_name: str) -> Path:
        """Generate a run.sh wrapper."""
        workflow_path = Path(workflow_dir)
        sh_path = workflow_path / "run.sh"
        sh_path.write_text(
            f'#!/bin/bash\ncd "{workflow_path}"\npython3 {script_name}\n',
            encoding="utf-8",
        )
        sh_path.chmod(0o755)
        return sh_path

    def _generate_plist(
        self,
        name: str,
        run_script: str,
        workflow_dir: str,
        schedule: str,
        time: str,
        days: str | None = None,
        plist_dir: Path | None = None,
    ) -> Path:
        """Generate a .plist file for launchd."""
        hour, minute = (int(x) for x in time.split(":"))
        label = self._label(name)

        if schedule == "ONCE":
            # Include Day and Month so it fires once, not daily.
            # Note: launchd has no true one-shot — this fires on the same
            # date every year. Document this limitation.
            today = date.today()
            interval = {
                "Month": today.month,
                "Day": today.day,
                "Hour": hour,
                "Minute": minute,
            }
        elif schedule == "WEEKLY" and days:
            day_list = [d.strip().upper() for d in days.split(",")]
            interval = [
                {"Weekday": _DAY_MAP[d], "Hour": hour, "Minute": minute}
                for d in day_list if d in _DAY_MAP
            ]
        else:
            # DAILY or fallback
            interval = {"Hour": hour, "Minute": minute}

        workflow_path = Path(workflow_dir)
        plist_data = {
            "Label": label,
            "ProgramArguments": [run_script],
            "WorkingDirectory": str(workflow_path),
            "StartCalendarInterval": interval,
            "StandardOutPath": str(workflow_path / "scout.log"),
            "StandardErrorPath": str(workflow_path / "scout.err"),
        }

        target_dir = plist_dir or self._plist_dir()
        target_dir.mkdir(parents=True, exist_ok=True)
        plist_path = target_dir / f"{label}.plist"
        with open(plist_path, "wb") as f:
            plistlib.dump(plist_data, f)

        return plist_path

    def create(
        self,
        name: str,
        run_script: str,
        schedule: str = "DAILY",
        time: str = "08:00",
        days: str | None = None,
    ) -> bool:
        """Create or update a LaunchAgent."""
        plist_dir = self._plist_dir()
        plist_path = self._plist_path(name)

        # Unload existing if present
        if plist_path.exists():
            subprocess.run(
                ["launchctl", "unload", str(plist_path)],
                capture_output=True, text=True,
            )

        # Infer workflow_dir from run_script path
        workflow_dir = str(Path(run_script).parent)

        self._generate_plist(
            name=name,
            run_script=run_script,
            workflow_dir=workflow_dir,
            schedule=schedule,
            time=time,
            days=days,
            plist_dir=plist_dir,
        )

        result = subprocess.run(
            ["launchctl", "load", str(plist_path)],
            capture_output=True, text=True,
        )
        return result.returncode == 0

    def delete(self, name: str) -> bool:
        """Unload and remove a LaunchAgent.

        Only removes the plist file if unload succeeds, to avoid
        inconsistent state where launchd still has the job loaded
        but the plist is gone.
        """
        plist_path = self._plist_path(name)
        if not plist_path.exists():
            return False

        result = subprocess.run(
            ["launchctl", "unload", str(plist_path)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            return False

        plist_path.unlink(missing_ok=True)
        return True

    def _check_loaded(self, name: str) -> str:
        """Check if a launchd job is loaded. Returns status string."""
        result = subprocess.run(
            ["launchctl", "list", self._label(name)],
            capture_output=True, text=True,
        )
        return "Loaded" if result.returncode == 0 else "Unloaded"

    def query(self, name: str) -> ScheduleInfo | None:
        """Query a single scheduled task by reading its plist."""
        plist_path = self._plist_path(name)
        if not plist_path.exists():
            return None

        with open(plist_path, "rb") as f:
            plist = plistlib.load(f)

        status = self._check_loaded(name)
        return self._plist_to_schedule_info(name, plist, status=status)

    def list_all(self) -> list[ScheduleInfo]:
        """List all Scout LaunchAgents by scanning plist files."""
        plist_dir = self._plist_dir()
        if not plist_dir.exists():
            return []

        tasks = []
        for plist_path in sorted(plist_dir.glob(f"{_LABEL_PREFIX}.*.plist")):
            label = plist_path.stem  # e.g., "com.scout.enrollment"
            name = label.replace(f"{_LABEL_PREFIX}.", "", 1)
            try:
                with open(plist_path, "rb") as f:
                    plist = plistlib.load(f)
                status = self._check_loaded(name)
                info = self._plist_to_schedule_info(name, plist, status=status)
                if info:
                    tasks.append(info)
            except Exception:
                continue
        return tasks

    @staticmethod
    def _plist_to_schedule_info(
        name: str, plist: dict, status: str = "Unknown",
    ) -> ScheduleInfo | None:
        """Convert a parsed plist dict to ScheduleInfo.

        Pure parsing — no subprocess calls. Status is passed in by the caller.
        """
        interval = plist.get("StartCalendarInterval", {})

        if isinstance(interval, list):
            schedule_type = "Weekly"
            first = interval[0]
            hour = first.get("Hour", 0)
            minute = first.get("Minute", 0)
            day_names = [_REVERSE_DAY_MAP.get(i.get("Weekday", -1), "?") for i in interval]
            days = ", ".join(day_names)
        else:
            hour = interval.get("Hour", 0)
            minute = interval.get("Minute", 0)
            if "Weekday" in interval:
                schedule_type = "Weekly"
                days = _REVERSE_DAY_MAP.get(interval["Weekday"], "?")
            else:
                schedule_type = "Daily"
                days = ""

        run_script = plist.get("ProgramArguments", [""])[0]

        return ScheduleInfo(
            name=name,
            task_name=plist.get("Label", f"{_LABEL_PREFIX}.{name}"),
            status=status,
            schedule_type=schedule_type,
            start_time=f"{hour:02d}:{minute:02d}",
            next_run="(managed by launchd)",
            task_to_run=run_script,
            days=days,
        )
