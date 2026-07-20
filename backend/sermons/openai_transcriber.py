from collections import defaultdict
from dataclasses import dataclass

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
from .models import Sermon
from .processing import (
    PermanentProcessingError,
    RetryableProcessingError,
    TranscriptSegment,
)


@dataclass(frozen=True)
class CleanedTranscript:
    text: str
    segments: tuple[TranscriptSegment, ...]


def predominant_speaker_segments(
    segments: list[TranscriptionDiarizedSegment],
    *,
    offset_seconds: float = 0,
) -> tuple[TranscriptSegment, ...]:
    durations: dict[str, float] = defaultdict(float)
    for segment in segments:
        durations[segment.speaker] += max(0, segment.end - segment.start)
    if not durations:
        return ()

    predominant_speaker = max(durations, key=durations.get)
    return tuple(
        TranscriptSegment(
            start_seconds=offset_seconds + segment.start,
            end_seconds=offset_seconds + segment.end,
            text=segment.text.strip(),
        )
        for segment in segments
        if segment.speaker == predominant_speaker
        and segment.end > segment.start
        and segment.text.strip()
    )


class OpenAIDiarizedTranscriber:
    def __init__(self, client: OpenAI | None = None):
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
        cleaned_segments: list[TranscriptSegment] = []

        try:
            with prepared_audio_chunks(sermon) as chunks:
                for chunk in chunks:
                    with chunk.path.open("rb") as audio:
                        transcription = self.client.audio.transcriptions.create(
                            model=settings.OPENAI_TRANSCRIPTION_MODEL,
                            file=audio,
                            response_format="diarized_json",
                            chunking_strategy="auto",
                        )
                    cleaned_segments.extend(
                        predominant_speaker_segments(
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

        if not cleaned_segments:
            raise PermanentProcessingError(
                "No predominant-speaker speech was found in the Sermon audio."
            )

        return CleanedTranscript(
            text=" ".join(segment.text for segment in cleaned_segments),
            segments=tuple(cleaned_segments),
        )
