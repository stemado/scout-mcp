"""Capture sequential screenshots for demo GIFs.

Uses botasaurus-driver directly to take CDP screenshots, saving numbered
JPEGs that ffmpeg can combine into GIFs.

Usage:
    python scripts/capture_demo_frames.py scroll <name> <url> [--frames N]
    python scripts/capture_demo_frames.py form-fill <name> <url>
    python scripts/capture_demo_frames.py form-hero <name> <url>
"""
import argparse
import base64
import os
import time

from botasaurus_driver import Driver
import botasaurus_driver.cdp.page as page_cdp
import botasaurus_driver.cdp.input_ as input_cdp


def take_frame(driver, output_dir: str, frame_num: int) -> str:
    """Take a single CDP screenshot and save as JPEG."""
    result = driver.run_cdp_command(page_cdp.capture_screenshot(
        format_="jpeg",
        quality=80,
    ))
    img_data = base64.b64decode(result)
    frame_path = os.path.join(output_dir, f"frame_{frame_num:06d}.jpg")
    with open(frame_path, "wb") as f:
        f.write(img_data)
    return frame_path


def hold_frame(driver, output_dir: str, frame_num: int, count: int = 6) -> int:
    """Repeat a screenshot to create a pause effect in the GIF."""
    for i in range(count):
        take_frame(driver, output_dir, frame_num + i)
    return frame_num + count


def type_char(driver, ch: str):
    """Type a single character via CDP Input.dispatchKeyEvent."""
    driver.run_cdp_command(input_cdp.dispatch_key_event(
        type_="keyDown",
        text=ch,
        key=ch,
    ))
    driver.run_cdp_command(input_cdp.dispatch_key_event(
        type_="keyUp",
        key=ch,
    ))


def type_into_field(driver, selector: str, text: str, output_dir: str, frame_num: int) -> int:
    """Click a field, type text char-by-char, capturing a frame per character."""
    driver.run_js(f'document.querySelector("{selector}").focus()')
    time.sleep(0.1)
    f = frame_num
    for ch in text:
        type_char(driver, ch)
        time.sleep(0.06)
        take_frame(driver, output_dir, f)
        f += 1
    return f


def capture_scroll(url: str, output_dir: str, num_frames: int = 60):
    """Scroll through a page, capturing frames."""
    os.makedirs(output_dir, exist_ok=True)
    driver = Driver()
    driver.get(url)
    time.sleep(2)

    total_height = driver.run_js("return document.body.scrollHeight")
    scroll_step = max(1, total_height // num_frames)
    pos = 0
    frame_count = 0

    while frame_count < num_frames and pos <= total_height:
        take_frame(driver, output_dir, frame_count)
        frame_count += 1
        pos += scroll_step
        driver.run_js(f"window.scrollTo(0, {pos})")
        time.sleep(0.05)

    driver.close()
    print(f"Captured {frame_count} frames in {output_dir}")


def capture_form_fill(url: str, output_dir: str):
    """Capture credential safety demo: show form, type into fields."""
    os.makedirs(output_dir, exist_ok=True)
    driver = Driver()
    driver.get(url)
    time.sleep(2)

    f = 0

    # Hold on empty form
    f = hold_frame(driver, output_dir, f, 8)

    # Type into Customer name
    f = type_into_field(driver, "input[name='custname']", "AcmeCorp", output_dir, f)
    f = hold_frame(driver, output_dir, f, 4)

    # Type into Telephone
    f = type_into_field(driver, "input[name='custtel']", "555-0199", output_dir, f)
    f = hold_frame(driver, output_dir, f, 4)

    # Type into Email
    f = type_into_field(driver, "input[name='custemail']", "admin@acme.io", output_dir, f)
    f = hold_frame(driver, output_dir, f, 6)

    # Select Large pizza
    driver.run_js("document.querySelector('input[value=\"large\"]').click()")
    take_frame(driver, output_dir, f)
    f += 1
    f = hold_frame(driver, output_dir, f, 4)

    # Check Mushrooms
    driver.run_js("document.querySelector('input[value=\"mushroom\"]').click()")
    take_frame(driver, output_dir, f)
    f += 1
    f = hold_frame(driver, output_dir, f, 4)

    # Type delivery instructions
    f = type_into_field(driver, "textarea[name='comments']", "Ring doorbell twice", output_dir, f)
    f = hold_frame(driver, output_dir, f, 8)

    driver.close()
    print(f"Captured {f} frames in {output_dir}")


def capture_hero(url: str, output_dir: str):
    """Capture hero workflow demo: form fill + submit + response."""
    os.makedirs(output_dir, exist_ok=True)
    driver = Driver()
    driver.get(url)
    time.sleep(2)

    f = 0

    # Hold on initial page
    f = hold_frame(driver, output_dir, f, 10)

    # Quick form fill
    fields = [
        ("input[name='custname']", "OttoPilot"),
        ("input[name='custtel']", "555-0100"),
        ("input[name='custemail']", "otto@example.com"),
    ]
    for selector, text in fields:
        f = type_into_field(driver, selector, text, output_dir, f)
        f = hold_frame(driver, output_dir, f, 3)

    # Select Medium pizza
    driver.run_js("document.querySelector('input[value=\"medium\"]').click()")
    take_frame(driver, output_dir, f)
    f += 1
    f = hold_frame(driver, output_dir, f, 3)

    # Check Bacon + Extra Cheese
    driver.run_js("document.querySelector('input[value=\"bacon\"]').click()")
    take_frame(driver, output_dir, f)
    f += 1
    driver.run_js("document.querySelector('input[value=\"cheese\"]').click()")
    take_frame(driver, output_dir, f)
    f += 1
    f = hold_frame(driver, output_dir, f, 3)

    # Type delivery instructions
    f = type_into_field(driver, "textarea[name='comments']", "Leave at door", output_dir, f)
    f = hold_frame(driver, output_dir, f, 4)

    # Submit the form
    # Submit — try multiple selectors
    driver.run_js('(document.querySelector("button") || document.querySelector("input[type=submit]")).click()')
    time.sleep(1.5)

    # Capture the response page
    f = hold_frame(driver, output_dir, f, 12)

    driver.close()
    print(f"Captured {f} frames in {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["scroll", "form-fill", "form-hero"])
    parser.add_argument("name", help="Name for the output directory")
    parser.add_argument("url", help="URL to capture")
    parser.add_argument("--frames", type=int, default=60)
    args = parser.parse_args()

    output_dir = os.path.join("assets", f"frames_{args.name}")

    if args.mode == "scroll":
        capture_scroll(args.url, output_dir, num_frames=args.frames)
    elif args.mode == "form-fill":
        capture_form_fill(args.url, output_dir)
    elif args.mode == "form-hero":
        capture_hero(args.url, output_dir)
