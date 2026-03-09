"""Tests for the annotated demo capture annotation overlay."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from PIL import Image
from capture_annotated_demos import AnnotatedCapture


def test_annotate_frame_adds_banner(tmp_path):
    """annotate_frame() adds a dark banner with text at the bottom."""
    img = Image.new("RGB", (1280, 800), color=(255, 255, 255))
    cap = AnnotatedCapture("test_output", output_root=str(tmp_path))
    result = cap.annotate_frame(img, "SCOUT: Scouting page...")

    # Result should be same size
    assert result.size == (1280, 800)

    # Bottom-center pixel should be dark (the banner).
    # Banner is rgba(0,0,0,0.8) over white, so composited value is ~51.
    bottom_pixel = result.getpixel((640, 790))
    assert bottom_pixel[0] < 60  # R channel should be near-black
    assert bottom_pixel[1] < 60  # G channel
    assert bottom_pixel[2] < 60  # B channel


def test_annotate_frame_none_text_no_banner(tmp_path):
    """annotate_frame() with None text returns image unchanged."""
    img = Image.new("RGB", (1280, 800), color=(255, 255, 255))
    cap = AnnotatedCapture("test_output", output_root=str(tmp_path))
    result = cap.annotate_frame(img, None)

    # Bottom pixel should still be white (no banner)
    bottom_pixel = result.getpixel((640, 790))
    assert bottom_pixel == (255, 255, 255)


def test_annotate_frame_preserves_dimensions(tmp_path):
    """annotate_frame() preserves the original image dimensions for various sizes."""
    cap = AnnotatedCapture("test_output", output_root=str(tmp_path))
    for w, h in [(800, 600), (1920, 1080), (640, 480)]:
        img = Image.new("RGB", (w, h), color=(128, 128, 128))
        result = cap.annotate_frame(img, "Testing dimensions")
        assert result.size == (w, h)


def test_annotate_frame_does_not_mutate_original(tmp_path):
    """annotate_frame() returns a new image, leaving the original untouched."""
    img = Image.new("RGB", (1280, 800), color=(255, 255, 255))
    cap = AnnotatedCapture("test_output", output_root=str(tmp_path))
    original_pixel = img.getpixel((640, 790))
    _ = cap.annotate_frame(img, "Mutate check")

    # Original image bottom pixel should still be white
    assert img.getpixel((640, 790)) == original_pixel


def test_output_dir_created(tmp_path):
    """AnnotatedCapture constructor creates the output directory."""
    cap = AnnotatedCapture("my_demo", output_root=str(tmp_path))
    assert os.path.isdir(cap.output_dir)
    assert cap.output_dir == os.path.join(str(tmp_path), "frames_my_demo")
