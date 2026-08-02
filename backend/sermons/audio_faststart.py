"""Ensure AAC/M4A listen files are faststart (moov before mdat) for iOS Safari."""

from __future__ import annotations

import logging
import struct
import subprocess
from pathlib import Path

from django.conf import settings

from .models import Sermon
from .processing import PermanentProcessingError

logger = logging.getLogger(__name__)

# Remux only — no re-encode. Safe for originals and derived playback copies.
_FASTSTART_MOVFLAGS = "+faststart"


def m4a_moov_exclusive_end(path: Path) -> int | None:
    """Byte offset just past the first ``moov`` atom, or None if not found early."""
    try:
        with path.open("rb") as handle:
            offset = 0
            while True:
                header = handle.read(8)
                if len(header) < 8:
                    return None
                size, atom_type = struct.unpack(">I4s", header)
                if size == 1:
                    large = handle.read(8)
                    if len(large) < 8:
                        return None
                    size = struct.unpack(">Q", large)[0]
                    header_size = 16
                elif size == 0:
                    return None
                else:
                    header_size = 8

                if size < header_size:
                    return None

                label = atom_type.decode("latin1")
                if label == "moov":
                    return offset + size
                if label == "mdat":
                    return None

                offset += size
                handle.seek(size - header_size, 1)
    except OSError:
        return None


def m4a_needs_faststart(path: Path) -> bool:
    """True when the first media atom is ``mdat`` (moov is later / at EOF)."""
    try:
        with path.open("rb") as handle:
            while True:
                header = handle.read(8)
                if len(header) < 8:
                    return False
                size, atom_type = struct.unpack(">I4s", header)
                if size == 1:
                    large = handle.read(8)
                    if len(large) < 8:
                        return False
                    size = struct.unpack(">Q", large)[0]
                    header_size = 16
                elif size == 0:
                    return False
                else:
                    header_size = 8
                if size < header_size:
                    return False
                label = atom_type.decode("latin1")
                if label == "moov":
                    return False
                if label == "mdat":
                    return True
                handle.seek(size - header_size, 1)
    except OSError:
        return False
    return False


def ensure_m4a_faststart(path: Path) -> bool:
    """Rewrite ``path`` in place with ``-movflags +faststart`` when needed.

    Returns True when the file was rewritten.
    """
    if not path.is_file():
        raise PermanentProcessingError("The audio file is missing on disk.")
    if not m4a_needs_faststart(path):
        return False

    temp_path = path.with_name(f".{path.name}.faststart.tmp.m4a")
    command = (
        settings.FFMPEG_BINARY,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(path),
        "-c",
        "copy",
        "-movflags",
        _FASTSTART_MOVFLAGS,
        str(temp_path),
    )
    try:
        subprocess.run(command, check=True, capture_output=True)
    except FileNotFoundError as error:
        raise PermanentProcessingError(
            "ffmpeg is required to prepare Sermon audio for mobile playback."
        ) from error
    except subprocess.CalledProcessError as error:
        details = error.stderr.decode(errors="replace").strip()
        raise PermanentProcessingError(
            f"Sermon audio could not be prepared for mobile playback: {details}"
        ) from error

    if temp_path.stat().st_size <= 0:
        temp_path.unlink(missing_ok=True)
        raise PermanentProcessingError("Faststart Sermon audio was empty.")

    temp_path.replace(path)
    return True


def ensure_sermon_listen_audio_faststart(sermon: Sermon) -> bool:
    """Faststart the original upload and any derived playback copy.

    Returns True when either file was rewritten.
    """
    changed = False
    try:
        original = sermon.original_audio_path()
    except (NotImplementedError, ValueError) as error:
        raise PermanentProcessingError(
            "The configured audio storage cannot provide a local worker path."
        ) from error

    if ensure_m4a_faststart(original):
        sermon.audio_size_bytes = original.stat().st_size
        sermon.save(update_fields=("audio_size_bytes", "updated_at"))
        changed = True
        logger.info("Faststarted original audio for sermon %s", sermon.id)

    if sermon.playback_audio:
        playback_path = Path(sermon.playback_audio.path)
        if ensure_m4a_faststart(playback_path):
            sermon.playback_audio_size_bytes = playback_path.stat().st_size
            sermon.save(
                update_fields=("playback_audio_size_bytes", "updated_at")
            )
            changed = True
            logger.info("Faststarted playback audio for sermon %s", sermon.id)

    return changed
