from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from io import StringIO

from accounts.models import User

from .models import Sermon
from .playback_audio import PLAYBACK_AUDIO_FILTER, normalize_sermon_playback_audio
from .processing import PermanentProcessingError


class PlaybackAudioTests(TestCase):
    def setUp(self):
        self.media_directory = TemporaryDirectory()
        self.settings_override = override_settings(MEDIA_ROOT=self.media_directory.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(self.media_directory.cleanup)
        self.user = User.objects.create_user(
            email="loudnorm@example.com",
            password="safe-test-password",
        )

    def sermon(self) -> Sermon:
        return Sermon.objects.create(
            owner=self.user,
            source_draft_id="loudnorm-source",
            captured_at=timezone.now(),
            duration_seconds=120,
            audio=SimpleUploadedFile(
                "quiet.m4a", b"quiet-audio", content_type="audio/mp4"
            ),
            audio_mime_type="audio/mp4",
            audio_size_bytes=11,
        )

    def test_normalize_rewrites_file_and_marks_normalized(self):
        sermon = self.sermon()
        source = Path(sermon.audio.path)

        def fake_ffmpeg(command: tuple[str, ...]) -> None:
            self.assertIn(PLAYBACK_AUDIO_FILTER, command)
            Path(command[-1]).write_bytes(b"louder-normalized-audio")

        with (
            patch("sermons.playback_audio._run_ffmpeg", side_effect=fake_ffmpeg),
            patch(
                "sermons.playback_audio.probe_audio_duration_seconds",
                return_value=121,
            ),
        ):
            changed = normalize_sermon_playback_audio(sermon)

        sermon.refresh_from_db()
        self.assertTrue(changed)
        self.assertIsNotNone(sermon.audio_normalized_at)
        self.assertEqual(sermon.audio_size_bytes, 23)
        self.assertEqual(sermon.duration_seconds, 121)
        self.assertEqual(sermon.audio_mime_type, "audio/mp4")
        self.assertTrue(source.is_file())
        self.assertEqual(source.read_bytes(), b"louder-normalized-audio")

    def test_normalize_is_idempotent_without_force(self):
        sermon = self.sermon()
        sermon.audio_normalized_at = timezone.now()
        sermon.save(update_fields=("audio_normalized_at", "updated_at"))

        with patch("sermons.playback_audio._run_ffmpeg") as run_ffmpeg:
            changed = normalize_sermon_playback_audio(sermon)

        self.assertFalse(changed)
        run_ffmpeg.assert_not_called()

    def test_management_command_dry_run_does_not_rewrite(self):
        sermon = self.sermon()
        stdout = StringIO()

        with patch("sermons.playback_audio._run_ffmpeg") as run_ffmpeg:
            call_command("normalize_sermon_audio", "--dry-run", stdout=stdout)

        run_ffmpeg.assert_not_called()
        sermon.refresh_from_db()
        self.assertIsNone(sermon.audio_normalized_at)
        self.assertIn(str(sermon.id), stdout.getvalue())

    def test_management_command_normalizes_pending_sermons(self):
        sermon = self.sermon()
        stdout = StringIO()

        def fake_ffmpeg(command: tuple[str, ...]) -> None:
            Path(command[-1]).write_bytes(b"normalized-via-command")

        with (
            patch("sermons.playback_audio._run_ffmpeg", side_effect=fake_ffmpeg),
            patch(
                "sermons.playback_audio.probe_audio_duration_seconds",
                return_value=120,
            ),
        ):
            call_command("normalize_sermon_audio", stdout=stdout)

        sermon.refresh_from_db()
        self.assertIsNotNone(sermon.audio_normalized_at)
        self.assertEqual(sermon.audio_size_bytes, 22)
        self.assertIn("rewritten=1", stdout.getvalue())

    def test_normalize_requires_existing_file(self):
        sermon = self.sermon()
        Path(sermon.audio.path).unlink()

        with self.assertRaises(PermanentProcessingError):
            normalize_sermon_playback_audio(sermon)
