from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from accounts.models import User

from .models import Sermon
from .processing import PermanentProcessingError
from .speechmatics_transcriber import (
    SpeechmaticsDiarizedTranscriber,
    speechmatics_raw_segments,
)
from .transcript_cleanup import TranscriptCleanupOutput
from .voice_isolation import isolate_sermon_voice


class SpeechmaticsMappingTests(SimpleTestCase):
    def test_collapses_words_by_speaker_and_attaches_punctuation(self):
        payload = {
            "results": [
                {
                    "type": "word",
                    "start_time": 1.0,
                    "end_time": 1.2,
                    "alternatives": [
                        {"content": "Grace", "speaker": "S1", "confidence": 0.9}
                    ],
                },
                {
                    "type": "word",
                    "start_time": 1.3,
                    "end_time": 1.5,
                    "alternatives": [
                        {"content": "welcomes", "speaker": "S1", "confidence": 0.9}
                    ],
                },
                {
                    "type": "punctuation",
                    "start_time": 1.5,
                    "end_time": 1.5,
                    "alternatives": [
                        {"content": ".", "speaker": "S1", "confidence": 1.0}
                    ],
                },
                {
                    "type": "word",
                    "start_time": 2.0,
                    "end_time": 2.3,
                    "alternatives": [
                        {"content": "Amen", "speaker": "S2", "confidence": 0.8}
                    ],
                },
            ]
        }

        segments = speechmatics_raw_segments(payload)

        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0].speaker, "S1")
        self.assertEqual(segments[0].text, "Grace welcomes.")
        self.assertEqual(segments[0].start_seconds, 1.0)
        self.assertEqual(segments[0].end_seconds, 1.5)
        self.assertEqual(segments[1].speaker, "S2")
        self.assertEqual(segments[1].text, "Amen")


class SpeechmaticsTranscriberTests(TestCase):
    def setUp(self):
        self.media_directory = TemporaryDirectory()
        self.settings_override = override_settings(
            MEDIA_ROOT=self.media_directory.name,
            SPEECHMATICS_API_KEY="test-speechmatics-key",
            SPEECHMATICS_API_BASE_URL="https://asr.example.test",
            SPEECHMATICS_POLL_INTERVAL_SECONDS=0,
            SPEECHMATICS_JOB_TIMEOUT_SECONDS=5,
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(self.media_directory.cleanup)
        self.user = User.objects.create_user(
            email="speechmatics@example.com",
            password="safe-test-password",
        )

    def sermon(self) -> Sermon:
        return Sermon.objects.create(
            owner=self.user,
            source_draft_id="speechmatics-source",
            captured_at=timezone.now(),
            duration_seconds=120,
            audio=SimpleUploadedFile(
                "sermon.m4a", b"fake-audio", content_type="audio/mp4"
            ),
            audio_mime_type="audio/mp4",
            audio_size_bytes=10,
        )

    def test_transcribe_submits_polls_and_cleans(self):
        sermon = self.sermon()
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(f"{request.method} {request.url.path}")
            if request.method == "POST" and request.url.path == "/v2/jobs":
                return httpx.Response(201, json={"id": "job-123"})
            if request.method == "GET" and request.url.path == "/v2/jobs/job-123":
                return httpx.Response(
                    200, json={"job": {"id": "job-123", "status": "done"}}
                )
            if (
                request.method == "GET"
                and request.url.path == "/v2/jobs/job-123/transcript"
            ):
                return httpx.Response(
                    200,
                    json={
                        "results": [
                            {
                                "type": "word",
                                "start_time": 0.0,
                                "end_time": 0.4,
                                "alternatives": [
                                    {
                                        "content": "Beloved",
                                        "speaker": "S1",
                                        "confidence": 0.95,
                                    }
                                ],
                            },
                            {
                                "type": "word",
                                "start_time": 0.5,
                                "end_time": 0.9,
                                "alternatives": [
                                    {
                                        "content": "friends",
                                        "speaker": "S1",
                                        "confidence": 0.95,
                                    }
                                ],
                            },
                        ]
                    },
                )
            return httpx.Response(404, json={"error": "unexpected"})

        transport = httpx.MockTransport(handler)
        client = httpx.Client(
            transport=transport,
            base_url="https://asr.example.test",
            headers={"Authorization": "Bearer test"},
        )

        transcriber = SpeechmaticsDiarizedTranscriber(
            client=client,
            cleanup_runner=lambda *args, **kwargs: TranscriptCleanupOutput(
                incidental_segment_indexes=[]
            ),
        )
        result = transcriber.transcribe(sermon)

        self.assertEqual(result.text, "Beloved friends")
        self.assertEqual(len(result.segments), 1)
        self.assertEqual(result.raw_segments[0].speaker, "S1")
        self.assertEqual(
            calls,
            [
                "POST /v2/jobs",
                "GET /v2/jobs/job-123",
                "GET /v2/jobs/job-123/transcript",
            ],
        )

    def test_unauthorized_is_permanent(self):
        sermon = self.sermon()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, text="unauthorized")

        client = httpx.Client(
            transport=httpx.MockTransport(handler),
            base_url="https://asr.example.test",
        )
        transcriber = SpeechmaticsDiarizedTranscriber(
            client=client,
            cleanup_runner=lambda *args, **kwargs: TranscriptCleanupOutput(),
        )
        with self.assertRaises(PermanentProcessingError):
            transcriber.transcribe(sermon)


class VoiceIsolationTests(TestCase):
    def setUp(self):
        self.media_directory = TemporaryDirectory()
        self.settings_override = override_settings(
            MEDIA_ROOT=self.media_directory.name,
            ELEVENLABS_API_KEY="test-eleven-key",
            ELEVENLABS_API_BASE_URL="https://api.eleven.example.test",
            SERMON_VOICE_ISOLATION_ENABLED=True,
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(self.media_directory.cleanup)
        self.user = User.objects.create_user(
            email="isolate@example.com",
            password="safe-test-password",
        )

    def sermon(self) -> Sermon:
        return Sermon.objects.create(
            owner=self.user,
            source_draft_id="isolate-source",
            captured_at=timezone.now(),
            duration_seconds=120,
            audio=SimpleUploadedFile(
                "quiet.m4a", b"quiet-audio", content_type="audio/mp4"
            ),
            audio_mime_type="audio/mp4",
            audio_size_bytes=11,
            audio_normalized_at=timezone.now(),
        )

    def test_isolate_rewrites_file_and_clears_normalized_flag(self):
        sermon = self.sermon()

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/v1/audio-isolation")
            self.assertEqual(request.headers["xi-api-key"], "test-eleven-key")
            return httpx.Response(200, content=b"isolated-raw-audio")

        def fake_encode(source_path: Path, destination_path: Path) -> None:
            destination_path.write_bytes(b"isolated-encoded-m4a")

        with (
            patch("sermons.voice_isolation.httpx.Client") as client_cls,
            patch(
                "sermons.voice_isolation._encode_playback_m4a",
                side_effect=fake_encode,
            ),
            patch(
                "sermons.voice_isolation.probe_audio_duration_seconds",
                return_value=119,
            ),
        ):
            client_cls.return_value.__enter__.return_value.post.side_effect = (
                lambda *args, **kwargs: handler(
                    httpx.Request("POST", "https://api.eleven.example.test/v1/audio-isolation")
                )
            )
            # Simpler: patch _call_elevenlabs_isolation instead
            pass

        with (
            patch(
                "sermons.voice_isolation._call_elevenlabs_isolation",
                return_value=b"isolated-raw-audio",
            ),
            patch(
                "sermons.voice_isolation._encode_playback_m4a",
                side_effect=fake_encode,
            ),
            patch(
                "sermons.voice_isolation.probe_audio_duration_seconds",
                return_value=119,
            ),
        ):
            changed = isolate_sermon_voice(sermon)

        sermon.refresh_from_db()
        self.assertTrue(changed)
        self.assertIsNotNone(sermon.audio_isolated_at)
        self.assertIsNone(sermon.audio_normalized_at)
        self.assertEqual(sermon.audio_size_bytes, 20)
        self.assertEqual(Path(sermon.audio.path).read_bytes(), b"isolated-encoded-m4a")

    def test_isolate_skips_when_already_isolated(self):
        sermon = self.sermon()
        sermon.audio_isolated_at = timezone.now()
        sermon.save(update_fields=("audio_isolated_at", "updated_at"))

        with patch("sermons.voice_isolation._call_elevenlabs_isolation") as call:
            changed = isolate_sermon_voice(sermon)

        self.assertFalse(changed)
        call.assert_not_called()

    @override_settings(SERMON_VOICE_ISOLATION_ENABLED=False)
    def test_isolate_can_be_disabled(self):
        sermon = self.sermon()
        with patch("sermons.voice_isolation._call_elevenlabs_isolation") as call:
            changed = isolate_sermon_voice(sermon)
        self.assertFalse(changed)
        call.assert_not_called()

    def test_isolate_skips_when_over_one_hour(self):
        sermon = self.sermon()
        sermon.duration_seconds = 60 * 60 + 1
        sermon.save(update_fields=("duration_seconds", "updated_at"))

        with patch("sermons.voice_isolation._call_elevenlabs_isolation") as call:
            changed = isolate_sermon_voice(sermon)

        self.assertFalse(changed)
        call.assert_not_called()
        sermon.refresh_from_db()
        self.assertIsNone(sermon.audio_isolated_at)