"""Owner-facing copy for Sermon processing states.

Internal ``processing_error`` text stays on the server. These messages explain
what failed and how to recover without leaking provider secrets or stack traces.
"""

from __future__ import annotations

from .models import Sermon

_UPLOADED = "Safely uploaded and waiting to process."
_PROCESSING = "Preparing the transcript and study guide."
_READY = "Ready to revisit."
_FAILED_FALLBACK = (
    "Processing couldn't finish. Your recording is still safe — "
    "try again when you're ready."
)

# Longer / more specific patterns first.
_FAILED_PATTERNS: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        ("openai_api_key", "missing provider key", "api key"),
        "Transcription isn't configured yet. Add an OpenAI API key on the server, "
        "then try again.",
    ),
    (
        ("no predominant-speaker", "no transcription chunks", "empty transcript"),
        "We couldn't find clear sermon speech in this recording. "
        "Your audio is still saved — try again, or upload a clearer recording.",
    ),
    (
        ("ffmpeg", "could not be prepared", "exceeds the transcription upload"),
        "This recording couldn't be prepared for transcription. "
        "Your audio is still saved — try again.",
    ),
    (
        (
            "rate limit",
            "timeout",
            "connection error",
            "connection refused",
            "temporarily unavailable",
            "internal server error",
            "service unavailable",
        ),
        "The transcription service stayed unavailable. "
        "Your audio is still saved — try again in a little while.",
    ),
    (
        ("bad request", "cannot be decoded", "unsupported", "invalid file"),
        "This recording couldn't be transcribed. "
        "The audio may be damaged or in an unsupported format.",
    ),
    (
        (
            "study artifact",
            "scripture reference",
            "tag suggestion",
            "related sermon",
            "settingserror",
            "modelresolution",
        ),
        "We started processing, but the study materials couldn't be finished. "
        "Your audio is still saved — try again.",
    ),
)


def owner_facing_processing_message(
    status: str,
    processing_error: str = "",
) -> str:
    if status == Sermon.ProcessingStatus.UPLOADED:
        return _UPLOADED
    if status == Sermon.ProcessingStatus.PROCESSING:
        return _PROCESSING
    if status == Sermon.ProcessingStatus.READY:
        return _READY
    if status != Sermon.ProcessingStatus.FAILED:
        return _FAILED_FALLBACK

    haystack = processing_error.casefold()
    for needles, message in _FAILED_PATTERNS:
        if any(needle in haystack for needle in needles):
            return message
    return _FAILED_FALLBACK
