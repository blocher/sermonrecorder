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
        self.settings_override = override_settings(
            MEDIA_ROOT=self.media_directory.name,
            SERMON_AUDIO_X_ACCEL_PREFIX="",
        )
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

    def test_head_request_is_allowed_for_media_probes(self):
        parsed = urlsplit(self.audio_url())
        self.client.force_authenticate(user=None)

        response = self.client.head(f"{parsed.path}?{parsed.query}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Accept-Ranges"], "bytes")
        self.assertEqual(response["Content-Type"], "audio/mp4")
        self.assertEqual(response["Content-Length"], str(len(self.audio)))

    def test_tiny_prefix_range_returns_exactly_the_requested_bytes(self):
        parsed = urlsplit(self.audio_url())
        self.client.force_authenticate(user=None)

        response = self.client.get(
            f"{parsed.path}?{parsed.query}",
            HTTP_RANGE="bytes=0-1",
        )

        self.assertEqual(response.status_code, status.HTTP_206_PARTIAL_CONTENT)
        body = b"".join(response.streaming_content)
        self.assertEqual(body, self.audio[:2])
        self.assertEqual(
            response["Content-Range"],
            f"bytes 0-1/{len(self.audio)}",
        )

    @override_settings(
        SERMON_AUDIO_X_ACCEL_PREFIX="/_protected_sermon_audio/",
    )
    def test_production_delegates_authorized_audio_to_nginx(self):
        parsed = urlsplit(self.audio_url())
        self.client.force_authenticate(user=None)

        response = self.client.get(
            f"{parsed.path}?{parsed.query}",
            HTTP_RANGE="bytes=0-1",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.content, b"")
        self.assertEqual(
            response["X-Accel-Redirect"],
            f"/_protected_sermon_audio/{self.sermon.audio.name}",
        )
        self.assertEqual(response["Accept-Ranges"], "bytes")
        self.assertEqual(response["Content-Type"], "audio/mp4")

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

    def test_variant_urls_stream_original_playback_and_isolated_audio(self):
        playback = b"playback-audio-bytes!!"
        isolated = b"isolated-audio-bytes!!"
        self.sermon.playback_audio = SimpleUploadedFile(
            "playback.m4a",
            playback,
            content_type="audio/mp4",
        )
        self.sermon.playback_audio_mime_type = "audio/mp4"
        self.sermon.playback_audio_size_bytes = len(playback)
        self.sermon.isolated_audio = SimpleUploadedFile(
            "isolated.m4a",
            isolated,
            content_type="audio/mp4",
        )
        self.sermon.isolated_audio_mime_type = "audio/mp4"
        self.sermon.isolated_audio_size_bytes = len(isolated)
        self.sermon.save(
            update_fields=(
                "playback_audio",
                "playback_audio_mime_type",
                "playback_audio_size_bytes",
                "isolated_audio",
                "isolated_audio_mime_type",
                "isolated_audio_size_bytes",
                "updated_at",
            )
        )

        self.client.force_authenticate(user=self.user)
        detail = self.client.get(f"/api/sermons/{self.sermon.id}/")
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertTrue(detail.data["has_playback_audio"])
        self.assertTrue(detail.data["has_isolated_audio"])
        self.assertIn("variant=original", detail.data["original_audio_url"])
        self.assertIn("variant=playback", detail.data["playback_audio_url"])
        self.assertIn("variant=isolated", detail.data["isolated_audio_url"])

        self.client.force_authenticate(user=None)
        original = urlsplit(detail.data["original_audio_url"])
        normalized = urlsplit(detail.data["playback_audio_url"])
        isolated_variant = urlsplit(detail.data["isolated_audio_url"])
        default = urlsplit(detail.data["audio_url"])

        original_response = self.client.get(f"{original.path}?{original.query}")
        playback_response = self.client.get(f"{normalized.path}?{normalized.query}")
        isolated_response = self.client.get(
            f"{isolated_variant.path}?{isolated_variant.query}"
        )
        default_response = self.client.get(f"{default.path}?{default.query}")

        self.assertEqual(original_response.status_code, status.HTTP_200_OK)
        self.assertEqual(b"".join(original_response.streaming_content), self.audio)
        self.assertEqual(playback_response.status_code, status.HTTP_200_OK)
        self.assertEqual(b"".join(playback_response.streaming_content), playback)
        self.assertEqual(isolated_response.status_code, status.HTTP_200_OK)
        self.assertEqual(b"".join(isolated_response.streaming_content), isolated)
        self.assertEqual(default_response.status_code, status.HTTP_200_OK)
        self.assertEqual(b"".join(default_response.streaming_content), playback)

        self.sermon.playback_audio.delete(save=False)
        self.sermon.playback_audio = None
        self.sermon.playback_audio_mime_type = ""
        self.sermon.playback_audio_size_bytes = None
        self.sermon.save(
            update_fields=(
                "playback_audio",
                "playback_audio_mime_type",
                "playback_audio_size_bytes",
                "updated_at",
            )
        )
        self.client.force_authenticate(user=self.user)
        detail_without = self.client.get(f"/api/sermons/{self.sermon.id}/")
        original_without = urlsplit(detail_without.data["original_audio_url"])
        self.client.force_authenticate(user=None)
        gone = self.client.get(
            f"{original_without.path}?"
            f"{original_without.query.replace('variant=original', 'variant=playback')}"
        )
        self.assertEqual(gone.status_code, status.HTTP_404_NOT_FOUND)

