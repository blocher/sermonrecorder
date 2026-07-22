from typing import Protocol

from .models import Sermon
from .openai_transcriber import CleanedTranscript, OpenAIDiarizedTranscriber
from .processing import ProcessedSermon, RelatedSermonResult
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
        )
