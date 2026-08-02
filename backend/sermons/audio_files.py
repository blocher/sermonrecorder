"""Helpers for derived Sermon playback audio files."""

from __future__ import annotations

from pathlib import Path

from django.core.files import File

from .models import Sermon


def _replace_audio_file(field, filename: str, encoded_path: Path) -> None:
    old_name = field.name if field else ""
    storage = field.storage
    with encoded_path.open("rb") as handle:
        field.save(filename, File(handle), save=False)
    if old_name and old_name != field.name:
        storage.delete(old_name)


def save_playback_m4a(sermon: Sermon, encoded_path: Path) -> None:
    """Store normalized original audio as the default playback copy.

    Leaves the original ``audio`` upload untouched.
    """
    _replace_audio_file(sermon.playback_audio, "playback.m4a", encoded_path)
    sermon.playback_audio_mime_type = "audio/mp4"
    sermon.playback_audio_size_bytes = encoded_path.stat().st_size


def save_isolated_m4a(sermon: Sermon, encoded_path: Path) -> None:
    """Store normalized voice-isolated audio as an optional listen copy."""
    _replace_audio_file(sermon.isolated_audio, "isolated.m4a", encoded_path)
    sermon.isolated_audio_mime_type = "audio/mp4"
    sermon.isolated_audio_size_bytes = encoded_path.stat().st_size
