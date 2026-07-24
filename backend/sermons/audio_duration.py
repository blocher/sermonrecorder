import json
import subprocess
from pathlib import Path

from django.conf import settings

from .processing import PermanentProcessingError


def probe_audio_duration_seconds(path: Path | str) -> int:
    """Return the rounded duration of an audio file via ffprobe."""
    audio_path = Path(path)
    command = (
        getattr(settings, "FFPROBE_BINARY", "ffprobe"),
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(audio_path),
    )
    try:
        completed = subprocess.run(command, check=True, capture_output=True)
    except FileNotFoundError as error:
        raise PermanentProcessingError(
            "ffprobe is required to measure Sermon audio duration."
        ) from error
    except subprocess.CalledProcessError as error:
        details = error.stderr.decode(errors="replace").strip()
        raise PermanentProcessingError(
            f"The Sermon audio duration could not be measured: {details}"
        ) from error

    try:
        payload = json.loads(completed.stdout.decode())
        duration = float(payload["format"]["duration"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise PermanentProcessingError(
            "The Sermon audio duration could not be measured."
        ) from error

    if duration <= 0:
        raise PermanentProcessingError(
            "The Sermon audio contains no measurable duration."
        )
    return max(1, round(duration))
