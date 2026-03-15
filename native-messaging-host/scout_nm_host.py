#!/usr/bin/env python3
"""Scout MCP Bridge — Chrome Native Messaging host.

Reads the Scout session token from a well-known temp file and returns it
to the Chrome extension via Chrome's Native Messaging wire protocol.

Wire format: 4-byte little-endian length prefix + JSON body.
"""

import json
import os
import struct
import sys
import tempfile

TOKEN_FILENAME = "scout-extension-token"


def _read_message() -> dict:
    """Read one NM message from stdin."""
    raw_length = sys.stdin.buffer.read(4)
    if len(raw_length) < 4:
        return {}
    length = struct.unpack("<I", raw_length)[0]
    if length == 0:
        return {}
    body = sys.stdin.buffer.read(length)
    return json.loads(body)


def _write_message(obj: dict) -> None:
    """Write one NM message to stdout."""
    body = json.dumps(obj).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("<I", len(body)))
    sys.stdout.buffer.write(body)
    sys.stdout.buffer.flush()


def main() -> None:
    try:
        msg = _read_message()
    except Exception:
        _write_message({"error": "invalid_request"})
        return

    token_path = os.path.join(tempfile.gettempdir(), TOKEN_FILENAME)

    try:
        with open(token_path, "r") as f:
            token = f.read().strip()
        _write_message({"token": token})
    except FileNotFoundError:
        _write_message({"error": "scout_not_running"})
    except Exception as e:
        _write_message({"error": str(e)})


if __name__ == "__main__":
    main()
