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

Return the zero-based indexes of segments that are clearly incidental side
conversation from the pew or gallery — speech that was never meant to be part of
the service or Sermon (for example "sit down kids", whispered logistics, or
unrelated chatter).

Keep every segment that could be intentional service speech:
- preaching, teaching, prayer, liturgy, scripture reading, announcements,
  congregational responses, singing introductions, or blessing
- any speech that might be the preacher/reader even if labeled as multiple speakers
- secondary speakers who appear to be part of the service
- anything uncertain

Do not drop a segment only because its speaker label differs from the majority.
When unsure, keep the segment.

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
