"""Tests for RecordingResult and RecordingRecord model GIF fields."""

from scout.models import RecordingResult, RecordingRecord


class TestRecordingResultModel:
    """Tests for RecordingResult model GIF fields."""

    def test_gif_path_field_exists(self):
        """RecordingResult should have a gif_path field."""
        result = RecordingResult(gif_path="/tmp/test.gif", output_format="gif")
        assert result.gif_path == "/tmp/test.gif"
        assert result.output_format == "gif"

    def test_default_output_format_is_mp4(self):
        """RecordingResult should default output_format to mp4."""
        result = RecordingResult()
        assert result.output_format == "mp4"

    def test_model_dump_excludes_none(self):
        """gif_path should be excluded when None."""
        result = RecordingResult(output_format="mp4")
        dumped = result.model_dump(exclude_none=True)
        assert "gif_path" not in dumped


class TestRecordingRecordModel:
    """Tests for RecordingRecord model format field."""

    def test_format_field_exists(self):
        """RecordingRecord should track output format."""
        record = RecordingRecord(output_format="gif")
        assert record.output_format == "gif"

    def test_default_format_is_mp4(self):
        """RecordingRecord should default to mp4."""
        record = RecordingRecord()
        assert record.output_format == "mp4"
