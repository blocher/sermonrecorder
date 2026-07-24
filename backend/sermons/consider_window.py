from collections.abc import Sequence

from .processing import RawTranscriptSegment


def filter_segments_to_consider_window(
    segments: Sequence[RawTranscriptSegment],
    *,
    start_seconds: float | None,
    end_seconds: float | None,
) -> tuple[RawTranscriptSegment, ...]:
    """Keep segments that overlap the optional regenerate consider window."""
    if start_seconds is None and end_seconds is None:
        return tuple(segments)

    window_start = 0.0 if start_seconds is None else float(start_seconds)
    window_end = float("inf") if end_seconds is None else float(end_seconds)
    if window_end <= window_start:
        return ()

    return tuple(
        segment
        for segment in segments
        if segment.end_seconds > window_start and segment.start_seconds < window_end
    )
