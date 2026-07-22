from django.db import transaction

from .models import (
    RelatedSermon,
    ScriptureReference,
    Sermon,
    StudyArtifact,
    TagSuggestion,
    Transcript,
)
from .processing import PermanentProcessingError, ProcessedSermon
from .scripture import normalize_scripture_reference
from .tagging import normalize_tag


def _normalized_tag(name: str) -> tuple[str, str]:
    try:
        return normalize_tag(name)
    except ValueError as error:
        raise PermanentProcessingError(
            "A suggested Tag is empty or too long."
        ) from error


def _validate_result(sermon: Sermon, result: ProcessedSermon) -> None:
    title = " ".join(result.title.split())
    if not title or len(title) > Sermon._meta.get_field("title").max_length:
        raise PermanentProcessingError(
            "The processor returned an invalid Sermon title."
        )
    if not result.transcript_text.strip():
        raise PermanentProcessingError("The processor returned an empty Transcript.")
    if not result.transcript_segments:
        raise PermanentProcessingError("The processor returned no Transcript segments.")

    previous_start = -1.0
    for segment in result.transcript_segments:
        if (
            segment.start_seconds < 0
            or segment.end_seconds <= segment.start_seconds
            or segment.start_seconds < previous_start
            or not segment.text.strip()
        ):
            raise PermanentProcessingError(
                "The processor returned an invalid Transcript segment."
            )
        previous_start = segment.start_seconds

    artifact_kinds = [artifact.kind for artifact in result.study_artifacts]
    if len(artifact_kinds) != len(set(artifact_kinds)):
        raise PermanentProcessingError(
            "The processor returned duplicate Study artifacts."
        )
    if set(artifact_kinds) != set(StudyArtifact.Kind.values):
        raise PermanentProcessingError(
            "The processor did not return every required Study artifact."
        )
    if any(not artifact.content.strip() for artifact in result.study_artifacts):
        raise PermanentProcessingError(
            "The processor returned an empty Study artifact."
        )
    quotations = next(
        artifact.content.splitlines()
        for artifact in result.study_artifacts
        if artifact.kind == StudyArtifact.Kind.QUOTATIONS
    )
    normalized_transcript = " ".join(result.transcript_text.split())
    normalized_quotations = [" ".join(quotation.split()) for quotation in quotations]
    if (
        not 1 <= len(normalized_quotations) <= 3
        or len(normalized_quotations) != len(set(normalized_quotations))
        or any(
            not quotation or quotation not in normalized_transcript
            for quotation in normalized_quotations
        )
    ):
        raise PermanentProcessingError(
            "Sermon quotations must contain one to three unique, verbatim Transcript excerpts."
        )

    normalized_tags = [_normalized_tag(name)[1] for name in result.tag_suggestions]
    if len(normalized_tags) != len(set(normalized_tags)):
        raise PermanentProcessingError(
            "The processor returned duplicate Tag suggestions."
        )

    for reference in result.scripture_references:
        try:
            normalize_scripture_reference(
                book=reference.book,
                chapter_start=reference.chapter_start,
                verse_start=reference.verse_start,
                chapter_end=reference.chapter_end,
                verse_end=reference.verse_end,
            )
        except ValueError as error:
            raise PermanentProcessingError(
                "The processor returned an invalid Scripture reference."
            ) from error

    related_ids = [related.sermon_id for related in result.related_sermons]
    if sermon.id in related_ids or len(related_ids) != len(set(related_ids)):
        raise PermanentProcessingError(
            "Related Sermons must be unique and cannot reference the Sermon itself."
        )
    if any(
        related.score < 0 or related.score > 1 or len(related.reason) > 255
        for related in result.related_sermons
    ):
        raise PermanentProcessingError(
            "The processor returned an invalid Related Sermon."
        )

    owner_related_ids = set(
        Sermon.objects.filter(
            owner=sermon.owner,
            id__in=related_ids,
        ).values_list("id", flat=True)
    )
    if owner_related_ids != set(related_ids):
        raise PermanentProcessingError(
            "Related Sermons must belong to the same Congregant."
        )


def persist_processed_sermon(sermon: Sermon, result: ProcessedSermon) -> None:
    segments = [
        {
            "start_seconds": segment.start_seconds,
            "end_seconds": segment.end_seconds,
            "text": segment.text.strip(),
        }
        for segment in result.transcript_segments
    ]

    with transaction.atomic():
        locked_sermon = Sermon.objects.select_for_update().get(id=sermon.id)
        _validate_result(locked_sermon, result)
        generated_title = " ".join(result.title.split())
        if (
            locked_sermon.title_edited_at is None
            and locked_sermon.title != generated_title
        ):
            locked_sermon.title = generated_title
            locked_sermon.save(update_fields=("title", "updated_at"))
        Transcript.objects.update_or_create(
            sermon=locked_sermon,
            defaults={
                "text": result.transcript_text.strip(),
                "segments": segments,
            },
        )

        for artifact in result.study_artifacts:
            StudyArtifact.objects.update_or_create(
                sermon=locked_sermon,
                kind=artifact.kind,
                defaults={
                    "content": artifact.content.strip(),
                    "edited_at": None,
                },
            )

        locked_sermon.scripture_references.all().delete()
        normalized_references = [
            normalize_scripture_reference(
                book=reference.book,
                chapter_start=reference.chapter_start,
                verse_start=reference.verse_start,
                chapter_end=reference.chapter_end,
                verse_end=reference.verse_end,
            )
            for reference in result.scripture_references
        ]
        ScriptureReference.objects.bulk_create(
            ScriptureReference(
                sermon=locked_sermon,
                book=reference["book"],
                chapter_start=reference["chapter_start"],
                verse_start=reference["verse_start"],
                chapter_end=reference["chapter_end"],
                verse_end=reference["verse_end"],
                sort_order=sort_order,
            )
            for sort_order, reference in enumerate(normalized_references)
        )

        locked_sermon.tag_suggestions.all().delete()
        TagSuggestion.objects.bulk_create(
            TagSuggestion(
                sermon=locked_sermon,
                name=display_name,
                normalized_name=normalized_name,
                sort_order=sort_order,
            )
            for sort_order, (display_name, normalized_name) in enumerate(
                _normalized_tag(name) for name in result.tag_suggestions
            )
        )

        locked_sermon.related_sermons.all().delete()
        RelatedSermon.objects.bulk_create(
            RelatedSermon(
                sermon=locked_sermon,
                related_sermon_id=related.sermon_id,
                score=related.score,
                reason=related.reason,
                sort_order=sort_order,
            )
            for sort_order, related in enumerate(result.related_sermons)
        )
