"""Capture annotated browser screenshots for demo GIFs.

Extends the existing capture pattern with PIL text overlays that show
what Scout is doing at each step. Produces frame directories that ffmpeg
encodes into GIFs.

Usage:
    python scripts/capture_annotated_demos.py scout
    python scripts/capture_annotated_demos.py form
    python scripts/capture_annotated_demos.py replay
    python scripts/capture_annotated_demos.py all
    python scripts/capture_annotated_demos.py encode [--fps 10]
"""
import argparse
import base64
import io
import os
import shutil
import subprocess
import time

from PIL import Image, ImageDraw, ImageFont

BANNER_HEIGHT = 48
BANNER_COLOR = (0, 0, 0, 204)  # rgba(0,0,0,0.8) -- 204/255 ~ 0.8
TEXT_COLOR = (255, 255, 255)
FONT_SIZE = 20
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")


def _load_font() -> ImageFont.FreeTypeFont:
    """Load Consolas (Windows) or fall back to DejaVu Sans Mono."""
    for name in ("consola.ttf", "DejaVuSansMono.ttf", "Courier New.ttf"):
        try:
            return ImageFont.truetype(name, FONT_SIZE)
        except OSError:
            continue
    return ImageFont.load_default()


class AnnotatedCapture:
    """Captures CDP screenshots with text annotation overlays."""

    def __init__(self, output_name: str, output_root: str | None = None):
        root = output_root if output_root is not None else ASSETS_DIR
        self.output_dir = os.path.join(root, f"frames_{output_name}")
        os.makedirs(self.output_dir, exist_ok=True)
        self.font = _load_font()
        self.frame_num = 0

    def annotate_frame(self, img: Image.Image, text: str | None) -> Image.Image:
        """Overlay a dark banner with white text at the bottom of the image.

        Returns a new image -- does not mutate the input.
        If text is None, returns the image unchanged.
        """
        if text is None:
            return img.copy()

        result = img.copy().convert("RGBA")
        overlay = Image.new("RGBA", result.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Draw banner rectangle
        w, h = result.size
        draw.rectangle(
            [(0, h - BANNER_HEIGHT), (w, h)],
            fill=BANNER_COLOR,
        )

        # Draw text centered in the banner
        bbox = draw.textbbox((0, 0), text, font=self.font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        text_x = (w - text_w) // 2
        text_y = h - BANNER_HEIGHT + (BANNER_HEIGHT - text_h) // 2
        draw.text((text_x, text_y), text, fill=TEXT_COLOR, font=self.font)

        result = Image.alpha_composite(result, overlay)
        return result.convert("RGB")

    def take_frame(self, driver, text: str | None = None) -> Image.Image:
        """Take a CDP screenshot, annotate it, save it, return the image."""
        from botasaurus_driver.cdp import page as page_cdp

        raw = driver.run_cdp_command(page_cdp.capture_screenshot(
            format_="jpeg",
            quality=85,
        ))
        img = Image.open(io.BytesIO(base64.b64decode(raw)))
        annotated = self.annotate_frame(img, text)
        path = os.path.join(self.output_dir, f"frame_{self.frame_num:06d}.jpg")
        annotated.save(path, "JPEG", quality=90)
        self.frame_num += 1
        return annotated

    def hold(self, driver, text: str | None, count: int = 8):
        """Repeat the current frame to create a pause effect."""
        for _ in range(count):
            self.take_frame(driver, text)

    def type_into_field(self, driver, selector: str, value: str,
                        text: str | None = None):
        """Focus a field and type char-by-char, capturing a frame per keystroke."""
        from botasaurus_driver.cdp import input_ as input_cdp

        driver.run_js(f'document.querySelector("{selector}").focus()')
        time.sleep(0.1)
        for ch in value:
            driver.run_cdp_command(input_cdp.dispatch_key_event(
                type_="keyDown", text=ch, key=ch,
            ))
            driver.run_cdp_command(input_cdp.dispatch_key_event(
                type_="keyUp", key=ch,
            ))
            time.sleep(0.05)
            self.take_frame(driver, text)


def capture_scout_demo():
    """Capture 'See the Web' demo: scout anthropic.com."""
    from botasaurus_driver import Driver

    cap = AnnotatedCapture("scout")
    driver = Driver()
    try:
        # Load anthropic.com
        driver.get("https://www.anthropic.com")
        time.sleep(3)

        # Hold on initial page — no annotation yet
        cap.hold(driver, None, 10)

        # "Scouting" phase
        cap.hold(driver, "Scout: Scouting page...", 12)

        # Show results
        # (We'll get real counts by running JS on the page)
        link_count = driver.run_js("return document.querySelectorAll('a').length")
        btn_count = driver.run_js("return document.querySelectorAll('button').length")
        input_count = driver.run_js("return document.querySelectorAll('input').length")
        cap.hold(
            driver,
            f"Found: {link_count} links, {btn_count} buttons, {input_count} inputs",
            18,
        )

        # Navigate to another page
        cap.hold(driver, "Navigating to /careers...", 6)
        driver.get("https://www.anthropic.com/careers")
        time.sleep(3)

        # Scout the new page
        cap.hold(driver, "Scout: Scouting new page...", 12)

        link_count = driver.run_js("return document.querySelectorAll('a').length")
        btn_count = driver.run_js("return document.querySelectorAll('button').length")
        cap.hold(
            driver,
            f"Found: {link_count} links, {btn_count} buttons  |  ~200 tokens",
            20,
        )

    finally:
        driver.close()

    print(f"Scout demo: {cap.frame_num} frames in {cap.output_dir}")


def _form_url() -> str:
    """Return the file:// URL for the demo form HTML page."""
    form_path = os.path.join(ASSETS_DIR, "demo-form.html")
    # Convert to absolute path and use forward slashes for file:// URL
    abs_path = os.path.abspath(form_path).replace("\\", "/")
    return f"file:///{abs_path}"


def capture_form_demo():
    """Capture 'Do Things' demo: fill Acme Technologies job application."""
    from botasaurus_driver import Driver

    cap = AnnotatedCapture("form")
    driver = Driver()
    try:
        driver.get(_form_url())
        time.sleep(2)

        # Show the empty form
        cap.hold(driver, None, 8)

        # Finding elements phase
        cap.hold(driver, "Scout: Finding form elements...", 10)
        cap.hold(driver, "Found: 6 inputs, 1 submit button", 12)

        # Fill each field with annotation
        fields = [
            ("#fullName", "John Doe", "Filling: Full Name"),
            ("#email", "john.doe@gmail.com", "Filling: Email"),
            ("#phone", "+1 (415) 555-0142", "Filling: Phone"),
        ]
        for selector, value, label in fields:
            cap.type_into_field(driver, selector, value, text=label)
            cap.hold(driver, label, 4)

        # LinkedIn and Current Role
        cap.type_into_field(
            driver, "#linkedin",
            "https://linkedin.com/in/johndoe",
            text="Filling: LinkedIn",
        )
        cap.hold(driver, "Filling: LinkedIn", 3)

        cap.type_into_field(
            driver, "#currentRole",
            "Staff Engineer at Stripe",
            text="Filling: Current Role",
        )
        cap.hold(driver, "Filling: Current Role", 3)

        # Motivation textarea
        cap.type_into_field(
            driver, "#motivation",
            "I'm passionate about developer tools that make automation accessible.",
            text="Filling: Motivation",
        )
        cap.hold(driver, "Filling: Motivation", 6)

        # Submit
        cap.hold(driver, "Submitting application...", 6)
        driver.run_js('document.querySelector(".submit-btn").click()')
        time.sleep(1)
        cap.hold(driver, "Application submitted  |  6 actions, 4.1s", 18)

    finally:
        driver.close()

    print(f"Form demo: {cap.frame_num} frames in {cap.output_dir}")


def capture_replay_demo():
    """Capture 'Automate It' demo: fast workflow replay."""
    from botasaurus_driver import Driver

    cap = AnnotatedCapture("replay")
    driver = Driver()
    try:
        driver.get(_form_url())
        time.sleep(2)

        # Show the empty form briefly
        cap.hold(driver, "Replaying exported workflow...", 10)

        # Fast fill — no per-keystroke capture, just inject values
        fields = [
            ("#fullName", "John Doe"),
            ("#email", "john.doe@gmail.com"),
            ("#phone", "+1 (415) 555-0142"),
            ("#linkedin", "https://linkedin.com/in/johndoe"),
            ("#currentRole", "Staff Engineer at Stripe"),
        ]
        for selector, value in fields:
            driver.run_js(
                f'var el = document.querySelector("{selector}");'
                f'el.value = "{value}";'
                f'el.dispatchEvent(new Event("input", {{bubbles: true}}));'
            )
            time.sleep(0.15)
            cap.take_frame(driver, "Replaying exported workflow...")
            cap.hold(driver, "Replaying exported workflow...", 2)

        # Textarea — inject value
        driver.run_js(
            'var el = document.querySelector("#motivation");'
            'el.value = "I\'m passionate about developer tools that make automation accessible.";'
            'el.dispatchEvent(new Event("input", {bubbles: true}));'
        )
        cap.hold(driver, "Replaying exported workflow...", 3)

        # Submit — triggers success state
        driver.run_js('document.querySelector(".submit-btn").click()')
        time.sleep(1)

        cap.hold(driver, "Workflow complete  |  6 actions, 1.8s", 18)

    finally:
        driver.close()

    print(f"Replay demo: {cap.frame_num} frames in {cap.output_dir}")


def _encode_gif(frames_dir: str, output_path: str, fps: int = 10):
    """Encode a frame directory to GIF using ffmpeg with palette optimization."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        try:
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            print(f"ffmpeg not found. Encode manually from: {frames_dir}")
            return

    palette = os.path.join(frames_dir, "palette.png")
    input_pattern = os.path.join(frames_dir, "frame_%06d.jpg")

    # Two-pass encoding for better color quality
    subprocess.run([
        ffmpeg, "-y",
        "-framerate", str(fps),
        "-i", input_pattern,
        "-vf", "palettegen=max_colors=128",
        palette,
    ], check=True, capture_output=True)

    subprocess.run([
        ffmpeg, "-y",
        "-framerate", str(fps),
        "-i", input_pattern,
        "-i", palette,
        "-lavfi", "paletteuse=dither=bayer:bayer_scale=3",
        "-loop", "0",
        output_path,
    ], check=True, capture_output=True)

    os.remove(palette)
    print(f"Encoded: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Capture annotated demo GIFs for Scout")
    parser.add_argument(
        "mode",
        choices=["scout", "form", "replay", "all", "encode"],
        help="Which demo to capture, or 'encode' to build GIFs from existing frames",
    )
    parser.add_argument("--fps", type=int, default=10, help="GIF framerate (default: 10)")
    parser.add_argument("--clean", action="store_true",
                        help="Remove frame directories after encoding")
    args = parser.parse_args()

    if args.mode in ("scout", "all"):
        capture_scout_demo()
    if args.mode in ("form", "all"):
        capture_form_demo()
    if args.mode in ("replay", "all"):
        capture_replay_demo()

    if args.mode in ("encode", "all"):
        for name in ("scout", "form", "replay"):
            frames = os.path.join(ASSETS_DIR, f"frames_{name}")
            gif = os.path.join(ASSETS_DIR, f"demo-{name}.gif")
            if os.path.isdir(frames):
                _encode_gif(frames, gif, fps=args.fps)

    if args.clean:
        for name in ("scout", "form", "replay"):
            frames = os.path.join(ASSETS_DIR, f"frames_{name}")
            if os.path.isdir(frames):
                shutil.rmtree(frames)
                print(f"Cleaned: {frames}")
