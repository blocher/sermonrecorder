"""Regenerate only Magisterium-backed Study artifacts from an existing Transcript."""

from __future__ import annotations

from django.db import transaction

from .magisterium_enrichment import MagisteriumArtifacts, MagisteriumEnricher
from .models import Sermon, StudyArtifact, Transcript
from .openai_transcriber import CleanedTranscript
from .processing import (
    PermanentProcessingError,
    RawTranscriptSegment,
    TranscriptSegment,
)


def cleaned_transcript_from_sermon(sermon: Sermon) -> CleanedTranscript:
    try:
        transcript = sermon.transcript
    except Transcript.DoesNotExist as error:
        raise PermanentProcessingError(
            "This Sermon has no Transcript to enrich with Magisterium AI."
        ) from error

    text = (transcript.text or "").strip()
    if not text:
        raise PermanentProcessingError(
            "This Sermon has an empty Transcript; Magisterium AI cannot run."
        )

    segments = tuple(
        TranscriptSegment(
            start_seconds=float(segment["start_seconds"]),
            end_seconds=float(segment["end_seconds"]),
            text=str(segment["text"]).strip(),
        )
        for segment in transcript.segments or ()
        if isinstance(segment, dict)
        and str(segment.get("text") or "").strip()
    )
    if not segments:
        raise PermanentProcessingError(
            "This Sermon has no Transcript segments; Magisterium AI cannot run."
        )

    raw_segments = tuple(
        RawTranscriptSegment(
            speaker=str(segment.get("speaker") or "").strip() or "Speaker",
            start_seconds=float(segment["start_seconds"]),
            end_seconds=float(segment["end_seconds"]),
            text=str(segment["text"]).strip(),
        )
        for segment in transcript.raw_segments or ()
        if isinstance(segment, dict)
        and str(segment.get("text") or "").strip()
    )
    return CleanedTranscript(
        text=text,
        segments=segments,
        raw_segments=raw_segments,
    )


def persist_magisterium_artifacts(
    sermon: Sermon,
    artifacts: MagisteriumArtifacts,
) -> None:
    with transaction.atomic():
        for artifact in artifacts.study_artifacts:
            if artifact.kind not in {
                StudyArtifact.Kind.RELATED_SOURCES,
                StudyArtifact.Kind.DOCTRINAL_REVIEW,
            }:
                continue
            content = artifact.content.strip()
            if not content:
                raise PermanentProcessingError(
                    "Magisterium regeneration returned an empty Study artifact."
                )
            StudyArtifact.objects.update_or_create(
                sermon=sermon,
                kind=artifact.kind,
                defaults={
                    "content": content,
                    "edited_at": None,
                },
            )


def regenerate_magisterium_artifacts(
    sermon: Sermon,
    *,
    enricher: MagisteriumEnricher | None = None,
) -> None:
    transcript = cleaned_transcript_from_sermon(sermon)
    result = (enricher or MagisteriumEnricher()).enrich(transcript)
    persist_magisterium_artifacts(sermon, result)
