"""Tests for screenshot auto-save to disk."""

import base64
import json
import os

from mcp.types import CallToolResult, ImageContent, TextContent

from scout.models import ScreenshotResult


def _save_screenshot(download_dir: str, raw_bytes: bytes, fmt: str = "png") -> ScreenshotResult:
    """Reproduce the disk-write logic from take_screenshot_tool for testability."""
    from datetime import datetime

    result = ScreenshotResult(success=True, format=fmt, byte_size=len(raw_bytes))
    ext = "jpg" if fmt == "jpeg" else fmt
    timestamp_str = datetime.now().strftime("%H%M%S")
    base = f"screenshot_{timestamp_str}"
    save_path = os.path.join(download_dir, f"{base}.{ext}")
    counter = 1
    while os.path.exists(save_path):
        save_path = os.path.join(download_dir, f"{base}_{counter}.{ext}")
        counter += 1
    os.makedirs(download_dir, exist_ok=True)
    with open(save_path, "wb") as f:
        f.write(raw_bytes)
    result.file_path = save_path
    return result


def test_screenshot_saves_to_disk(tmp_path):
    result = _save_screenshot(str(tmp_path), b"\x89PNG_fake_data")
    assert result.file_path is not None
    assert os.path.isfile(result.file_path)
    with open(result.file_path, "rb") as f:
        assert f.read() == b"\x89PNG_fake_data"


def test_screenshot_auto_increments_on_collision(tmp_path):
    r1 = _save_screenshot(str(tmp_path), b"first")
    r2 = _save_screenshot(str(tmp_path), b"second")
    assert r1.file_path != r2.file_path
    assert "_1." in os.path.basename(r2.file_path)
    with open(r2.file_path, "rb") as f:
        assert f.read() == b"second"


def test_screenshot_jpeg_extension(tmp_path):
    result = _save_screenshot(str(tmp_path), b"jpeg_data", fmt="jpeg")
    assert result.file_path.endswith(".jpg")


def _build_screenshot_response(
    result: ScreenshotResult, raw_bytes: bytes, fmt: str = "png", return_image: bool = True
) -> CallToolResult:
    """Reproduce the response-assembly logic from take_screenshot_tool."""
    content = [TextContent(type="text", text=json.dumps(result.model_dump(exclude_none=True)))]
    if return_image:
        mime = f"image/{fmt}"
        content.append(ImageContent(type="image", data=base64.b64encode(raw_bytes).decode(), mimeType=mime))
    return CallToolResult(content=content)


def test_return_image_true_includes_image_content():
    result = ScreenshotResult(success=True, format="png", byte_size=10, file_path="/tmp/test.png")
    response = _build_screenshot_response(result, b"fake_image", return_image=True)
    assert len(response.content) == 2
    assert response.content[0].type == "text"
    assert response.content[1].type == "image"
    assert response.content[1].data == base64.b64encode(b"fake_image").decode()


def test_return_image_false_excludes_image_content():
    result = ScreenshotResult(success=True, format="png", byte_size=10, file_path="/tmp/test.png")
    response = _build_screenshot_response(result, b"fake_image", return_image=False)
    assert len(response.content) == 1
    assert response.content[0].type == "text"
    metadata = json.loads(response.content[0].text)
    assert metadata["file_path"] == "/tmp/test.png"
    assert metadata["success"] is True
