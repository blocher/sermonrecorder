from typing import Protocol

from django.conf import settings
from django.utils.module_loading import import_string

from .audio_duration import probe_audio_duration_seconds
from .audio_faststart import ensure_sermon_listen_audio_faststart
from .magisterium_enrichment import (
    MagisteriumArtifacts,
    MagisteriumEnricher,
    without_magisterium_artifacts,
)
from .models import Sermon
from .openai_transcriber import CleanedTranscript
from .playback_audio import normalize_sermon_playback_audio
from .processing import PermanentProcessingError, ProcessedSermon, RelatedSermonResult
from .simpleai_artifacts import GeneratedArtifacts, SimpleAIArtifactGenerator
from .transcript_display_cleanup import polish_display_segments
from .voice_isolation import isolate_sermon_voice


class Transcriber(Protocol):
    def transcribe(self, sermon: Sermon) -> CleanedTranscript: ...


class ArtifactGenerator(Protocol):
    def generate(self, transcript: CleanedTranscript) -> GeneratedArtifacts: ...


class MagisteriumArtifactEnricher(Protocol):
    def enrich(self, transcript: CleanedTranscript) -> MagisteriumArtifacts: ...


def get_sermon_transcriber() -> Transcriber:
    transcriber_class = import_string(settings.SERMON_TRANSCRIBER)
    return transcriber_class()


def _related_sermons(
    sermon: Sermon,
    tag_suggestions: tuple[str, ...],
) -> tuple[RelatedSermonResult, ...]:
    normalized_tags = {
        " ".join(tag.split()).casefold() for tag in tag_suggestions if tag.strip()
    }
    if not normalized_tags:
        return ()

    matches: list[tuple[float, Sermon, set[str]]] = []
    candidates = (
        Sermon.objects.filter(
            owner=sermon.owner,
            processing_status=Sermon.ProcessingStatus.READY,
        )
        .exclude(id=sermon.id)
        .prefetch_related("tag_suggestions")
    )
    for candidate in candidates:
        candidate_tags = {
            suggestion.normalized_name for suggestion in candidate.tag_suggestions.all()
        }
        shared_tags = normalized_tags & candidate_tags
        if not shared_tags:
            continue
        score = len(shared_tags) / len(normalized_tags | candidate_tags)
        matches.append((score, candidate, shared_tags))

    matches.sort(key=lambda match: (-match[0], -match[1].captured_at.timestamp()))
    return tuple(
        RelatedSermonResult(
            sermon_id=candidate.id,
            score=score,
            reason=f"Shared Tags: {', '.join(sorted(shared_tags))}",
        )
        for score, candidate, shared_tags in matches[:5]
    )


class ProviderSermonProcessor:
    def __init__(
        self,
        transcriber: Transcriber | None = None,
        artifact_generator: ArtifactGenerator | None = None,
        magisterium_enricher: MagisteriumArtifactEnricher | None = None,
    ):
        self.transcriber = transcriber or get_sermon_transcriber()
        self.artifact_generator = artifact_generator or SimpleAIArtifactGenerator()
        self.magisterium_enricher = magisterium_enricher or MagisteriumEnricher()

    def process(self, sermon: Sermon) -> ProcessedSermon:
        # iOS Safari cannot play progressive M4A when moov is after mdat.
        ensure_sermon_listen_audio_faststart(sermon)
        normalize_sermon_playback_audio(sermon)
        isolate_sermon_voice(sermon)
        ensure_sermon_listen_audio_faststart(sermon)
        _sync_duration_from_audio(sermon)
        transcript = self.transcriber.transcribe(sermon)
        # Study / Magisterium prompts must use the unpolished intentional-service text.
        artifacts = self.artifact_generator.generate(transcript)
        magisterium = self.magisterium_enricher.enrich(transcript)
        display_text, display_segments = polish_display_segments(transcript.segments)
        study_artifacts = (
            without_magisterium_artifacts(artifacts.study_artifacts)
            + magisterium.study_artifacts
        )
        return ProcessedSermon(
            title=artifacts.title,
            transcript_text=transcript.text,
            transcript_segments=transcript.segments,
            study_artifacts=study_artifacts,
            scripture_references=artifacts.scripture_references,
            tag_suggestions=artifacts.tag_suggestions,
            related_sermons=_related_sermons(sermon, artifacts.tag_suggestions),
            raw_transcript_segments=tuple(
                {
                    "speaker": segment.speaker,
                    "start_seconds": segment.start_seconds,
                    "end_seconds": segment.end_seconds,
                    "text": segment.text,
                }
                for segment in getattr(transcript, "raw_segments", ())
            ),
            display_transcript_text=display_text,
            display_transcript_segments=display_segments,
        )


def _sync_duration_from_audio(sermon: Sermon) -> None:
    try:
        audio_path = sermon.audio.path
    except (NotImplementedError, ValueError):
        return
    try:
        measured = probe_audio_duration_seconds(audio_path)
    except PermanentProcessingError:
        return
    if measured != sermon.duration_seconds:
        sermon.duration_seconds = measured
        sermon.save(update_fields=("duration_seconds", "updated_at"))
