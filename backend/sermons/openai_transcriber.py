from dataclasses import dataclass
import json

from django.conf import settings
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    BadRequestError,
    InternalServerError,
    OpenAI,
    OpenAIError,
    RateLimitError,
)
from openai.types.audio.transcription_diarized_segment import (
    TranscriptionDiarizedSegment,
)

from .audio_chunks import prepared_audio_chunks
from .consider_window import filter_segments_to_consider_window
from .models import Sermon
from .processing import (
    PermanentProcessingError,
    RawTranscriptSegment,
    RetryableProcessingError,
    TranscriptSegment,
)
from .transcript_cleanup import intentional_service_segments


@dataclass(frozen=True)
class CleanedTranscript:
    text: str
    segments: tuple[TranscriptSegment, ...]
    raw_segments: tuple[RawTranscriptSegment, ...] = ()


def transcription_chunking_strategy() -> str:
    """JSON server_vad config for multipart uploads (nested dicts are dropped by the API)."""
    return json.dumps(
        {
            "type": "server_vad",
            "threshold": settings.OPENAI_TRANSCRIPTION_VAD_THRESHOLD,
            "prefix_padding_ms": settings.OPENAI_TRANSCRIPTION_VAD_PREFIX_PADDING_MS,
            "silence_duration_ms": settings.OPENAI_TRANSCRIPTION_VAD_SILENCE_DURATION_MS,
        }
    )


def raw_diarized_segments(
    segments: list[TranscriptionDiarizedSegment],
    *,
    offset_seconds: float = 0,
) -> tuple[RawTranscriptSegment, ...]:
    return tuple(
        RawTranscriptSegment(
            speaker=segment.speaker,
            start_seconds=offset_seconds + segment.start,
            end_seconds=offset_seconds + segment.end,
            text=segment.text.strip(),
        )
        for segment in segments
        if segment.end > segment.start and segment.text.strip()
    )


class OpenAIDiarizedTranscriber:
    def __init__(self, client: OpenAI | None = None, cleanup_runner=None):
        self.cleanup_runner = cleanup_runner
        if client is not None:
            self.client = client
            return
        if not settings.OPENAI_API_KEY:
            raise PermanentProcessingError(
                "OPENAI_API_KEY is required for Sermon transcription."
            )
        self.client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=settings.OPENAI_TRANSCRIPTION_TIMEOUT_SECONDS,
            max_retries=settings.OPENAI_TRANSCRIPTION_REQUEST_RETRIES,
        )

    def transcribe(self, sermon: Sermon) -> CleanedTranscript:
        raw_segments: list[RawTranscriptSegment] = []

        try:
            with prepared_audio_chunks(sermon) as chunks:
                for chunk in chunks:
                    with chunk.path.open("rb") as audio:
                        transcription = self.client.audio.transcriptions.create(
                            model=settings.OPENAI_TRANSCRIPTION_MODEL,
                            file=audio,
                            response_format="diarized_json",
                            chunking_strategy=transcription_chunking_strategy(),
                        )
                    raw_segments.extend(
                        raw_diarized_segments(
                            transcription.segments,
                            offset_seconds=chunk.start_seconds,
                        )
                    )
        except (
            APIConnectionError,
            APITimeoutError,
            RateLimitError,
            InternalServerError,
        ) as error:
            raise RetryableProcessingError(str(error)) from error
        except BadRequestError as error:
            raise PermanentProcessingError(str(error)) from error
        except APIStatusError as error:
            if error.status_code >= 500:
                raise RetryableProcessingError(str(error)) from error
            raise PermanentProcessingError(str(error)) from error
        except OpenAIError as error:
            raise PermanentProcessingError(str(error)) from error

        if not raw_segments:
            raise PermanentProcessingError("No speech was found in the Sermon audio.")

        considered = filter_segments_to_consider_window(
            raw_segments,
            start_seconds=sermon.consider_start_seconds,
            end_seconds=sermon.consider_end_seconds,
        )
        if not considered:
            raise PermanentProcessingError(
                "No speech was found in the selected regenerate time window."
            )

        cleanup_kwargs = {}
        if self.cleanup_runner is not None:
            cleanup_kwargs["runner"] = self.cleanup_runner
        cleaned_segments = intentional_service_segments(
            considered,
            **cleanup_kwargs,
        )
        return CleanedTranscript(
            text=" ".join(segment.text for segment in cleaned_segments),
            segments=cleaned_segments,
            # Full diarization (including outside the consider window) for owner review.
            raw_segments=tuple(raw_segments),
        )
