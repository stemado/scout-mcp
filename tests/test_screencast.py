"""Tests for screencast GIF encoding."""

import os
import struct
import tempfile
from unittest.mock import patch, MagicMock

import pytest

from scout.screencast import ScreencastMonitor, _find_ffmpeg


def _create_minimal_png(path: str) -> None:
    """Create a 1x1 red PNG file for testing."""
    import zlib

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
    ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)
    raw = b"\x00\xff\x00\x00"
    compressed = zlib.compress(raw)
    idat_crc = zlib.crc32(b"IDAT" + compressed) & 0xFFFFFFFF
    idat = struct.pack(">I", len(compressed)) + b"IDAT" + compressed + struct.pack(">I", idat_crc)
    iend_crc = zlib.crc32(b"IEND") & 0xFFFFFFFF
    iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)

    with open(path, "wb") as f:
        f.write(signature + ihdr + idat + iend)


class TestEncodeGif:
    """Tests for GIF encoding via ffmpeg."""

    def test_encode_gif_produces_file(self, tmp_path):
        """GIF encoding should produce a .gif file from frames."""
        ffmpeg = _find_ffmpeg()
        if ffmpeg is None:
            pytest.skip("ffmpeg not available")

        monitor = ScreencastMonitor(str(tmp_path))
        monitor._target_fps = 10

        frames_dir = str(tmp_path / "frames")
        os.makedirs(frames_dir)
        for i in range(5):
            _create_minimal_png(os.path.join(frames_dir, f"frame_{i:06d}.png"))

        gif_path, success, warning = monitor._encode_gif(frames_dir, 5)

        assert success is True
        assert gif_path is not None
        assert gif_path.endswith(".gif")
        assert os.path.isfile(gif_path)
        assert warning is None

    def test_encode_gif_no_ffmpeg_returns_error(self, tmp_path):
        """GIF encoding without ffmpeg should return a helpful error."""
        monitor = ScreencastMonitor(str(tmp_path))

        with patch("scout.screencast._find_ffmpeg", return_value=None):
            gif_path, success, warning = monitor._encode_gif(str(tmp_path), 5)

        assert success is False
        assert gif_path is None
        assert "ffmpeg not found" in warning

    def test_encode_gif_no_frames_returns_error(self, tmp_path):
        """GIF encoding with zero frames should return an error."""
        monitor = ScreencastMonitor(str(tmp_path))

        gif_path, success, warning = monitor._encode_gif(str(tmp_path), 0)

        assert success is False
        assert "No frames" in warning

    def test_encode_gif_default_params(self, tmp_path):
        """GIF encoding should use sensible defaults for fps and width."""
        ffmpeg = _find_ffmpeg()
        if ffmpeg is None:
            pytest.skip("ffmpeg not available")

        monitor = ScreencastMonitor(str(tmp_path))
        monitor._target_fps = 15

        frames_dir = str(tmp_path / "frames")
        os.makedirs(frames_dir)
        for i in range(3):
            _create_minimal_png(os.path.join(frames_dir, f"frame_{i:06d}.png"))

        gif_path, success, _ = monitor._encode_gif(frames_dir, 3)

        assert success is True
        assert os.path.getsize(gif_path) > 0


class TestStopWithFormat:
    """Tests for stop() with format parameter."""

    def test_stop_default_format_is_mp4(self, tmp_path):
        """stop() with no format arg should default to mp4 (backward compat)."""
        monitor = ScreencastMonitor(str(tmp_path))
        monitor.recording = True
        monitor._start_time = __import__("time").monotonic()
        monitor._frame_count = 0
        monitor._frames_dir = str(tmp_path)
        monitor._started_at = "2026-01-01T00:00:00Z"

        result = monitor.stop()
        assert result["encoded"] is False
        assert result["output_format"] == "mp4"
        assert result["gif_path"] is None
        assert result["video_path"] is None

    def test_stop_gif_format_calls_encode_gif(self, tmp_path):
        """stop(format='gif') should use GIF encoding path."""
        ffmpeg = _find_ffmpeg()
        if ffmpeg is None:
            pytest.skip("ffmpeg not available")

        monitor = ScreencastMonitor(str(tmp_path))
        monitor.recording = True
        monitor._start_time = __import__("time").monotonic()
        monitor._started_at = "2026-01-01T00:00:00Z"
        monitor._target_fps = 10

        frames_dir = str(tmp_path / "frames")
        os.makedirs(frames_dir)
        for i in range(3):
            _create_minimal_png(os.path.join(frames_dir, f"frame_{i:06d}.png"))
        monitor._frames_dir = frames_dir
        monitor._frame_count = 3

        result = monitor.stop(output_format="gif")

        assert result["encoded"] is True
        assert result.get("gif_path") is not None
        assert result["gif_path"].endswith(".gif")
