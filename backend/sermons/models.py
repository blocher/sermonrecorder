import uuid
from pathlib import Path

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


def sermon_audio_path(sermon: "Sermon", filename: str) -> str:
    suffix = Path(filename).suffix.lower()[:10] or ".audio"
    return f"sermons/{sermon.owner_id}/{sermon.id}/original{suffix}"


class Sermon(models.Model):
    class ProcessingStatus(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sermons",
    )
    source_draft_id = models.CharField(max_length=128)
    captured_at = models.DateTimeField()
    duration_seconds = models.PositiveIntegerField(
        validators=(MinValueValidator(1), MaxValueValidator(12 * 60 * 60))
    )
    audio = models.FileField(upload_to=sermon_audio_path, max_length=500)
    audio_mime_type = models.CharField(max_length=120)
    audio_size_bytes = models.PositiveBigIntegerField()
    processing_status = models.CharField(
        max_length=20,
        choices=ProcessingStatus,
        default=ProcessingStatus.UPLOADED,
    )
    processing_error = models.TextField(blank=True)
    processing_attempts = models.PositiveSmallIntegerField(default=0)
    processing_claim_id = models.CharField(max_length=255, blank=True)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    processing_finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-captured_at",)
        constraints = (
            models.UniqueConstraint(
                fields=("owner", "source_draft_id"),
                name="unique_owner_source_draft",
            ),
        )
        indexes = (
            models.Index(fields=("owner", "processing_status")),
            models.Index(fields=("owner", "captured_at")),
        )

    def __str__(self) -> str:
        return f"{self.owner} · {self.captured_at:%Y-%m-%d %H:%M}"


class Transcript(models.Model):
    sermon = models.OneToOneField(
        Sermon,
        on_delete=models.CASCADE,
        related_name="transcript",
        primary_key=True,
    )
    text = models.TextField()
    segments = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class StudyArtifact(models.Model):
    class Kind(models.TextChoices):
        SHORT_SUMMARY = "short_summary", "Short summary"
        LONG_SUMMARY = "long_summary", "Long summary"
        OUTLINE = "outline", "Outline"
        ADULT_DISCUSSION_QUESTIONS = (
            "adult_discussion_questions",
            "Adult discussion questions",
        )
        KIDS_DISCUSSION_QUESTIONS = (
            "kids_discussion_questions",
            "Kids discussion questions",
        )

    sermon = models.ForeignKey(
        Sermon,
        on_delete=models.CASCADE,
        related_name="study_artifacts",
    )
    kind = models.CharField(max_length=40, choices=Kind)
    content = models.TextField()
    edited_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("kind",)
        constraints = (
            models.UniqueConstraint(
                fields=("sermon", "kind"),
                name="unique_sermon_study_artifact_kind",
            ),
        )


class ScriptureReference(models.Model):
    sermon = models.ForeignKey(
        Sermon,
        on_delete=models.CASCADE,
        related_name="scripture_references",
    )
    book = models.CharField(max_length=64)
    chapter_start = models.PositiveSmallIntegerField()
    verse_start = models.PositiveSmallIntegerField(null=True, blank=True)
    chapter_end = models.PositiveSmallIntegerField(null=True, blank=True)
    verse_end = models.PositiveSmallIntegerField(null=True, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "id")


class TagSuggestion(models.Model):
    sermon = models.ForeignKey(
        Sermon,
        on_delete=models.CASCADE,
        related_name="tag_suggestions",
    )
    name = models.CharField(max_length=80)
    normalized_name = models.CharField(max_length=80)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "id")
        constraints = (
            models.UniqueConstraint(
                fields=("sermon", "normalized_name"),
                name="unique_sermon_tag_suggestion",
            ),
        )


class RelatedSermon(models.Model):
    sermon = models.ForeignKey(
        Sermon,
        on_delete=models.CASCADE,
        related_name="related_sermons",
    )
    related_sermon = models.ForeignKey(
        Sermon,
        on_delete=models.CASCADE,
        related_name="suggested_for_sermons",
    )
    score = models.FloatField()
    reason = models.CharField(max_length=255, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "id")
        constraints = (
            models.UniqueConstraint(
                fields=("sermon", "related_sermon"),
                name="unique_related_sermon_suggestion",
            ),
            models.CheckConstraint(
                condition=~models.Q(sermon=models.F("related_sermon")),
                name="related_sermon_cannot_reference_itself",
            ),
        )


class Reflection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sermon = models.ForeignKey(
        Sermon,
        on_delete=models.CASCADE,
        related_name="reflections",
    )
    prompt = models.TextField(blank=True)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("created_at",)
