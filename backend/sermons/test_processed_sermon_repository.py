from dataclasses import replace

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from accounts.models import User

from .models import (
    RelatedSermon,
    ScriptureReference,
    Sermon,
    StudyArtifact,
    TagSuggestion,
    Transcript,
)
from .processed_sermon_repository import persist_processed_sermon
from .processing import (
    PermanentProcessingError,
    ProcessedSermon,
    RelatedSermonResult,
    ScriptureReferenceResult,
    StudyArtifactResult,
    TranscriptSegment,
)


def complete_result() -> ProcessedSermon:
    return ProcessedSermon(
        transcript_text="The first cleaned Transcript.",
        transcript_segments=(
            TranscriptSegment(
                start_seconds=1.5,
                end_seconds=8,
                text="The first cleaned Transcript.",
            ),
        ),
        study_artifacts=tuple(
            StudyArtifactResult(kind=kind, content=f"First {kind}.")
            for kind in StudyArtifact.Kind.values
        ),
        scripture_references=(
            ScriptureReferenceResult(
                book="Luke",
                chapter_start=15,
                verse_start=11,
                verse_end=32,
            ),
        ),
        tag_suggestions=("Grace", "Homecoming"),
    )


class ProcessedSermonRepositoryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="artifacts@example.com",
            password="safe-test-password",
        )
        self.sermon = self.create_sermon(self.user, "source")

    def create_sermon(self, owner: User, source_draft_id: str) -> Sermon:
        return Sermon.objects.create(
            owner=owner,
            source_draft_id=source_draft_id,
            captured_at=timezone.now(),
            duration_seconds=120,
            audio=SimpleUploadedFile(
                f"{source_draft_id}.m4a",
                b"test audio",
                content_type="audio/mp4",
            ),
            audio_mime_type="audio/mp4",
            audio_size_bytes=10,
        )

    def test_incomplete_results_are_rejected_without_partial_content(self):
        incomplete = replace(
            complete_result(),
            study_artifacts=complete_result().study_artifacts[:-1],
        )

        with self.assertRaisesMessage(
            PermanentProcessingError,
            "every required Study artifact",
        ):
            persist_processed_sermon(self.sermon, incomplete)

        self.assertFalse(Transcript.objects.filter(sermon=self.sermon).exists())
        self.assertFalse(StudyArtifact.objects.filter(sermon=self.sermon).exists())

    def test_reprocessing_atomically_replaces_generated_content(self):
        persist_processed_sermon(self.sermon, complete_result())
        artifact = StudyArtifact.objects.get(
            sermon=self.sermon,
            kind=StudyArtifact.Kind.SHORT_SUMMARY,
        )
        artifact.content = "Congregant edit"
        artifact.edited_at = timezone.now()
        artifact.save(update_fields=("content", "edited_at", "updated_at"))
        replacement = replace(
            complete_result(),
            transcript_text="The replacement Transcript.",
            transcript_segments=(
                TranscriptSegment(
                    start_seconds=0,
                    end_seconds=6,
                    text="The replacement Transcript.",
                ),
            ),
            study_artifacts=tuple(
                StudyArtifactResult(kind=kind, content=f"Replacement {kind}.")
                for kind in StudyArtifact.Kind.values
            ),
            scripture_references=(),
            tag_suggestions=("Renewal",),
        )

        persist_processed_sermon(self.sermon, replacement)

        self.assertEqual(
            Transcript.objects.get(sermon=self.sermon).text,
            "The replacement Transcript.",
        )
        artifact.refresh_from_db()
        self.assertEqual(artifact.content, "Replacement short_summary.")
        self.assertIsNone(artifact.edited_at)
        self.assertEqual(
            StudyArtifact.objects.filter(sermon=self.sermon).count(),
            len(StudyArtifact.Kind.values),
        )
        self.assertFalse(ScriptureReference.objects.filter(sermon=self.sermon).exists())
        self.assertEqual(
            list(
                TagSuggestion.objects.filter(sermon=self.sermon).values_list(
                    "name", flat=True
                )
            ),
            ["Renewal"],
        )

    def test_related_sermons_cannot_cross_congregant_libraries(self):
        related = self.create_sermon(self.user, "related")
        other_user = User.objects.create_user(
            email="other-artifacts@example.com",
            password="safe-test-password",
        )
        private_sermon = self.create_sermon(other_user, "private")
        result = replace(
            complete_result(),
            related_sermons=(
                RelatedSermonResult(
                    sermon_id=related.id,
                    score=0.92,
                    reason="Shared themes",
                ),
            ),
        )
        persist_processed_sermon(self.sermon, result)

        self.assertEqual(
            RelatedSermon.objects.get(sermon=self.sermon).related_sermon,
            related,
        )

        cross_library_result = replace(
            result,
            transcript_text="This must not be persisted.",
            related_sermons=(
                RelatedSermonResult(
                    sermon_id=private_sermon.id,
                    score=0.8,
                ),
            ),
        )
        with self.assertRaisesMessage(
            PermanentProcessingError,
            "same Congregant",
        ):
            persist_processed_sermon(self.sermon, cross_library_result)

        self.assertEqual(
            Transcript.objects.get(sermon=self.sermon).text,
            "The first cleaned Transcript.",
        )
