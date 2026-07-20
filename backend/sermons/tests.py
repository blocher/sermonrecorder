from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils.http import urlencode
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User

from .models import Sermon


def sermon_audio(contents: bytes = b"captured sermon") -> SimpleUploadedFile:
    return SimpleUploadedFile("sermon.m4a", contents, content_type="audio/mp4")


class SermonApiTests(APITestCase):
    def setUp(self):
        self.media_directory = TemporaryDirectory()
        self.settings_override = override_settings(MEDIA_ROOT=self.media_directory.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(self.media_directory.cleanup)
        self.user = User.objects.create_user(
            email="owner@example.com", password="strong-password"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com", password="strong-password"
        )

    def upload(self, source_draft_id: str, *, user=None):
        self.client.force_authenticate(user=user or self.user)
        return self.client.post(
            "/api/sermons/",
            {
                "source_draft_id": source_draft_id,
                "captured_at": "2026-07-20T15:30:00Z",
                "duration_seconds": 2700,
                "audio": sermon_audio(),
            },
            format="multipart",
        )

    def test_upload_creates_an_owned_sermon_waiting_for_processing(self):
        response = self.upload("draft-on-this-device")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        sermon = Sermon.objects.get()
        self.assertEqual(sermon.owner, self.user)
        self.assertEqual(sermon.processing_status, Sermon.ProcessingStatus.UPLOADED)
        self.assertEqual(sermon.audio_mime_type, "audio/mp4")
        self.assertEqual(sermon.audio_size_bytes, len(b"captured sermon"))

    def test_native_upload_metadata_can_arrive_as_query_parameters(self):
        self.client.force_authenticate(user=self.user)
        query = urlencode(
            {
                "source_draft_id": "native-draft",
                "captured_at": "2026-07-20T15:30:00Z",
                "duration_seconds": 2700,
            }
        )

        response = self.client.post(
            f"/api/sermons/?{query}",
            {"audio": sermon_audio()},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["source_draft_id"], "native-draft")

    def test_repeating_a_draft_upload_is_idempotent(self):
        first = self.upload("same-draft")
        second = self.upload("same-draft")

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data["id"], second.data["id"])
        self.assertEqual(Sermon.objects.count(), 1)

    def test_congregants_only_list_their_own_sermons(self):
        mine = self.upload("my-draft")
        self.upload("their-draft", user=self.other_user)
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/sermons/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([sermon["id"] for sermon in response.data], [mine.data["id"]])

    def test_processing_failures_hide_internal_error_details(self):
        uploaded = self.upload("failed-processing")
        sermon = Sermon.objects.get(id=uploaded.data["id"])
        sermon.processing_status = Sermon.ProcessingStatus.FAILED
        sermon.processing_error = "provider-secret: internal stack detail"
        sermon.save(
            update_fields=("processing_status", "processing_error", "updated_at")
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/sermons/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("processing_error", response.data[0])
        self.assertEqual(
            response.data[0]["processing_message"],
            "Processing could not finish. The recording is still safe.",
        )

    def test_upload_requires_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.post(
            "/api/sermons/",
            {
                "source_draft_id": "anonymous-draft",
                "captured_at": "2026-07-20T15:30:00Z",
                "duration_seconds": 10,
                "audio": sermon_audio(),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_upload_rejects_non_audio_files(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/sermons/",
            {
                "source_draft_id": "not-audio",
                "captured_at": "2026-07-20T15:30:00Z",
                "duration_seconds": 10,
                "audio": SimpleUploadedFile(
                    "notes.txt", b"not audio", content_type="text/plain"
                ),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("audio", response.data)
