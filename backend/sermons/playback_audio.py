"""Loudness-normalize stored Sermon playback audio in place."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from .audio_duration import probe_audio_duration_seconds
from .models import Sermon
from .processing import PermanentProcessingError

logger = logging.getLogger(__name__)

# Match transcription target so distant pew speech is audible on playback.
PLAYBACK_AUDIO_FILTER = "loudnorm=I=-16:TP=-1.5:LRA=11"
PLAYBACK_AUDIO_BITRATE = "128k"


def _run_ffmpeg(command: tuple[str, ...]) -> None:
    try:
        subprocess.run(command, check=True, capture_output=True)
    except FileNotFoundError as error:
        raise PermanentProcessingError(
            "ffmpeg is required to normalize Sermon playback audio."
        ) from error
    except subprocess.CalledProcessError as error:
        details = error.stderr.decode(errors="replace").strip()
        raise PermanentProcessingError(
            f"The Sermon playback audio could not be normalized: {details}"
        ) from error


def normalize_sermon_playback_audio(
    sermon: Sermon,
    *,
    force: bool = False,
) -> bool:
    """Replace the stored audio with a loudness-normalized AAC copy.

    Returns True when the file was rewritten. Skips when already normalized
    unless ``force`` is set. Updates size, mime, duration, and
    ``audio_normalized_at``.
    """
    if sermon.audio_normalized_at is not None and not force:
        return False

    try:
        source_path = Path(sermon.audio.path)
    except (NotImplementedError, ValueError) as error:
        raise PermanentProcessingError(
            "The configured audio storage cannot provide a local worker path."
        ) from error

    if not source_path.is_file():
        raise PermanentProcessingError("The Sermon audio file is missing on disk.")

    temp_path = source_path.with_name(f".{source_path.name}.loudnorm.tmp.m4a")
    try:
        _run_ffmpeg(
            (
                settings.FFMPEG_BINARY,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(source_path),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "44100",
                "-af",
                PLAYBACK_AUDIO_FILTER,
                "-c:a",
                "aac",
                "-b:a",
                PLAYBACK_AUDIO_BITRATE,
                str(temp_path),
            )
        )
        if temp_path.stat().st_size <= 0:
            raise PermanentProcessingError(
                "Normalized Sermon playback audio was empty."
            )

        # Prefer a stable .m4a name for the playback asset.
        final_path = source_path.with_suffix(".m4a")
        temp_path.replace(final_path)
        if final_path != source_path and source_path.exists():
            source_path.unlink()

        relative_name = Path(sermon.audio.name).with_suffix(".m4a").as_posix()
        sermon.audio.name = relative_name
        sermon.audio_mime_type = "audio/mp4"
        sermon.audio_size_bytes = final_path.stat().st_size
        sermon.audio_normalized_at = timezone.now()
        try:
            sermon.duration_seconds = probe_audio_duration_seconds(final_path)
        except PermanentProcessingError:
            logger.warning(
                "Normalized sermon %s but could not re-probe duration.",
                sermon.id,
            )
        sermon.save(
            update_fields=(
                "audio",
                "audio_mime_type",
                "audio_size_bytes",
                "audio_normalized_at",
                "duration_seconds",
                "updated_at",
            )
        )
        return True
    finally:
        if temp_path.exists():
            temp_path.unlink()
