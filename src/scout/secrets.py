"""Load credentials from .env files for fill_secret.

Search order for the .env file:
    1. Explicit ``env_file`` path (if provided)
    2. ``SCOUT_ENV_FILE`` environment variable
    3. ``.env`` in the current working directory

Uses ``python-dotenv`` for parsing.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values


class EnvLoadError(Exception):
    """Raised when the .env file cannot be located or loaded."""


def _resolve_env_path(env_file: str | None = None) -> Path:
    """Determine which .env file to load using the three-level search order."""
    # 1. Explicit path
    if env_file is not None:
        p = Path(env_file)
        if not p.is_file():
            raise EnvLoadError(f".env file not found: {p}")
        return p

    # 2. SCOUT_ENV_FILE env var
    env_var = os.environ.get("SCOUT_ENV_FILE")
    if env_var:
        p = Path(env_var)
        if not p.is_file():
            raise EnvLoadError(f".env file not found: {p}")
        return p

    # 3. .env in current working directory
    cwd_env = Path.cwd() / ".env"
    if cwd_env.is_file():
        return cwd_env

    raise EnvLoadError(
        "No .env file found. Searched: SCOUT_ENV_FILE env var and .env in working directory."
    )


def load_env_vars(env_file: str | None = None) -> dict[str, str]:
    """Load variables from a .env file and return them as a dict."""
    path = _resolve_env_path(env_file)
    raw = dotenv_values(path)
    return {key: (value if value is not None else "") for key, value in raw.items()}
