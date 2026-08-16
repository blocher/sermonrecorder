"""Prefix sermon audio with a tail copy so ASR can warm up before the real start."""

from __future__ import annotations

import subprocess
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from django.conf import settings

from .processing import PermanentProcessingError, RawTranscriptSegment


def effective_warmup_seconds(duration_seconds: float) -> float:
    """Seconds of tail audio to prefix, capped to the recording length."""
    configured = float(getattr(settings, "TRANSCRIPTION_WARMUP_SECONDS", 0) or 0)
    if configured <= 0 or duration_seconds <= 0:
        return 0.0
    return min(configured, float(duration_seconds))


def strip_warmup_from_raw_segments(
    segments: Sequence[RawTranscriptSegment],
    warmup_seconds: float,
) -> tuple[RawTranscriptSegment, ...]:
    """Drop the prefixed tail and shift remaining times back to the original audio."""
    if warmup_seconds <= 0:
        return tuple(segments)
    clipped: list[RawTranscriptSegment] = []
    for segment in segments:
        if segment.end_seconds <= warmup_seconds:
            continue
        start = max(segment.start_seconds, warmup_seconds) - warmup_seconds
        end = segment.end_seconds - warmup_seconds
        if end <= start:
            continue
        clipped.append(replace(segment, start_seconds=start, end_seconds=end))
    return tuple(clipped)


def strip_warmup_from_speechmatics_payload(
    payload: dict[str, Any],
    warmup_seconds: float,
) -> dict[str, Any]:
    """Shift Speechmatics word timings past the prefixed tail."""
    if warmup_seconds <= 0:
        return payload
    results: list[dict[str, Any]] = []
    for item in payload.get("results") or []:
        start = float(item.get("start_time") or 0)
        end = float(item.get("end_time") or start)
        if end <= warmup_seconds:
            continue
        updated = dict(item)
        updated["start_time"] = max(start, warmup_seconds) - warmup_seconds
        updated["end_time"] = end - warmup_seconds
        results.append(updated)
    return {**payload, "results": results}


def write_warmup_prefixed_audio(
    source_path: Path,
    destination: Path,
    *,
    duration_seconds: float,
    warmup_seconds: float,
) -> None:
    """Write ``[last warmup_seconds] + original`` to ``destination``."""
    start = max(0.0, float(duration_seconds) - float(warmup_seconds))
    _run_ffmpeg(
        (
            settings.FFMPEG_BINARY,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source_path),
            "-filter_complex",
            (
                f"[0:a]atrim=start={start},asetpts=PTS-STARTPTS[tail];"
                "[tail][0:a]concat=n=2:v=0:a=1[out]"
            ),
            "-map",
            "[out]",
            "-vn",
            str(destination),
        )
    )


@contextmanager
def warmed_transcription_audio(
    source_path: Path,
    duration_seconds: float,
) -> Iterator[tuple[Path, float]]:
    """Yield a temp file with the tail prefixed, plus the warmup length to clip later."""
    warmup_seconds = effective_warmup_seconds(duration_seconds)
    if warmup_seconds <= 0:
        yield source_path, 0.0
        return
    suffix = source_path.suffix or ".m4a"
    with TemporaryDirectory(prefix="pewcorder-warmup-") as directory:
        destination = Path(directory) / f"warmed{suffix}"
        write_warmup_prefixed_audio(
            source_path,
            destination,
            duration_seconds=duration_seconds,
            warmup_seconds=warmup_seconds,
        )
        yield destination, warmup_seconds


def _run_ffmpeg(command: tuple[str, ...]) -> None:
    try:
        subprocess.run(command, check=True, capture_output=True)
    except FileNotFoundError as error:
        raise PermanentProcessingError(
            "ffmpeg is required to prepare Sermon recordings for transcription."
        ) from error
    except subprocess.CalledProcessError as error:
        details = error.stderr.decode(errors="replace").strip()
        raise PermanentProcessingError(
            f"The Sermon audio could not be prepared for transcription: {details}"
        ) from error
