import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings

from .models import Sermon
from .processing import PermanentProcessingError

MAX_TRANSCRIPTION_UPLOAD_BYTES = 24 * 1024 * 1024
# Louder, clearer mono for distant pew speech before OpenAI VAD/ASR.
TRANSCRIPTION_AUDIO_FILTER = "loudnorm=I=-16:TP=-1.5:LRA=11"
TRANSCRIPTION_AUDIO_BITRATE = "64k"


@dataclass(frozen=True)
class AudioChunk:
    path: Path
    start_seconds: float


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


@contextmanager
def prepared_audio_chunks(sermon: Sermon) -> Iterator[tuple[AudioChunk, ...]]:
    try:
        source_path = Path(sermon.audio.path)
    except NotImplementedError as error:
        raise PermanentProcessingError(
            "The configured audio storage cannot provide a local worker path."
        ) from error

    chunk_seconds = settings.SERMON_TRANSCRIPTION_CHUNK_SECONDS
    with TemporaryDirectory(prefix=f"pewcorder-{sermon.id}-") as directory:
        directory_path = Path(directory)
        if (
            sermon.audio_size_bytes <= MAX_TRANSCRIPTION_UPLOAD_BYTES
            and sermon.duration_seconds <= chunk_seconds
        ):
            prepared = directory_path / "normalized.m4a"
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
                    "16000",
                    "-af",
                    TRANSCRIPTION_AUDIO_FILTER,
                    "-c:a",
                    "aac",
                    "-b:a",
                    TRANSCRIPTION_AUDIO_BITRATE,
                    str(prepared),
                )
            )
            if prepared.stat().st_size > MAX_TRANSCRIPTION_UPLOAD_BYTES:
                raise PermanentProcessingError(
                    "A prepared audio chunk still exceeds the transcription upload limit."
                )
            yield (AudioChunk(path=prepared, start_seconds=0),)
            return

        output_pattern = directory_path / "chunk-%03d.m4a"
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
                "16000",
                "-af",
                TRANSCRIPTION_AUDIO_FILTER,
                "-c:a",
                "aac",
                "-b:a",
                TRANSCRIPTION_AUDIO_BITRATE,
                "-f",
                "segment",
                "-segment_time",
                str(chunk_seconds),
                "-reset_timestamps",
                "1",
                str(output_pattern),
            )
        )

        paths = tuple(sorted(directory_path.glob("chunk-*.m4a")))
        if not paths:
            raise PermanentProcessingError(
                "The Sermon audio produced no transcription chunks."
            )
        if any(path.stat().st_size > MAX_TRANSCRIPTION_UPLOAD_BYTES for path in paths):
            raise PermanentProcessingError(
                "A prepared audio chunk still exceeds the transcription upload limit."
            )

        yield tuple(
            AudioChunk(path=path, start_seconds=index * chunk_seconds)
            for index, path in enumerate(paths)
        )
