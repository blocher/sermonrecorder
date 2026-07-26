"""ElevenLabs Voice Isolator for cleaner pew-recording playback."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import httpx
from django.conf import settings
from django.utils import timezone

from .audio_duration import probe_audio_duration_seconds
from .models import Sermon
from .processing import PermanentProcessingError, RetryableProcessingError

logger = logging.getLogger(__name__)

ELEVENLABS_AUDIO_ISOLATION_PATH = "/v1/audio-isolation"
# Official Voice Isolator cap: 1 hour / 500 MB.
ELEVENLABS_MAX_ISOLATION_SECONDS = 60 * 60
ELEVENLABS_MAX_ISOLATION_BYTES = 500 * 1024 * 1024


def isolate_sermon_voice(sermon: Sermon, *, force: bool = False) -> bool:
    """Replace stored audio with an ElevenLabs voice-isolated copy.

    Returns True when the file was rewritten. Skips when already isolated
    unless ``force`` is set. Clears ``audio_normalized_at`` so loudnorm can
    run on the cleaned speech. Skips (without failing) when the recording
    exceeds ElevenLabs' 1-hour / 500 MB isolation limits.
    """
    if not settings.SERMON_VOICE_ISOLATION_ENABLED:
        return False
    if sermon.audio_isolated_at is not None and not force:
        return False
    if not settings.ELEVENLABS_API_KEY:
        raise PermanentProcessingError(
            "ELEVENLABS_API_KEY is required for Sermon voice isolation."
        )

    try:
        source_path = Path(sermon.audio.path)
    except (NotImplementedError, ValueError) as error:
        raise PermanentProcessingError(
            "The configured audio storage cannot provide a local worker path."
        ) from error
    if not source_path.is_file():
        raise PermanentProcessingError("The Sermon audio file is missing on disk.")

    if (
        sermon.duration_seconds > ELEVENLABS_MAX_ISOLATION_SECONDS
        or sermon.audio_size_bytes > ELEVENLABS_MAX_ISOLATION_BYTES
        or source_path.stat().st_size > ELEVENLABS_MAX_ISOLATION_BYTES
    ):
        logger.warning(
            "Skipping ElevenLabs isolation for sermon %s "
            "(duration=%ss size=%s exceeds 1h/500MB limit).",
            sermon.id,
            sermon.duration_seconds,
            sermon.audio_size_bytes,
        )
        return False

    isolated_bytes = _call_elevenlabs_isolation(source_path)
    raw_temp = source_path.with_name(f".{source_path.name}.isolated.raw")
    m4a_temp = source_path.with_name(f".{source_path.name}.isolated.tmp.m4a")
    try:
        raw_temp.write_bytes(isolated_bytes)
        _encode_playback_m4a(raw_temp, m4a_temp)
        if m4a_temp.stat().st_size <= 0:
            raise PermanentProcessingError("Isolated Sermon audio was empty.")

        final_path = source_path.with_suffix(".m4a")
        m4a_temp.replace(final_path)
        if final_path != source_path and source_path.exists():
            source_path.unlink()

        relative_name = Path(sermon.audio.name).with_suffix(".m4a").as_posix()
        sermon.audio.name = relative_name
        sermon.audio_mime_type = "audio/mp4"
        sermon.audio_size_bytes = final_path.stat().st_size
        sermon.audio_isolated_at = timezone.now()
        # Isolation changes levels; require a fresh loudnorm pass.
        sermon.audio_normalized_at = None
        try:
            sermon.duration_seconds = probe_audio_duration_seconds(final_path)
        except PermanentProcessingError:
            logger.warning(
                "Isolated sermon %s but could not re-probe duration.",
                sermon.id,
            )
        sermon.save(
            update_fields=(
                "audio",
                "audio_mime_type",
                "audio_size_bytes",
                "audio_isolated_at",
                "audio_normalized_at",
                "duration_seconds",
                "updated_at",
            )
        )
        return True
    finally:
        for path in (raw_temp, m4a_temp):
            if path.exists():
                path.unlink()


def _call_elevenlabs_isolation(source_path: Path) -> bytes:
    url = f"{settings.ELEVENLABS_API_BASE_URL.rstrip('/')}{ELEVENLABS_AUDIO_ISOLATION_PATH}"
    headers = {"xi-api-key": settings.ELEVENLABS_API_KEY}
    timeout = httpx.Timeout(settings.ELEVENLABS_ISOLATION_TIMEOUT_SECONDS)
    try:
        with source_path.open("rb") as audio:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    url,
                    headers=headers,
                    files={
                        "audio": (
                            source_path.name,
                            audio,
                            "application/octet-stream",
                        )
                    },
                    data={"file_format": "other"},
                )
    except httpx.TimeoutException as error:
        raise RetryableProcessingError(
            "ElevenLabs voice isolation timed out."
        ) from error
    except httpx.HTTPError as error:
        raise RetryableProcessingError(
            f"ElevenLabs voice isolation request failed: {error}"
        ) from error

    if response.status_code in {408, 429} or response.status_code >= 500:
        raise RetryableProcessingError(
            f"ElevenLabs voice isolation temporary error ({response.status_code})."
        )
    if response.status_code == 401:
        raise PermanentProcessingError(
            "ElevenLabs rejected ELEVENLABS_API_KEY (unauthorized)."
        )
    if response.status_code >= 400:
        detail = response.text.strip()[:500]
        raise PermanentProcessingError(
            f"ElevenLabs voice isolation failed ({response.status_code}): {detail}"
        )
    if not response.content:
        raise PermanentProcessingError("ElevenLabs returned empty isolated audio.")
    return response.content


def _encode_playback_m4a(source_path: Path, destination_path: Path) -> None:
    command = (
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
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        str(destination_path),
    )
    try:
        subprocess.run(command, check=True, capture_output=True)
    except FileNotFoundError as error:
        raise PermanentProcessingError(
            "ffmpeg is required to encode isolated Sermon playback audio."
        ) from error
    except subprocess.CalledProcessError as error:
        details = error.stderr.decode(errors="replace").strip()
        raise PermanentProcessingError(
            f"Isolated Sermon audio could not be encoded: {details}"
        ) from error
