"""Helpers for derived Sermon playback audio files."""

from __future__ import annotations

from pathlib import Path

from django.core.files import File

from .models import Sermon


def save_playback_m4a(sermon: Sermon, encoded_path: Path) -> None:
    """Store ``encoded_path`` as the Sermon's derived playback copy.

    Leaves the original ``audio`` upload untouched.
    """
    with encoded_path.open("rb") as handle:
        sermon.playback_audio.save("playback.m4a", File(handle), save=False)
    sermon.playback_audio_mime_type = "audio/mp4"
    sermon.playback_audio_size_bytes = encoded_path.stat().st_size
