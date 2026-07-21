from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User

from .models import (
    Reflection,
    ScriptureReference,
    Sermon,
    StudyArtifact,
    TagSuggestion,
    Transcript,
)


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
        self.transcript = Transcript.objects.create(
            sermon=self.sermon,
            text="First segment. Second segment.",
            segments=[
                {"start_seconds": 0, "end_seconds": 5, "text": "First segment."},
                {"start_seconds": 5, "end_seconds": 10, "text": "Second segment."},
            ],
        )
        TagSuggestion.objects.create(
            sermon=self.sermon,
            name="Grace",
            normalized_name="grace",
            sort_order=0,
        )
        TagSuggestion.objects.create(
            sermon=self.sermon,
            name="Hope",
            normalized_name="hope",
            sort_order=1,
        )
        ScriptureReference.objects.create(
            sermon=self.sermon,
            book="Luke",
            chapter_start=15,
            verse_start=11,
            verse_end=32,
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

    def test_owner_edits_transcript_words_without_changing_timestamps(self):
        url = f"/api/sermons/{self.sermon.id}/transcript/"
        self.client.force_authenticate(user=self.user)
        response = self.client.patch(
            url,
            {
                "segments": [
                    {"start_seconds": 0, "text": "Corrected first segment."},
                    {"start_seconds": 5, "text": "Corrected second segment."},
                ]
            },
            format="json",
        )
        changed_timestamp = self.client.patch(
            url,
            {
                "segments": [
                    {"start_seconds": 1, "text": "Moved."},
                    {"start_seconds": 5, "text": "Second."},
                ]
            },
            format="json",
        )
        self.client.force_authenticate(user=self.other_user)
        private = self.client.patch(
            url,
            {"segments": [{"start_seconds": 0, "text": "Intrusion"}]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(changed_timestamp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(private.status_code, status.HTTP_404_NOT_FOUND)
        self.transcript.refresh_from_db()
        self.assertEqual(
            self.transcript.text,
            "Corrected first segment. Corrected second segment.",
        )
        self.assertEqual(self.transcript.segments[0]["end_seconds"], 5)

    def test_owner_replaces_ai_suggestions_with_curated_tags(self):
        url = f"/api/sermons/{self.sermon.id}/tags/"
        self.client.force_authenticate(user=self.user)

        response = self.client.put(
            url,
            {"tags": ["  Mercy  and   justice ", "Prayer"]},
            format="json",
        )
        detail = self.client.get(f"/api/sermons/{self.sermon.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"tags": ["Mercy and justice", "Prayer"]})
        self.assertEqual(
            list(
                TagSuggestion.objects.filter(sermon=self.sermon).values_list(
                    "name",
                    "normalized_name",
                    "sort_order",
                )
            ),
            [
                ("Mercy and justice", "mercy and justice", 0),
                ("Prayer", "prayer", 1),
            ],
        )
        self.assertEqual(
            detail.data["tag_suggestions"],
            ["Mercy and justice", "Prayer"],
        )

        cleared = self.client.put(url, {"tags": []}, format="json")
        self.assertEqual(cleared.status_code, status.HTTP_200_OK)
        self.assertFalse(TagSuggestion.objects.filter(sermon=self.sermon).exists())

    def test_tag_curation_rejects_duplicates_and_nonowners(self):
        url = f"/api/sermons/{self.sermon.id}/tags/"
        self.client.force_authenticate(user=self.user)
        duplicate = self.client.put(
            url,
            {"tags": ["Mercy", " mercy "]},
            format="json",
        )
        too_many = self.client.put(
            url,
            {"tags": [f"Tag {index}" for index in range(13)]},
            format="json",
        )
        too_long = self.client.put(
            url,
            {"tags": ["t" * 81]},
            format="json",
        )
        self.client.force_authenticate(user=self.other_user)
        private = self.client.put(
            url,
            {"tags": ["Intrusion"]},
            format="json",
        )
        self.sermon.processing_status = Sermon.ProcessingStatus.UPLOADED
        self.sermon.save(update_fields=("processing_status", "updated_at"))
        self.client.force_authenticate(user=self.user)
        not_ready = self.client.put(
            url,
            {"tags": ["Too early"]},
            format="json",
        )

        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(too_many.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(too_long.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(private.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(not_ready.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            list(
                TagSuggestion.objects.filter(sermon=self.sermon).values_list(
                    "name",
                    flat=True,
                )
            ),
            ["Grace", "Hope"],
        )

    def test_owner_replaces_scripture_references_with_structured_corrections(self):
        url = f"/api/sermons/{self.sermon.id}/scripture-references/"
        self.client.force_authenticate(user=self.user)
        response = self.client.put(
            url,
            {
                "scripture_references": [
                    {
                        "book": "  Romans ",
                        "chapter_start": 8,
                        "verse_start": 31,
                        "chapter_end": 8,
                        "verse_end": 39,
                    },
                    {
                        "book": "Psalm",
                        "chapter_start": 23,
                    },
                ]
            },
            format="json",
        )
        detail = self.client.get(f"/api/sermons/{self.sermon.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [
                reference["display"]
                for reference in response.data["scripture_references"]
            ],
            ["Romans 8:31–39", "Psalm 23"],
        )
        self.assertIsNone(response.data["scripture_references"][0]["chapter_end"])
        self.assertEqual(
            [reference["display"] for reference in detail.data["scripture_references"]],
            ["Romans 8:31–39", "Psalm 23"],
        )
        self.assertEqual(
            list(
                ScriptureReference.objects.filter(sermon=self.sermon).values_list(
                    "book",
                    "sort_order",
                )
            ),
            [("Romans", 0), ("Psalm", 1)],
        )

        cleared = self.client.put(
            url,
            {"scripture_references": []},
            format="json",
        )
        self.assertEqual(cleared.status_code, status.HTTP_200_OK)
        self.assertFalse(ScriptureReference.objects.filter(sermon=self.sermon).exists())

    def test_scripture_reference_edits_are_validated_and_owner_only(self):
        url = f"/api/sermons/{self.sermon.id}/scripture-references/"
        invalid_range = {
            "book": "John",
            "chapter_start": 3,
            "verse_start": 16,
            "verse_end": 10,
        }
        self.client.force_authenticate(user=self.user)
        invalid = self.client.put(
            url,
            {"scripture_references": [invalid_range]},
            format="json",
        )
        duplicate = self.client.put(
            url,
            {
                "scripture_references": [
                    {
                        "book": "Luke",
                        "chapter_start": 15,
                        "verse_start": 11,
                        "verse_end": 32,
                    },
                    {
                        "book": " luke ",
                        "chapter_start": 15,
                        "verse_start": 11,
                        "verse_end": 32,
                    },
                ]
            },
            format="json",
        )
        self.client.force_authenticate(user=self.other_user)
        private = self.client.put(
            url,
            {"scripture_references": []},
            format="json",
        )

        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(private.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            ScriptureReference.objects.get(sermon=self.sermon).book,
            "Luke",
        )
