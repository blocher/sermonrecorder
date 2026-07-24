import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from .audio_duration import probe_audio_duration_seconds
from .processing import PermanentProcessingError


class AudioDurationTests(SimpleTestCase):
    def test_probe_rounds_ffprobe_duration(self):
        completed = SimpleNamespace(
            stdout=json.dumps({"format": {"duration": "691.98"}}).encode()
        )
        with patch("sermons.audio_duration.subprocess.run", return_value=completed):
            self.assertEqual(
                probe_audio_duration_seconds(Path("/tmp/sermon.m4a")),
                692,
            )

    def test_probe_rejects_missing_duration(self):
        completed = SimpleNamespace(stdout=b'{"format": {}}')
        with patch("sermons.audio_duration.subprocess.run", return_value=completed):
            with self.assertRaises(PermanentProcessingError):
                probe_audio_duration_seconds(Path("/tmp/sermon.m4a"))
