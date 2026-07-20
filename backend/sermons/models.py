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
