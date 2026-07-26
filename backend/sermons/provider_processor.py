from typing import Protocol

from .audio_duration import probe_audio_duration_seconds
from .models import Sermon
from .openai_transcriber import CleanedTranscript, OpenAIDiarizedTranscriber
from .playback_audio import normalize_sermon_playback_audio
from .processing import PermanentProcessingError, ProcessedSermon, RelatedSermonResult
from .simpleai_artifacts import GeneratedArtifacts, SimpleAIArtifactGenerator


class Transcriber(Protocol):
    def transcribe(self, sermon: Sermon) -> CleanedTranscript: ...


class ArtifactGenerator(Protocol):
    def generate(self, transcript: CleanedTranscript) -> GeneratedArtifacts: ...


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
    ):
        self.transcriber = transcriber or OpenAIDiarizedTranscriber()
        self.artifact_generator = artifact_generator or SimpleAIArtifactGenerator()

    def process(self, sermon: Sermon) -> ProcessedSermon:
        normalize_sermon_playback_audio(sermon)
        _sync_duration_from_audio(sermon)
        transcript = self.transcriber.transcribe(sermon)
        artifacts = self.artifact_generator.generate(transcript)
        return ProcessedSermon(
            title=artifacts.title,
            transcript_text=transcript.text,
            transcript_segments=transcript.segments,
            study_artifacts=artifacts.study_artifacts,
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
