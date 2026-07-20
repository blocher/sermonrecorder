from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from django.conf import settings
from django.utils.module_loading import import_string

from .models import Sermon


class SermonProcessingError(Exception):
    """An expected failure while preparing a Sermon."""


class RetryableProcessingError(SermonProcessingError):
    """A temporary failure that should be retried."""


class PermanentProcessingError(SermonProcessingError):
    """A failure that requires configuration or Congregant action."""


@dataclass(frozen=True)
class TranscriptSegment:
    start_seconds: float
    end_seconds: float
    text: str


@dataclass(frozen=True)
class StudyArtifactResult:
    kind: str
    content: str


@dataclass(frozen=True)
class ScriptureReferenceResult:
    book: str
    chapter_start: int
    verse_start: int | None = None
    chapter_end: int | None = None
    verse_end: int | None = None


@dataclass(frozen=True)
class RelatedSermonResult:
    sermon_id: UUID
    score: float
    reason: str = ""


@dataclass(frozen=True)
class ProcessedSermon:
    transcript_text: str
    transcript_segments: tuple[TranscriptSegment, ...]
    study_artifacts: tuple[StudyArtifactResult, ...]
    scripture_references: tuple[ScriptureReferenceResult, ...] = ()
    tag_suggestions: tuple[str, ...] = ()
    related_sermons: tuple[RelatedSermonResult, ...] = ()


class SermonProcessor(Protocol):
    def process(self, sermon: Sermon) -> ProcessedSermon:
        """Return every result required for the Sermon to become Ready."""


class UnconfiguredSermonProcessor:
    def process(self, sermon: Sermon) -> ProcessedSermon:
        raise PermanentProcessingError(
            "No Sermon processor is configured. Set SERMON_PROCESSOR before running workers."
        )


def get_sermon_processor() -> SermonProcessor:
    processor_class = import_string(settings.SERMON_PROCESSOR)
    return processor_class()
