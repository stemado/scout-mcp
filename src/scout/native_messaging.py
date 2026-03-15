"""Native Messaging host registration for Chrome extension auth.

Writes the NM host manifest to the OS-specific Chrome directory so the
extension can call chrome.runtime.sendNativeMessage() to retrieve the
Scout session token.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import stat
import sys
import textwrap

logger = logging.getLogger(__name__)

NM_HOST_NAME = "com.scout.bridge"

# Deterministic extension ID derived from the public key in extension/manifest.json.
# Pinning a key in manifest.json makes Chrome assign this same ID on every machine,
# so users never need to look it up manually.  Override with SCOUT_EXTENSION_ID if
# you build a custom extension with a different key.
DEFAULT_EXTENSION_ID = "mjialmenlimilhhjgjjjofneeflihccn"


def _scout_data_dir() -> str:
    """Return ~/.scout path."""
    return os.path.join(os.path.expanduser("~"), ".scout")


def _nm_manifest_dir() -> str:
    """Return the OS-specific Chrome NativeMessagingHosts directory.

    Returns the SCOUT_CHROME_NM_PATH env var if set (escape hatch for
    Brave, Chromium, Edge). Otherwise returns the Chrome stable path.
    """
    custom = os.environ.get("SCOUT_CHROME_NM_PATH")
    if custom:
        return os.path.expanduser(custom)

    system = platform.system()
    if system == "Windows":
        # Windows uses registry, but we still write the manifest file
        # to the Scout data dir and point the registry at it.
        return os.path.join(_scout_data_dir(), "native-messaging")
    elif system == "Darwin":
        return os.path.expanduser(
            "~/Library/Application Support/Google/Chrome/NativeMessagingHosts"
        )
    else:
        return os.path.expanduser(
            "~/.config/google-chrome/NativeMessagingHosts"
        )


def _write_nm_host_script(path: str) -> None:
    """Write the NM host script to disk.

    Embedded as a string so it works whether Scout is run from source
    or installed as a package.
    """
    script = textwrap.dedent("""\
        #!/usr/bin/env python3
        import json, os, struct, sys, tempfile
        TOKEN_FILENAME = "scout-extension-token"
        def _read():
            raw = sys.stdin.buffer.read(4)
            if len(raw) < 4: return {}
            n = struct.unpack("<I", raw)[0]
            return json.loads(sys.stdin.buffer.read(n)) if n else {}
        def _write(obj):
            b = json.dumps(obj).encode()
            sys.stdout.buffer.write(struct.pack("<I", len(b)) + b)
            sys.stdout.buffer.flush()
        def main():
            try: _read()
            except: pass
            p = os.path.join(tempfile.gettempdir(), TOKEN_FILENAME)
            try:
                with open(p) as f: _write({"token": f.read().strip()})
            except FileNotFoundError: _write({"error": "scout_not_running"})
            except Exception as e: _write({"error": str(e)})
        if __name__ == "__main__": main()
    """)
    with open(path, "w", newline="\n") as f:
        f.write(script)


def ensure_native_messaging_host() -> bool:
    """Register the NM host for Chrome.

    Returns True if registered, False if skipped.
    """
    extension_id = os.environ.get("SCOUT_EXTENSION_ID", DEFAULT_EXTENSION_ID)

    nm_dir = os.path.join(_scout_data_dir(), "native-messaging")
    os.makedirs(nm_dir, exist_ok=True)

    # Write the NM host script (embedded to work in installed packages)
    host_script_dst = os.path.join(nm_dir, "scout_nm_host.py")
    _write_nm_host_script(host_script_dst)

    # Determine the path Chrome should launch
    system = platform.system()
    if system == "Windows":
        # Write .bat wrapper with absolute Python path from sys.executable
        bat_path = os.path.join(nm_dir, "scout_nm_host.bat")
        with open(bat_path, "w") as f:
            f.write(f'@echo off\n"{sys.executable}" "%~dp0scout_nm_host.py"\n')
        host_path = bat_path
    else:
        # Make script executable on Unix
        os.chmod(host_script_dst, os.stat(host_script_dst).st_mode | stat.S_IXUSR)
        host_path = host_script_dst

    # Write the manifest
    manifest = {
        "name": NM_HOST_NAME,
        "description": "Scout MCP token relay",
        "path": host_path,
        "type": "stdio",
        "allowed_origins": [f"chrome-extension://{extension_id}/"],
    }

    manifest_dir = _nm_manifest_dir()
    os.makedirs(manifest_dir, exist_ok=True)
    manifest_path = os.path.join(manifest_dir, f"{NM_HOST_NAME}.json")

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    # Windows: create registry key pointing to the manifest
    if system == "Windows":
        try:
            import winreg
            key_path = f"Software\\Google\\Chrome\\NativeMessagingHosts\\{NM_HOST_NAME}"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, manifest_path)
            logger.info("Registered NM host in Windows registry: %s", key_path)
        except Exception as e:
            logger.warning("Failed to create Windows registry key for NM host: %s", e)

    logger.info(
        "Native Messaging host registered: manifest=%s, host=%s, extension=%s",
        manifest_path, host_path, extension_id,
    )
    return True
