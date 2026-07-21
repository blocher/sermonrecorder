from tempfile import TemporaryDirectory
from urllib.parse import unquote, urlsplit

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User

from .models import (
    Church,
    Preacher,
    Reflection,
    ScriptureReference,
    Sermon,
    ShareLink,
    StudyArtifact,
    TagSuggestion,
    Transcript,
)


class SermonSharingTests(APITestCase):
    def setUp(self):
        self.media_directory = TemporaryDirectory()
        self.settings_override = override_settings(
            MEDIA_ROOT=self.media_directory.name,
            PEWCORDER_PUBLIC_WEB_URL="https://listen.example.test",
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(self.media_directory.cleanup)
        self.owner = User.objects.create_user(
            email="sharing-owner@example.com",
            password="safe-test-password",
        )
        self.other_user = User.objects.create_user(
            email="sharing-other@example.com",
            password="safe-test-password",
        )
        self.audio = b"shared-sermon-audio"
        self.church = Church.objects.create(
            owner=self.owner,
            name="Grace Parish",
        )
        self.preacher = Preacher.objects.create(
            owner=self.owner,
            name="Rev. Miriam Cho",
        )
        self.sermon = Sermon.objects.create(
            owner=self.owner,
            source_draft_id="shared-ready-sermon",
            captured_at=timezone.now(),
            duration_seconds=900,
            audio=SimpleUploadedFile(
                "sermon.m4a",
                self.audio,
                content_type="audio/mp4",
            ),
            audio_mime_type="audio/mp4",
            audio_size_bytes=len(self.audio),
            church=self.church,
            preacher=self.preacher,
            occasion_kind=Sermon.OccasionKind.SUNDAY,
            liturgical_day="Third Sunday of Ordinary Time",
            processing_status=Sermon.ProcessingStatus.READY,
        )
        Transcript.objects.create(
            sermon=self.sermon,
            text="The cleaned public Transcript.",
            segments=[
                {
                    "start_seconds": 0,
                    "end_seconds": 3,
                    "text": "The cleaned public Transcript.",
                }
            ],
        )
        StudyArtifact.objects.create(
            sermon=self.sermon,
            kind=StudyArtifact.Kind.SHORT_SUMMARY,
            content="A shareable summary.",
        )
        ScriptureReference.objects.create(
            sermon=self.sermon,
            book="Luke",
            chapter_start=14,
            verse_start=12,
            verse_end=24,
        )
        TagSuggestion.objects.create(
            sermon=self.sermon,
            name="Welcome",
            normalized_name="welcome",
        )
        Reflection.objects.create(
            sermon=self.sermon,
            prompt="What will I do?",
            content="This response is private.",
        )

    @property
    def owner_url(self) -> str:
        return f"/api/sermons/{self.sermon.id}/share/"

    def create_share_link(self) -> str:
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(self.owner_url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.data["url"]

    def public_token(self, url: str) -> str:
        return unquote(urlsplit(url).path.removeprefix("/share/"))

    def test_owner_can_create_inspect_and_revoke_one_active_link(self):
        self.client.force_authenticate(user=self.owner)
        empty = self.client.get(self.owner_url)
        created = self.client.post(self.owner_url)
        repeated = self.client.post(self.owner_url)
        inspected = self.client.get(self.owner_url)

        self.assertEqual(empty.data, {"share_link": None})
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(repeated.status_code, status.HTTP_200_OK)
        self.assertEqual(repeated.data["url"], created.data["url"])
        self.assertEqual(inspected.data["share_link"]["url"], created.data["url"])
        self.assertEqual(ShareLink.objects.filter(revoked_at=None).count(), 1)

        revoked = self.client.delete(self.owner_url)
        self.assertEqual(revoked.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ShareLink.objects.filter(revoked_at=None).exists())

        replacement = self.client.post(self.owner_url)
        self.assertEqual(replacement.status_code, status.HTTP_201_CREATED)
        self.assertNotEqual(replacement.data["url"], created.data["url"])

    def test_share_link_management_is_owner_only_and_ready_only(self):
        self.client.force_authenticate(user=None)
        unauthenticated = self.client.post(self.owner_url)
        self.client.force_authenticate(user=self.other_user)
        another_congregant = self.client.post(self.owner_url)
        Sermon.objects.filter(id=self.sermon.id).update(
            processing_status=Sermon.ProcessingStatus.PROCESSING
        )
        self.client.force_authenticate(user=self.owner)
        not_ready = self.client.post(self.owner_url)

        self.assertEqual(
            unauthenticated.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(another_congregant.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(not_ready.status_code, status.HTTP_404_NOT_FOUND)

    def test_public_link_includes_shareable_content_but_never_reflections(self):
        token = self.public_token(self.create_share_link())
        self.client.force_authenticate(user=None)

        response = self.client.get(f"/api/shares/{token}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["transcript"]["text"],
            "The cleaned public Transcript.",
        )
        self.assertEqual(
            response.data["study_artifacts"][0]["content"],
            "A shareable summary.",
        )
        self.assertEqual(
            response.data["scripture_references"][0]["display"],
            "Luke 14:12–24",
        )
        self.assertEqual(response.data["tag_suggestions"], ["Welcome"])
        self.assertEqual(response.data["church"]["name"], "Grace Parish")
        self.assertEqual(response.data["preacher"]["name"], "Rev. Miriam Cho")
        self.assertEqual(response.data["occasion_kind"], "sunday")
        self.assertEqual(
            response.data["liturgical_day"],
            "Third Sunday of Ordinary Time",
        )
        self.assertIn(f"/api/shares/{token}/audio/", response.data["audio_url"])
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertNotIn("reflections", response.data)
        self.assertNotIn("source_draft_id", response.data)
        self.assertNotIn("id", response.data)

    def test_shared_audio_supports_ranges_and_stops_immediately_on_revocation(self):
        token = self.public_token(self.create_share_link())
        self.client.force_authenticate(user=None)

        audio_response = self.client.get(
            f"/api/shares/{token}/audio/",
            HTTP_RANGE="bytes=2-7",
        )

        self.assertEqual(audio_response.status_code, status.HTTP_206_PARTIAL_CONTENT)
        self.assertEqual(
            b"".join(audio_response.streaming_content),
            self.audio[2:8],
        )
        self.assertEqual(audio_response["Cache-Control"], "private, no-store")

        self.client.force_authenticate(user=self.owner)
        self.client.delete(self.owner_url)
        self.client.force_authenticate(user=None)

        detail_after_revoke = self.client.get(f"/api/shares/{token}/")
        audio_after_revoke = self.client.get(f"/api/shares/{token}/audio/")
        self.assertEqual(detail_after_revoke.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(audio_after_revoke.status_code, status.HTTP_404_NOT_FOUND)
