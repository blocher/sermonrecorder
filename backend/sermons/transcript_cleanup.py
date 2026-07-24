from collections.abc import Callable, Sequence
from typing import Any

from pydantic import BaseModel, Field
from simpleai import SimpleAIException, run_prompt
from simpleai.exceptions import ModelResolutionError, SettingsError

from .processing import (
    PermanentProcessingError,
    RawTranscriptSegment,
    RetryableProcessingError,
    TranscriptSegment,
)

# Hard caps so cleanup never strips substantial preaching by accident.
MAX_INCIDENTAL_SEGMENT_SECONDS = 8.0
MAX_INCIDENTAL_DROP_RATIO = 0.12


class TranscriptCleanupOutput(BaseModel):
    incidental_segment_indexes: list[int] = Field(default_factory=list)


def intentional_service_segments(
    raw_segments: Sequence[RawTranscriptSegment],
    *,
    runner: Callable[..., Any] = run_prompt,
) -> tuple[TranscriptSegment, ...]:
    """Keep intentional/uncertain speech; drop only high-confidence incidental pew talk."""
    if not raw_segments:
        return ()

    numbered = "\n".join(
        f"[{index}] speaker={segment.speaker} "
        f"{segment.start_seconds:.2f}-{segment.end_seconds:.2f}: {segment.text}"
        for index, segment in enumerate(raw_segments)
    )
    prompt = f"""
You are cleaning a diarized pew recording of a Christian worship service for a
Congregant's private sermon journal.

Return the zero-based indexes of segments that are CLEARLY incidental side
conversation from the pew or gallery — speech that was never meant to be part of
the service or Sermon.

Examples that MAY be dropped (only when clearly incidental):
- "sit down kids", whispered logistics, seating chatter, unrelated small talk

NEVER drop segments that could be intentional service speech, including:
- preaching, teaching, prayer, liturgy, scripture reading, announcements
- congregational responses ("Amen", "And also with you", creed lines, sung text)
- singing introductions, blessings, absolution, dismissal
- short liturgical formulae ("In the name of the Father…", "The Lord be with you")
- any speech that might be the preacher, priest, deacon, reader, or cantor
- secondary speakers who appear to be part of the service
- anything uncertain, overlapping, or hard to classify

Do not drop a segment only because its speaker label differs from the majority,
because it is short, or because diarization split one speaker into many labels.
When unsure, keep the segment. Prefer leaving occasional pew chatter over
losing any service speech.

Segments:
{numbered}
""".strip()

    try:
        result = runner(
            prompt,
            output_format=TranscriptCleanupOutput,
            model=None,
        )
    except (SettingsError, ModelResolutionError) as error:
        raise PermanentProcessingError(str(error)) from error
    except SimpleAIException as error:
        raise RetryableProcessingError(str(error)) from error

    drop = {
        index
        for index in result.incidental_segment_indexes
        if isinstance(index, int) and 0 <= index < len(raw_segments)
    }
    # Long turns are almost never incidental pew chatter.
    drop = {
        index
        for index in drop
        if (
            raw_segments[index].end_seconds - raw_segments[index].start_seconds
            <= MAX_INCIDENTAL_SEGMENT_SECONDS
        )
    }
    total_duration = sum(
        max(0.0, segment.end_seconds - segment.start_seconds)
        for segment in raw_segments
    )
    dropped_duration = sum(
        max(0.0, raw_segments[index].end_seconds - raw_segments[index].start_seconds)
        for index in drop
    )
    # Fail open when cleanup would remove a meaningful share of speech time.
    if total_duration > 0 and dropped_duration / total_duration > MAX_INCIDENTAL_DROP_RATIO:
        drop = set()

    kept = tuple(
        TranscriptSegment(
            start_seconds=segment.start_seconds,
            end_seconds=segment.end_seconds,
            text=segment.text,
        )
        for index, segment in enumerate(raw_segments)
        if index not in drop
    )
    # Fail open: never discard an entire Transcript because cleanup was overzealous.
    if not kept:
        return tuple(
            TranscriptSegment(
                start_seconds=segment.start_seconds,
                end_seconds=segment.end_seconds,
                text=segment.text,
            )
            for segment in raw_segments
        )
    return kept
