from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User

from .models import Sermon


class PrivateSermonAudioTests(APITestCase):
    def setUp(self):
        self.media_directory = TemporaryDirectory()
        self.settings_override = override_settings(MEDIA_ROOT=self.media_directory.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(self.media_directory.cleanup)
        self.user = User.objects.create_user(
            email="private-audio@example.com",
            password="safe-test-password",
        )
        self.other_user = User.objects.create_user(
            email="other-private-audio@example.com",
            password="safe-test-password",
        )
        self.audio = b"0123456789abcdef"
        self.sermon = Sermon.objects.create(
            owner=self.user,
            source_draft_id="private-audio",
            captured_at=timezone.now(),
            duration_seconds=60,
            audio=SimpleUploadedFile(
                "sermon.m4a",
                self.audio,
                content_type="audio/mp4",
            ),
            audio_mime_type="audio/mp4",
            audio_size_bytes=len(self.audio),
        )

    def audio_url(self) -> str:
        self.client.force_authenticate(user=self.user)
        response = self.client.get(f"/api/sermons/{self.sermon.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data["audio_url"]

    def test_owner_issued_url_streams_without_exposing_a_permanent_media_path(self):
        audio_url = self.audio_url()
        parsed = urlsplit(audio_url)
        self.client.force_authenticate(user=None)

        response = self.client.get(
            f"{parsed.path}?{parsed.query}",
            HTTP_ORIGIN="capacitor://localhost",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(b"".join(response.streaming_content), self.audio)
        self.assertEqual(response["Accept-Ranges"], "bytes")
        self.assertEqual(response["Content-Type"], "audio/mp4")
        self.assertEqual(
            response["Access-Control-Allow-Origin"], "capacitor://localhost"
        )
        self.assertNotIn(self.sermon.audio.name, audio_url)

    def test_range_request_returns_only_the_requested_audio_bytes(self):
        parsed = urlsplit(self.audio_url())
        self.client.force_authenticate(user=None)

        response = self.client.get(
            f"{parsed.path}?{parsed.query}",
            HTTP_RANGE="bytes=2-5",
        )

        self.assertEqual(response.status_code, status.HTTP_206_PARTIAL_CONTENT)
        self.assertEqual(b"".join(response.streaming_content), self.audio[2:6])
        self.assertEqual(response["Content-Range"], f"bytes 2-5/{len(self.audio)}")
        self.assertEqual(response["Content-Length"], "4")

    def test_invalid_or_mismatched_audio_capabilities_are_rejected(self):
        parsed = urlsplit(self.audio_url())
        other_sermon = Sermon.objects.create(
            owner=self.other_user,
            source_draft_id="other-audio",
            captured_at=timezone.now(),
            duration_seconds=60,
            audio=SimpleUploadedFile(
                "other.m4a",
                b"other",
                content_type="audio/mp4",
            ),
            audio_mime_type="audio/mp4",
            audio_size_bytes=5,
        )
        self.client.force_authenticate(user=None)

        invalid = self.client.get(f"{parsed.path}?token=invalid")
        mismatched = self.client.get(
            f"/api/sermons/{other_sermon.id}/audio/?{parsed.query}"
        )

        self.assertEqual(invalid.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(mismatched.status_code, status.HTTP_403_FORBIDDEN)
