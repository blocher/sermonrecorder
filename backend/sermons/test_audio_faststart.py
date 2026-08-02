import shutil
import subprocess
import struct
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import skipUnless

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from io import StringIO

from accounts.models import User

from .audio_faststart import (
    ensure_m4a_faststart,
    ensure_sermon_listen_audio_faststart,
    m4a_needs_faststart,
)
from .models import Sermon

FFMPEG = shutil.which("ffmpeg")


def _write_sine_m4a(path: Path, *, faststart: bool) -> None:
    command = [
        FFMPEG,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "sine=f=440:d=0.5",
        "-c:a",
        "aac",
        "-b:a",
        "64k",
    ]
    if faststart:
        command.extend(["-movflags", "+faststart"])
    command.append(str(path))
    subprocess.run(command, check=True, capture_output=True)


def _first_media_atom(path: Path) -> str:
    with path.open("rb") as handle:
        while True:
            header = handle.read(8)
            size, atom_type = struct.unpack(">I4s", header)
            label = atom_type.decode("latin1")
            if label in {"moov", "mdat"}:
                return label
            handle.seek(size - 8, 1)


@skipUnless(FFMPEG, "ffmpeg is required for faststart fixture tests")
class AudioFaststartTests(TestCase):
    def setUp(self):
        self.media_directory = TemporaryDirectory()
        self.settings_override = override_settings(
            MEDIA_ROOT=self.media_directory.name,
            FFMPEG_BINARY=FFMPEG,
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(self.media_directory.cleanup)
        self.user = User.objects.create_user(
            email="faststart@example.com",
            password="safe-test-password",
        )

    def test_detects_and_rewrites_moov_at_end(self):
        path = Path(self.media_directory.name) / "late-moov.m4a"
        _write_sine_m4a(path, faststart=False)

        self.assertEqual(_first_media_atom(path), "mdat")
        self.assertTrue(m4a_needs_faststart(path))
        self.assertTrue(ensure_m4a_faststart(path))
        self.assertEqual(_first_media_atom(path), "moov")
        self.assertFalse(m4a_needs_faststart(path))
        self.assertFalse(ensure_m4a_faststart(path))

    def test_sermon_helper_updates_original_size(self):
        path = Path(self.media_directory.name) / "upload.m4a"
        _write_sine_m4a(path, faststart=False)
        sermon = Sermon.objects.create(
            owner=self.user,
            source_draft_id="faststart-source",
            captured_at=timezone.now(),
            duration_seconds=1,
            audio=SimpleUploadedFile(
                "upload.m4a",
                path.read_bytes(),
                content_type="audio/mp4",
            ),
            audio_mime_type="audio/mp4",
            audio_size_bytes=path.stat().st_size,
        )

        changed = ensure_sermon_listen_audio_faststart(sermon)

        sermon.refresh_from_db()
        self.assertTrue(changed)
        self.assertFalse(m4a_needs_faststart(Path(sermon.audio.path)))
        self.assertEqual(sermon.audio_size_bytes, Path(sermon.audio.path).stat().st_size)

    def test_management_command_dry_run(self):
        path = Path(self.media_directory.name) / "cmd.m4a"
        _write_sine_m4a(path, faststart=False)
        sermon = Sermon.objects.create(
            owner=self.user,
            source_draft_id="faststart-cmd",
            captured_at=timezone.now(),
            duration_seconds=1,
            audio=SimpleUploadedFile(
                "cmd.m4a",
                path.read_bytes(),
                content_type="audio/mp4",
            ),
            audio_mime_type="audio/mp4",
            audio_size_bytes=path.stat().st_size,
        )
        stdout = StringIO()

        call_command("faststart_sermon_audio", "--dry-run", stdout=stdout)

        self.assertIn(str(sermon.id), stdout.getvalue())
        self.assertTrue(m4a_needs_faststart(Path(sermon.audio.path)))
