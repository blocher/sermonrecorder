"""Speechmatics batch diarized transcription for Sermon pew recordings."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import httpx
from django.conf import settings

from .consider_window import filter_segments_to_consider_window
from .models import Sermon
from .openai_transcriber import CleanedTranscript
from .processing import (
    PermanentProcessingError,
    RawTranscriptSegment,
    RetryableProcessingError,
)
from .transcript_cleanup import intentional_service_segments

logger = logging.getLogger(__name__)


def speechmatics_raw_segments(payload: dict[str, Any]) -> tuple[RawTranscriptSegment, ...]:
    """Collapse Speechmatics word/punctuation results into speaker segments."""
    results = payload.get("results") or []
    segments: list[RawTranscriptSegment] = []
    current_speaker = ""
    current_start = 0.0
    current_end = 0.0
    current_parts: list[str] = []

    def flush() -> None:
        nonlocal current_speaker, current_start, current_end, current_parts
        text = " ".join(part for part in current_parts if part).strip()
        text = " ".join(text.split())
        if current_speaker and text and current_end > current_start:
            segments.append(
                RawTranscriptSegment(
                    speaker=current_speaker,
                    start_seconds=current_start,
                    end_seconds=current_end,
                    text=text,
                )
            )
        current_speaker = ""
        current_start = 0.0
        current_end = 0.0
        current_parts = []

    for item in results:
        item_type = item.get("type")
        if item_type not in {"word", "punctuation"}:
            continue
        alternatives = item.get("alternatives") or []
        if not alternatives:
            continue
        best = alternatives[0]
        content = str(best.get("content") or "").strip()
        if not content:
            continue
        speaker = str(best.get("speaker") or item.get("speaker") or "UU")
        start = float(item.get("start_time") or 0)
        end = float(item.get("end_time") or start)
        attaches = item_type == "punctuation" and content in {
            ".",
            ",",
            "!",
            "?",
            ";",
            ":",
            "'",
            '"',
            "-",
            "—",
            "…",
        }

        if not current_speaker:
            current_speaker = speaker
            current_start = start
            current_end = end
            current_parts = [content]
            continue

        if speaker != current_speaker:
            flush()
            current_speaker = speaker
            current_start = start
            current_end = end
            current_parts = [content]
            continue

        current_end = max(current_end, end)
        if attaches and current_parts:
            current_parts[-1] = f"{current_parts[-1]}{content}"
        else:
            current_parts.append(content)

    flush()
    return tuple(segments)


class SpeechmaticsDiarizedTranscriber:
    def __init__(self, client: httpx.Client | None = None, cleanup_runner=None):
        self.cleanup_runner = cleanup_runner
        self._owns_client = client is None
        if client is not None:
            self.client = client
            return
        if not settings.SPEECHMATICS_API_KEY:
            raise PermanentProcessingError(
                "SPEECHMATICS_API_KEY is required for Sermon transcription."
            )
        self.client = httpx.Client(
            base_url=settings.SPEECHMATICS_API_BASE_URL.rstrip("/"),
            headers={"Authorization": f"Bearer {settings.SPEECHMATICS_API_KEY}"},
            timeout=httpx.Timeout(settings.SPEECHMATICS_REQUEST_TIMEOUT_SECONDS),
        )

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> SpeechmaticsDiarizedTranscriber:
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def transcribe(self, sermon: Sermon) -> CleanedTranscript:
        try:
            source_path = Path(sermon.audio.path)
        except (NotImplementedError, ValueError) as error:
            raise PermanentProcessingError(
                "The configured audio storage cannot provide a local worker path."
            ) from error
        if not source_path.is_file():
            raise PermanentProcessingError("The Sermon audio file is missing on disk.")

        job_id = self._submit_job(source_path)
        self._wait_for_job(job_id)
        payload = self._fetch_transcript(job_id)

        raw_segments = speechmatics_raw_segments(payload)
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
            raw_segments=tuple(raw_segments),
        )

    def _submit_job(self, source_path: Path) -> str:
        config = {
            "type": "transcription",
            "transcription_config": {
                "language": settings.SPEECHMATICS_LANGUAGE,
                "model": settings.SPEECHMATICS_MODEL,
                "diarization": "speaker",
                "speaker_diarization_config": {
                    "speaker_sensitivity": settings.SPEECHMATICS_SPEAKER_SENSITIVITY,
                    "prefer_current_speaker": True,
                },
            },
        }
        try:
            with source_path.open("rb") as audio:
                response = self.client.post(
                    "/v2/jobs",
                    data={"config": json.dumps(config)},
                    files={
                        "data_file": (
                            source_path.name,
                            audio,
                            "application/octet-stream",
                        )
                    },
                )
        except httpx.TimeoutException as error:
            raise RetryableProcessingError(
                "Speechmatics job submission timed out."
            ) from error
        except httpx.HTTPError as error:
            raise RetryableProcessingError(
                f"Speechmatics job submission failed: {error}"
            ) from error

        self._raise_for_status(response, action="submit job")
        try:
            job_id = response.json()["id"]
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise PermanentProcessingError(
                "Speechmatics did not return a job id."
            ) from error
        return str(job_id)

    def _wait_for_job(self, job_id: str) -> None:
        deadline = time.monotonic() + settings.SPEECHMATICS_JOB_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            try:
                response = self.client.get(f"/v2/jobs/{job_id}")
            except httpx.TimeoutException as error:
                raise RetryableProcessingError(
                    "Speechmatics job status polling timed out."
                ) from error
            except httpx.HTTPError as error:
                raise RetryableProcessingError(
                    f"Speechmatics job status polling failed: {error}"
                ) from error

            self._raise_for_status(response, action="poll job")
            try:
                status = response.json()["job"]["status"]
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                raise PermanentProcessingError(
                    "Speechmatics job status response was invalid."
                ) from error

            if status == "done":
                return
            if status == "rejected":
                detail = response.json().get("job", {}).get("errors") or status
                raise PermanentProcessingError(
                    f"Speechmatics rejected the transcription job: {detail}"
                )
            if status not in {"running", "queued"}:
                raise PermanentProcessingError(
                    f"Speechmatics job ended with unexpected status: {status}"
                )
            time.sleep(settings.SPEECHMATICS_POLL_INTERVAL_SECONDS)

        raise RetryableProcessingError(
            "Speechmatics transcription job timed out before completion."
        )

    def _fetch_transcript(self, job_id: str) -> dict[str, Any]:
        try:
            response = self.client.get(f"/v2/jobs/{job_id}/transcript")
        except httpx.TimeoutException as error:
            raise RetryableProcessingError(
                "Speechmatics transcript download timed out."
            ) from error
        except httpx.HTTPError as error:
            raise RetryableProcessingError(
                f"Speechmatics transcript download failed: {error}"
            ) from error

        self._raise_for_status(response, action="fetch transcript")
        try:
            payload = response.json()
        except json.JSONDecodeError as error:
            raise PermanentProcessingError(
                "Speechmatics transcript was not valid JSON."
            ) from error
        if not isinstance(payload, dict):
            raise PermanentProcessingError(
                "Speechmatics transcript payload was invalid."
            )
        return payload

    def _raise_for_status(self, response: httpx.Response, *, action: str) -> None:
        if response.status_code in {408, 429} or response.status_code >= 500:
            raise RetryableProcessingError(
                f"Speechmatics temporary error while trying to {action} "
                f"({response.status_code})."
            )
        if response.status_code == 401:
            raise PermanentProcessingError(
                "Speechmatics returned 401 Unauthorized. Check SPEECHMATICS_API_KEY "
                "and SPEECHMATICS_API_BASE_URL (use a regional host such as "
                "https://us1.asr.api.speechmatics.com or https://eu1.asr.api.speechmatics.com)."
            )
        if response.status_code >= 400:
            detail = response.text.strip()[:500]
            raise PermanentProcessingError(
                f"Speechmatics failed to {action} ({response.status_code}): {detail}"
            )
