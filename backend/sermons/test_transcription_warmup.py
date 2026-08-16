from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from accounts.models import User

from .models import Sermon
from .processing import RawTranscriptSegment
from .speechmatics_transcriber import SpeechmaticsDiarizedTranscriber
from .transcript_cleanup import TranscriptCleanupOutput
from .transcription_warmup import (
    effective_warmup_seconds,
    strip_warmup_from_raw_segments,
    strip_warmup_from_speechmatics_payload,
    write_warmup_prefixed_audio,
)

import httpx


class TranscriptionWarmupMappingTests(SimpleTestCase):
    @override_settings(TRANSCRIPTION_WARMUP_SECONDS=45)
    def test_warmup_is_capped_to_recording_length(self):
        self.assertEqual(effective_warmup_seconds(120), 45)
        self.assertEqual(effective_warmup_seconds(30), 30)
        self.assertEqual(effective_warmup_seconds(0), 0)

    @override_settings(TRANSCRIPTION_WARMUP_SECONDS=0)
    def test_disabled_warmup_is_zero(self):
        self.assertEqual(effective_warmup_seconds(120), 0)

    def test_strips_prefixed_tail_and_shifts_remaining_segments(self):
        segments = (
            RawTranscriptSegment("S1", 0.0, 2.0, "Amen from the ending."),
            RawTranscriptSegment("S1", 44.0, 50.0, "straddling the cut"),
            RawTranscriptSegment("S1", 45.0, 48.0, "Beloved friends"),
            RawTranscriptSegment("S1", 100.0, 110.0, "The real ending."),
        )

        clipped = strip_warmup_from_raw_segments(segments, 45.0)

        self.assertEqual(
            [
                (segment.start_seconds, segment.end_seconds, segment.text)
                for segment in clipped
            ],
            [
                (0.0, 5.0, "straddling the cut"),
                (0.0, 3.0, "Beloved friends"),
                (55.0, 65.0, "The real ending."),
            ],
        )

    def test_speechmatics_payload_drops_warmup_words(self):
        payload = {
            "results": [
                {
                    "type": "word",
                    "start_time": 10.0,
                    "end_time": 10.4,
                    "alternatives": [{"content": "Amen", "speaker": "S1"}],
                },
                {
                    "type": "word",
                    "start_time": 44.5,
                    "end_time": 45.5,
                    "alternatives": [{"content": "Grace", "speaker": "S1"}],
                },
                {
                    "type": "word",
                    "start_time": 46.0,
                    "end_time": 47.0,
                    "alternatives": [{"content": "welcomes", "speaker": "S1"}],
                },
            ]
        }

        shifted = strip_warmup_from_speechmatics_payload(payload, 45.0)

        self.assertEqual(
            [
                (
                    item["start_time"],
                    item["end_time"],
                    item["alternatives"][0]["content"],
                )
                for item in shifted["results"]
            ],
            [
                (0.0, 0.5, "Grace"),
                (1.0, 2.0, "welcomes"),
            ],
        )

    @override_settings(FFMPEG_BINARY="ffmpeg-test")
    def test_ffmpeg_prefixes_the_last_forty_five_seconds(self):
        captured: list[tuple[str, ...]] = []

        def fake_ffmpeg(command: tuple[str, ...]) -> None:
            captured.append(command)
            Path(command[-1]).write_bytes(b"warmed")

        with patch(
            "sermons.transcription_warmup._run_ffmpeg",
            side_effect=fake_ffmpeg,
        ):
            write_warmup_prefixed_audio(
                Path("/tmp/sermon.m4a"),
                Path("/tmp/warmed.m4a"),
                duration_seconds=120,
                warmup_seconds=45,
            )

        self.assertEqual(len(captured), 1)
        command = captured[0]
        self.assertEqual(command[0], "ffmpeg-test")
        filter_complex = command[command.index("-filter_complex") + 1]
        self.assertEqual(
            filter_complex,
            "[0:a]atrim=start=75.0,asetpts=PTS-STARTPTS[tail];"
            "[tail][0:a]concat=n=2:v=0:a=1[out]",
        )
        self.assertEqual(command[-1], "/tmp/warmed.m4a")


class TranscriptionWarmupTranscriberTests(TestCase):
    def setUp(self):
        self.media_directory = TemporaryDirectory()
        self.settings_override = override_settings(
            MEDIA_ROOT=self.media_directory.name,
            SPEECHMATICS_API_KEY="test-speechmatics-key",
            SPEECHMATICS_API_BASE_URL="https://asr.example.test",
            SPEECHMATICS_POLL_INTERVAL_SECONDS=0,
            SPEECHMATICS_JOB_TIMEOUT_SECONDS=5,
            TRANSCRIPTION_WARMUP_SECONDS=45,
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(self.media_directory.cleanup)
        self.user = User.objects.create_user(
            email="warmup@example.com",
            password="safe-test-password",
        )

    def test_speechmatics_uploads_prefixed_audio_and_clips_transcript(self):
        sermon = Sermon.objects.create(
            owner=self.user,
            source_draft_id="warmup-source",
            captured_at=timezone.now(),
            duration_seconds=120,
            audio=SimpleUploadedFile(
                "sermon.m4a", b"fake-audio", content_type="audio/mp4"
            ),
            audio_mime_type="audio/mp4",
            audio_size_bytes=10,
        )
        original_audio = Path(sermon.audio.path).read_bytes()
        uploaded_names: list[str] = []

        def fake_ffmpeg(command: tuple[str, ...]) -> None:
            Path(command[-1]).write_bytes(b"prefixed-audio")

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST" and request.url.path == "/v2/jobs":
                filename = request.headers.get("content-type", "")
                uploaded_names.append(filename)
                return httpx.Response(201, json={"id": "job-warmup"})
            if request.method == "GET" and request.url.path == "/v2/jobs/job-warmup":
                return httpx.Response(
                    200, json={"job": {"id": "job-warmup", "status": "done"}}
                )
            if (
                request.method == "GET"
                and request.url.path == "/v2/jobs/job-warmup/transcript"
            ):
                return httpx.Response(
                    200,
                    json={
                        "results": [
                            {
                                "type": "word",
                                "start_time": 2.0,
                                "end_time": 2.4,
                                "alternatives": [{"content": "Amen", "speaker": "S1"}],
                            },
                            {
                                "type": "word",
                                "start_time": 45.0,
                                "end_time": 45.5,
                                "alternatives": [
                                    {"content": "Beloved", "speaker": "S1"}
                                ],
                            },
                            {
                                "type": "word",
                                "start_time": 45.6,
                                "end_time": 46.0,
                                "alternatives": [
                                    {"content": "friends", "speaker": "S1"}
                                ],
                            },
                        ]
                    },
                )
            return httpx.Response(404, json={"error": "unexpected"})

        client = httpx.Client(
            transport=httpx.MockTransport(handler),
            base_url="https://asr.example.test",
            headers={"Authorization": "Bearer test"},
        )
        transcriber = SpeechmaticsDiarizedTranscriber(
            client=client,
            cleanup_runner=lambda *args, **kwargs: TranscriptCleanupOutput(
                incidental_segment_indexes=[]
            ),
        )

        with patch(
            "sermons.transcription_warmup._run_ffmpeg",
            side_effect=fake_ffmpeg,
        ):
            result = transcriber.transcribe(sermon)

        self.assertEqual(result.text, "Beloved friends")
        self.assertEqual(result.segments[0].start_seconds, 0.0)
        self.assertEqual(result.segments[0].end_seconds, 1.0)
        self.assertEqual(result.raw_segments[0].text, "Beloved friends")
        self.assertEqual(Path(sermon.audio.path).read_bytes(), original_audio)
        self.assertEqual(len(uploaded_names), 1)
