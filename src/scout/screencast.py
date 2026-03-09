"""CDP screencast recording — captures frames and encodes video."""

from __future__ import annotations

import base64
import logging
import os
import shutil
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from botasaurus_driver import cdp

if TYPE_CHECKING:
    from botasaurus_driver import Driver

logger = logging.getLogger(__name__)

# Defaults
DEFAULT_MAX_WIDTH = 1920
DEFAULT_MAX_HEIGHT = 1080
DEFAULT_QUALITY = 95
DEFAULT_TARGET_FPS = 15
MAX_RECORDING_SECONDS = 600  # 10 minute safety cap
CHROME_COMPOSITOR_FPS = 60
FFMPEG_TIMEOUT_MINIMUM = 30  # seconds — floor for dynamic timeout


def _every_nth_frame(target_fps: int) -> int:
    """Calculate every_nth_frame for CDP startScreencast.

    Chrome compositor runs at ~60fps. To approximate target_fps,
    we skip frames: every_nth = 60 / target_fps (clamped to >= 1).
    """
    if target_fps <= 0:
        return 6  # default ~10fps
    return max(1, round(CHROME_COMPOSITOR_FPS / target_fps))


def _find_ffmpeg() -> str | None:
    """Locate an ffmpeg binary, checking imageio-ffmpeg first, then system PATH."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError):
        pass

    return shutil.which("ffmpeg")


class ScreencastMonitor:
    """Records browser screen via CDP Page.startScreencast.

    Frames are written to a temp directory on disk as numbered JPEG files.
    On stop(), frames are stitched into an MP4 video using ffmpeg
    (if available) or returned as a directory of frame images.

    Thread safety: all shared state protected by self._lock.
    Deadlock safety: frame ACK uses send(..., wait_for_response=False).
    """

    def __init__(self, output_dir: str) -> None:
        self.output_dir = output_dir
        self.recording = False
        self._driver: Driver | None = None
        self._lock = threading.Lock()
        self._frame_count = 0
        self._frames_dir: str | None = None
        self._started_at: str | None = None
        self._stopped_at: str | None = None
        self._target_fps: int = DEFAULT_TARGET_FPS
        self._max_width: int = DEFAULT_MAX_WIDTH
        self._max_height: int = DEFAULT_MAX_HEIGHT
        self._quality: int = DEFAULT_QUALITY
        self._start_time: float = 0.0
        self._generation: int = 0
        self._safety_timer: threading.Timer | None = None
        self._encoding_succeeded: bool = False

    def start(
        self,
        driver: Driver,
        max_width: int = DEFAULT_MAX_WIDTH,
        max_height: int = DEFAULT_MAX_HEIGHT,
        quality: int = DEFAULT_QUALITY,
        target_fps: int = DEFAULT_TARGET_FPS,
    ) -> None:
        """Start screencast recording."""
        if self.recording:
            raise ValueError("Recording already in progress. Stop current recording first.")

        self._driver = driver
        self._max_width = max_width
        self._max_height = max_height
        self._quality = quality
        self._target_fps = target_fps
        self._frame_count = 0
        self._started_at = datetime.now(timezone.utc).isoformat()
        self._stopped_at = None
        self._start_time = time.monotonic()

        # Create temp directory for frames
        os.makedirs(self.output_dir, exist_ok=True)
        self._frames_dir = tempfile.mkdtemp(
            prefix="scout_screencast_", dir=self.output_dir
        )

        # Increment generation to invalidate any stale handlers from previous recordings.
        # botasaurus has no remove_handler(), so old handlers accumulate.
        # The closure below captures `gen`; if self._generation has been
        # incremented by a subsequent start(), the stale handler returns early.
        self._generation += 1
        gen = self._generation

        def handler(event: cdp.page.ScreencastFrame) -> None:
            if gen != self._generation:
                return
            self._on_frame(event)

        driver._tab.add_handler(cdp.page.ScreencastFrame, handler)

        # Start screencast via CDP
        nth = _every_nth_frame(target_fps)
        driver.run_cdp_command(cdp.page.start_screencast(
            format_="png",
            quality=100,
            max_width=max_width,
            max_height=max_height,
            every_nth_frame=nth,
        ))

        self.recording = True

        # Safety timer: auto-stop after MAX_RECORDING_SECONDS
        self._safety_timer = threading.Timer(
            MAX_RECORDING_SECONDS, self._auto_stop
        )
        self._safety_timer.daemon = True
        self._safety_timer.start()

    def stop(self) -> dict:
        """Stop recording and encode video.

        Returns dict with: video_path, frames_dir, frame_count,
        duration_seconds, encoded, and optionally encode_warning.
        """
        with self._lock:
            if not self.recording:
                return {
                    "video_path": None,
                    "frames_dir": None,
                    "frame_count": 0,
                    "duration_seconds": 0.0,
                    "encoded": False,
                    "error": "No recording in progress.",
                }
            self.recording = False

        # Cancel safety timer
        if self._safety_timer:
            self._safety_timer.cancel()
            self._safety_timer = None

        self._stopped_at = datetime.now(timezone.utc).isoformat()

        # Stop CDP screencast
        if self._driver:
            try:
                self._driver.run_cdp_command(cdp.page.stop_screencast())
            except Exception:
                pass  # Best effort — browser might have closed

        duration = time.monotonic() - self._start_time

        with self._lock:
            frame_count = self._frame_count
            frames_dir = self._frames_dir

        # Attempt video encoding
        video_path = None
        encoded = False
        encode_warning = None

        if frame_count > 0:
            video_path, encoded, encode_warning = self._encode_video(
                frames_dir, frame_count
            )

        self._encoding_succeeded = encoded

        # Clean up frames directory only if encoding succeeded
        if encoded and frames_dir and os.path.isdir(frames_dir):
            try:
                shutil.rmtree(frames_dir)
            except Exception:
                pass

        result = {
            "video_path": video_path,
            "frames_dir": frames_dir if not encoded else None,
            "frame_count": frame_count,
            "duration_seconds": round(duration, 1),
            "encoded": encoded,
        }
        if encode_warning:
            result["encode_warning"] = encode_warning

        return result

    def status(self) -> dict:
        """Return current recording status."""
        with self._lock:
            return {
                "recording": self.recording,
                "frame_count": self._frame_count,
                "started_at": self._started_at,
                "elapsed_seconds": round(
                    time.monotonic() - self._start_time, 1
                ) if self.recording else 0.0,
                "target_fps": self._target_fps,
                "resolution": f"{self._max_width}x{self._max_height}",
            }

    def cleanup(self) -> None:
        """Clean up any leftover temp directories and timers.

        Preserves raw frames if encoding failed — the user may want
        to manually encode or retry.
        """
        if self._safety_timer:
            self._safety_timer.cancel()
            self._safety_timer = None
        if self._encoding_succeeded and self._frames_dir and os.path.isdir(self._frames_dir):
            try:
                shutil.rmtree(self._frames_dir)
            except Exception:
                pass

    def _on_frame(self, event: cdp.page.ScreencastFrame) -> None:
        """CDP ScreencastFrame handler — runs on websocket thread.

        CRITICAL: Must NOT call run_cdp_command() here (deadlock).
        Uses _tab.send(..., wait_for_response=False) for ACK.
        """
        if not self.recording:
            return

        try:
            # Decode and write frame to disk
            frame_data = base64.b64decode(event.data)
            with self._lock:
                frame_num = self._frame_count
                self._frame_count += 1
                frames_dir = self._frames_dir

            if frames_dir:
                frame_path = os.path.join(
                    frames_dir, f"frame_{frame_num:06d}.png"
                )
                with open(frame_path, "wb") as f:
                    f.write(frame_data)

            # ACK the frame (fire-and-forget, no deadlock)
            self._driver._tab.send(
                cdp.page.screencast_frame_ack(event.session_id),
                wait_for_response=False,
            )
        except Exception:
            logger.debug("Error processing screencast frame", exc_info=True)

    def _auto_stop(self) -> None:
        """Called by safety timer — stops screencast to prevent runaway."""
        with self._lock:
            if not self.recording:
                return
            self.recording = False

        logger.warning(
            "Auto-stopping recording after %ds safety limit",
            MAX_RECORDING_SECONDS,
        )
        self._stopped_at = datetime.now(timezone.utc).isoformat()

        if self._driver:
            try:
                # Fire-and-forget — we're on the timer thread, not main thread
                self._driver._tab.send(
                    cdp.page.stop_screencast(),
                    wait_for_response=False,
                )
            except Exception:
                pass

    def _encode_video(
        self, frames_dir: str, frame_count: int
    ) -> tuple[str | None, bool, str | None]:
        """Encode frames to MP4 using ffmpeg subprocess.

        Returns (video_path, success, error_message).
        Falls back gracefully if ffmpeg is not available.
        """
        if frame_count == 0:
            return None, False, "No frames to encode"

        ffmpeg = _find_ffmpeg()
        if ffmpeg is None:
            return None, False, (
                "ffmpeg not found. Frames saved to: "
                f"{frames_dir}. Install with: pip install 'imageio-ffmpeg' "
                "or install ffmpeg on your system PATH."
            )

        # Verify frame files exist
        frame_pattern = os.path.join(frames_dir, "frame_%06d.png")
        first_frame = os.path.join(frames_dir, "frame_000000.png")
        if not os.path.isfile(first_frame):
            return None, False, "No frame files found in temp directory"

        video_filename = (
            f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        )
        video_path = os.path.join(self.output_dir, video_filename)

        try:
            cmd = [
                ffmpeg, "-y",
                "-framerate", str(self._target_fps),
                "-i", frame_pattern,
                "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                video_path,
            ]
            # ~25 frames/sec encoding speed gives 120s for 3000 frames (old parity)
            # and 240s for 6000 frames (new max). Floor of 30s prevents tiny timeouts.
            encoding_timeout = max(FFMPEG_TIMEOUT_MINIMUM, frame_count // 25)
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=encoding_timeout,
            )
            if result.returncode != 0:
                stderr = result.stderr.decode(errors="replace")[:500]
                return None, False, f"ffmpeg exited with code {result.returncode}: {stderr}"

            return video_path, True, None

        except subprocess.TimeoutExpired:
            return None, False, (
                f"ffmpeg encoding timed out after {encoding_timeout}s "
                f"({frame_count} frames). Frames at: {frames_dir}"
            )
        except Exception as e:
            return None, False, f"Encoding failed: {e}. Frames at: {frames_dir}"
