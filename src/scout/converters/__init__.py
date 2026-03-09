"""Pluggable file format conversion registry.

Usage:
    from scout.converters import convert, detect_format

    # Auto-detect and convert
    fmt = detect_format("report.xls")
    csv_path = convert("report.xls", fmt, "csv")

    # Explicit format
    csv_path = convert("report.xls", "spreadsheetml_2003", "csv")
"""

from __future__ import annotations

from typing import Callable

_HANDLERS: dict[tuple[str, str], Callable[[str], str]] = {}


def register(source: str, target: str):
    """Decorator to register a conversion handler.

    Usage:
        @register("spreadsheetml_2003", "csv")
        def spreadsheetml_to_csv(source_path: str) -> str:
            ...
    """
    def wrapper(fn: Callable[[str], str]) -> Callable[[str], str]:
        _HANDLERS[(source, target)] = fn
        return fn
    return wrapper


def convert(source_path: str, source_format: str, target_format: str) -> str:
    """Convert a file from one format to another.

    Args:
        source_path: Absolute path to the source file.
        source_format: Source format identifier (e.g., "spreadsheetml_2003").
                       Use detect_format() to auto-detect.
        target_format: Target format identifier (e.g., "csv").

    Returns:
        Absolute path to the converted file.

    Raises:
        ValueError: If no converter is registered for the format pair.
    """
    handler = _HANDLERS.get((source_format, target_format))
    if handler is None:
        available = [f"{s} -> {t}" for s, t in _HANDLERS]
        raise ValueError(
            f"No converter registered for {source_format} -> {target_format}. "
            f"Available: {', '.join(available) or 'none'}"
        )
    return handler(source_path)


def detect_format(file_path: str) -> str:
    """Detect file format by inspecting magic bytes and content.

    Returns one of: "spreadsheetml_2003", "xls_binary", "xlsx", "csv", "xml", "unknown".
    """
    with open(file_path, "rb") as f:
        header = f.read(64)

    if not header:
        return "unknown"

    # XML-based formats (SpreadsheetML starts with <?xml)
    if header.startswith(b"<?xml") or header.startswith(b"\xef\xbb\xbf<?xml"):
        with open(file_path, "r", encoding="utf-8-sig") as f:
            peek = f.read(500)
        if "schemas-microsoft-com:office:spreadsheet" in peek:
            return "spreadsheetml_2003"
        return "xml"

    # OLE2 compound document (Excel 97-2003 binary .xls)
    if header[:4] == b"\xd0\xcf\x11\xe0":
        return "xls_binary"

    # ZIP archive (xlsx, docx, etc.)
    if header[:2] == b"PK":
        return "xlsx"

    # ASCII text — likely CSV
    if all(b < 128 for b in header[:64]):
        return "csv"

    return "unknown"


def available_conversions() -> list[str]:
    """List all registered conversion pairs."""
    return [f"{s} -> {t}" for s, t in _HANDLERS]


# Import converter modules to trigger @register decorators
from scout.converters import spreadsheetml  # noqa: E402, F401
