"""Loudness-normalize derived Sermon playback audio."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from .audio_duration import probe_audio_duration_seconds
from .audio_files import save_playback_m4a
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
    """Write a loudness-normalized AAC copy to ``playback_audio``.

    Uses existing playback audio as the source when present (e.g. after
    isolation); otherwise loudnorms the original upload into a new playback
    file. Never modifies the original ``audio`` upload.

    Returns True when the playback file was rewritten. Skips when already
    normalized unless ``force`` is set.
    """
    if sermon.audio_normalized_at is not None and not force:
        return False

    try:
        if sermon.playback_audio:
            source_path = Path(sermon.playback_audio.path)
        else:
            source_path = sermon.original_audio_path()
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
                "-movflags",
                "+faststart",
                str(temp_path),
            )
        )
        if temp_path.stat().st_size <= 0:
            raise PermanentProcessingError(
                "Normalized Sermon playback audio was empty."
            )

        save_playback_m4a(sermon, temp_path)
        sermon.audio_normalized_at = timezone.now()
        try:
            sermon.duration_seconds = probe_audio_duration_seconds(temp_path)
        except PermanentProcessingError:
            logger.warning(
                "Normalized sermon %s but could not re-probe duration.",
                sermon.id,
            )
        sermon.save(
            update_fields=(
                "playback_audio",
                "playback_audio_mime_type",
                "playback_audio_size_bytes",
                "audio_normalized_at",
                "duration_seconds",
                "updated_at",
            )
        )
        return True
    finally:
        if temp_path.exists():
            temp_path.unlink()
