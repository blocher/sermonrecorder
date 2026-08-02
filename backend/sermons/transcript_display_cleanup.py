"""AI polish for Congregant-facing Transcript display (not used by Study prompts)."""

from collections.abc import Callable, Sequence
from typing import Any

from pydantic import BaseModel, Field
from simpleai import SimpleAIException, run_prompt
from simpleai.exceptions import ModelResolutionError, SettingsError

from .processing import TranscriptSegment


class DisplayCleanupOutput(BaseModel):
    segments: list[str] = Field(default_factory=list)


def polish_display_segments(
    segments: Sequence[TranscriptSegment],
    *,
    runner: Callable[..., Any] = run_prompt,
) -> tuple[str, tuple[TranscriptSegment, ...]]:
    """Return polished display text/segments; fail open to the original segments."""
    if not segments:
        return "", ()

    numbered = "\n".join(
        f"[{index}] {segment.start_seconds:.2f}-{segment.end_seconds:.2f}: {segment.text}"
        for index, segment in enumerate(segments)
    )
    prompt = f"""
You are polishing a cleaned Christian sermon Transcript for comfortable reading
and listening along. Side conversations are already removed. Your job is display
cleanup only — Study notes and other AI tools will keep using the unpolished
original wording.

Rewrite each numbered segment in order. Return exactly one polished string per
input segment, same count and order.

Do:
- Fix obvious ASR mistakes, capitalization, and punctuation
- Smooth filler such as um, uh, you know, when they add no meaning
- Improve line breaks inside a segment when a sentence clearly continues
- Keep the preacher's meaning, names, Scripture references, and distinctive voice

Do not:
- Merge, split, omit, or reorder segments
- Invent content that is not implied by the segment
- Soften theological claims or change who is speaking
- Add headings, bullets, or commentary

Segments:
{numbered}
""".strip()

    try:
        result = runner(
            prompt,
            output_format=DisplayCleanupOutput,
            model=None,
        )
    except (SettingsError, ModelResolutionError, SimpleAIException):
        # Display polish is optional; never block a Ready Sermon on it.
        return _fallback(segments)

    polished = [
        " ".join(str(text).split()).strip()
        for text in result.segments
        if isinstance(text, str)
    ]
    if len(polished) != len(segments) or any(not text for text in polished):
        return _fallback(segments)

    display_segments = tuple(
        TranscriptSegment(
            start_seconds=segment.start_seconds,
            end_seconds=segment.end_seconds,
            text=text,
        )
        for segment, text in zip(segments, polished, strict=True)
    )
    display_text = " ".join(segment.text for segment in display_segments)
    return display_text, display_segments


def _fallback(
    segments: Sequence[TranscriptSegment],
) -> tuple[str, tuple[TranscriptSegment, ...]]:
    kept = tuple(segments)
    return " ".join(segment.text for segment in kept), kept
