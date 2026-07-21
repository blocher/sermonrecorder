from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User

from .models import Reflection, Sermon, StudyArtifact


class SermonEditingApiTests(APITestCase):
    def setUp(self):
        self.media_directory = TemporaryDirectory()
        self.settings_override = override_settings(MEDIA_ROOT=self.media_directory.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(self.media_directory.cleanup)
        self.user = User.objects.create_user(
            email="editor@example.com",
            password="safe-test-password",
        )
        self.other_user = User.objects.create_user(
            email="other-editor@example.com",
            password="safe-test-password",
        )
        self.sermon = Sermon.objects.create(
            owner=self.user,
            source_draft_id="editable",
            captured_at=timezone.now(),
            duration_seconds=120,
            audio=SimpleUploadedFile(
                "editable.m4a",
                b"audio",
                content_type="audio/mp4",
            ),
            audio_mime_type="audio/mp4",
            audio_size_bytes=5,
            processing_status=Sermon.ProcessingStatus.READY,
        )
        self.artifact = StudyArtifact.objects.create(
            sermon=self.sermon,
            kind=StudyArtifact.Kind.SHORT_SUMMARY,
            content="Generated summary.",
        )

    def test_owner_can_edit_one_study_artifact_without_replacing_others(self):
        other_artifact = StudyArtifact.objects.create(
            sermon=self.sermon,
            kind=StudyArtifact.Kind.OUTLINE,
            content="Generated outline.",
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            f"/api/sermons/{self.sermon.id}/artifacts/{self.artifact.kind}/",
            {"content": "My corrected summary."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.artifact.refresh_from_db()
        other_artifact.refresh_from_db()
        self.assertEqual(self.artifact.content, "My corrected summary.")
        self.assertIsNotNone(self.artifact.edited_at)
        self.assertEqual(other_artifact.content, "Generated outline.")

    def test_artifact_edits_are_nonempty_and_owner_only(self):
        self.client.force_authenticate(user=self.user)
        empty = self.client.patch(
            f"/api/sermons/{self.sermon.id}/artifacts/{self.artifact.kind}/",
            {"content": "  "},
            format="json",
        )
        self.client.force_authenticate(user=self.other_user)
        private = self.client.patch(
            f"/api/sermons/{self.sermon.id}/artifacts/{self.artifact.kind}/",
            {"content": "Intrusion"},
            format="json",
        )

        self.assertEqual(empty.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(private.status_code, status.HTTP_404_NOT_FOUND)
        self.artifact.refresh_from_db()
        self.assertEqual(self.artifact.content, "Generated summary.")

    def test_reflections_are_created_updated_and_returned_only_to_the_owner(self):
        self.client.force_authenticate(user=self.user)
        created = self.client.post(
            f"/api/sermons/{self.sermon.id}/reflections/",
            {
                "prompt": "Where is grace asking me to act?",
                "content": "I need to make room before I feel ready.",
            },
            format="json",
        )
        reflection_id = created.data["id"]
        updated = self.client.patch(
            f"/api/sermons/{self.sermon.id}/reflections/{reflection_id}/",
            {"content": "I will make room before I feel ready."},
            format="json",
        )
        detail = self.client.get(f"/api/sermons/{self.sermon.id}/")

        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(updated.status_code, status.HTTP_200_OK)
        self.assertEqual(
            detail.data["reflections"][0]["content"],
            "I will make room before I feel ready.",
        )

        self.client.force_authenticate(user=self.other_user)
        private_list = self.client.get(f"/api/sermons/{self.sermon.id}/reflections/")
        private_update = self.client.patch(
            f"/api/sermons/{self.sermon.id}/reflections/{reflection_id}/",
            {"content": "Intrusion"},
            format="json",
        )

        self.assertEqual(private_list.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(private_update.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            Reflection.objects.get().content, "I will make room before I feel ready."
        )
