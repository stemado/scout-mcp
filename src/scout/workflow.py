"""Workflow JSON schema models -- portable, replayable browser automation recipes."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field

from .models import ActionRecord, SessionHistory


class WorkflowVariable(BaseModel):
    """A declared variable for parameterizing workflow steps."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["credential", "string", "url"] = "string"
    default: str = ""
    description: str = ""


class WorkflowSettings(BaseModel):
    """Global execution settings for a workflow."""

    model_config = ConfigDict(extra="forbid")

    headless: bool = False
    default_timeout_ms: int = Field(default=30000, ge=0)
    step_delay_ms: int = Field(default=500, ge=0)
    on_error: Literal["stop", "continue", "retry"] = "stop"


class WorkflowStep(BaseModel):
    """A single step in a workflow sequence."""

    model_config = ConfigDict(extra="forbid")

    order: int = Field(ge=1)
    name: str
    action: Literal[
        "navigate", "click", "type", "select", "scroll", "wait",
        "wait_for_download", "wait_for_response",
        "press_key", "hover", "clear", "upload_file",
    ]

    # Common optional fields
    selector: str | None = None
    value: str | None = None
    frame_context: str | None = None
    on_error: Literal["stop", "continue", "retry"] | None = None
    timeout_ms: int | None = Field(default=None, ge=0)

    # Action-specific optional fields
    clear_first: bool | None = None            # type
    filename_pattern: str | None = None        # wait_for_download
    download_dir: str | None = None            # wait_for_download
    url_pattern: str | None = None             # wait_for_response
    method: str | None = None                  # wait_for_response


class WorkflowSource(BaseModel):
    """Provenance of a workflow -- which tool generated it."""

    model_config = ConfigDict(extra="forbid")

    tool: str = "scout"
    session_id: str = ""


class Workflow(BaseModel):
    """A portable, replayable browser automation workflow."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    name: str
    description: str = ""
    created: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: WorkflowSource = Field(default_factory=WorkflowSource)
    variables: dict[str, WorkflowVariable] = Field(default_factory=dict)
    settings: WorkflowSettings = Field(default_factory=WorkflowSettings)
    steps: list[WorkflowStep] = Field(default_factory=list)


# Patterns that indicate a credential field
_PASSWORD_PATTERNS = re.compile(r"password|passwd|pwd|secret", re.IGNORECASE)
_USERNAME_PATTERNS = re.compile(
    r"username|user[-_]?(?:name|id)|email|login[-_]?(?:name|id)|userid",
    re.IGNORECASE,
)


class WorkflowConverter:
    """Converts a Scout SessionHistory into a portable Workflow."""

    @staticmethod
    def from_history(
        history: SessionHistory,
        name: str,
        description: str = "",
    ) -> Workflow:
        """Build a Workflow from a SessionHistory.

        - Filters to successful actions only
        - Auto-generates human-readable step names
        - Parameterizes credential fields (password/username)
        - Strips 'main' frame_context (it's the default)
        """
        successful = [a for a in history.actions if a.success]

        def _is_pre_parameterized(action: ActionRecord) -> bool:
            return bool(action.value and action.value.startswith("${"))

        # First pass: identify credential fields (skip pre-parameterized values)
        password_indices: set[int] = set()
        username_indices: set[int] = set()

        for i, action in enumerate(successful):
            if action.action == "type" and action.selector and not _is_pre_parameterized(action):
                if _PASSWORD_PATTERNS.search(action.selector):
                    password_indices.add(i)
                    # Look backward for the nearest type action on a username-like field
                    for j in range(i - 1, -1, -1):
                        prev = successful[j]
                        if prev.action == "type" and prev.selector and not _is_pre_parameterized(prev) and _USERNAME_PATTERNS.search(prev.selector):
                            username_indices.add(j)
                            break

        # Build variables from auto-detected credential fields
        variables: dict[str, WorkflowVariable] = {}
        if password_indices:
            variables["PASSWORD"] = WorkflowVariable(
                type="credential", default="your_password", description="Login password",
            )
        if username_indices:
            variables["USERNAME"] = WorkflowVariable(
                type="credential", default="your_username", description="Login username",
            )

        # Collect pre-parameterized ${VAR} values and create credential entries
        _VAR_RE = re.compile(r"^\$\{(\w+)\}$")
        for action in successful:
            if _is_pre_parameterized(action):
                m = _VAR_RE.match(action.value)  # type: ignore[arg-type]
                if m:
                    var_name = m.group(1)
                    if var_name not in variables:
                        variables[var_name] = WorkflowVariable(type="credential")

        # Second pass: build steps
        steps: list[WorkflowStep] = []
        for i, action in enumerate(successful):
            value = action.value
            if _is_pre_parameterized(action):
                pass  # preserve pre-parameterized value as-is
            elif i in password_indices:
                value = "${PASSWORD}"
            elif i in username_indices:
                value = "${USERNAME}"

            frame_context = action.frame_context
            if frame_context == "main":
                frame_context = None

            step = WorkflowStep(
                order=len(steps) + 1,
                name=_generate_step_name(action),
                action=action.action,
                selector=action.selector,
                value=value,
                frame_context=frame_context if frame_context else None,
            )
            steps.append(step)

        return Workflow(
            name=name,
            description=description,
            source=WorkflowSource(tool="scout", session_id=history.session_id),
            variables=variables,
            steps=steps,
        )


def _generate_step_name(action: ActionRecord) -> str:
    """Generate a human-readable name for a workflow step."""
    match action.action:
        case "navigate":
            url = action.value or ""
            try:
                domain = urlparse(url).netloc
                return f"Navigate to {domain}" if domain else "Navigate"
            except Exception:
                return "Navigate"
        case "click":
            selector = action.selector or ""
            return f"Click '{selector}'"
        case "type":
            selector = action.selector or ""
            return f"Type into '{selector}'"
        case "select":
            selector = action.selector or ""
            return f"Select option in '{selector}'"
        case "scroll":
            return "Scroll page"
        case "wait":
            if action.selector:
                return f"Wait for '{action.selector}'"
            return f"Wait {action.value or '1000'}ms"
        case "press_key":
            return f"Press '{action.value}' key"
        case "hover":
            return f"Hover over '{action.selector}'"
        case "clear":
            return f"Clear '{action.selector}'"
        case "upload_file":
            return f"Upload file to '{action.selector}'"
        case _:
            return action.action.replace("_", " ").title()
