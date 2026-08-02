from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch
import json

import httpx
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from openai import APIConnectionError
from openai.types.audio.transcription_diarized_segment import (
    TranscriptionDiarizedSegment,
)
from simpleai.exceptions import ProviderError, SettingsError
from simpleai.schema import openai_response_schema

from accounts.models import User

from .audio_chunks import MAX_TRANSCRIPTION_UPLOAD_BYTES, prepared_audio_chunks
from .models import Sermon, StudyArtifact, TagSuggestion
from .openai_transcriber import (
    CleanedTranscript,
    OpenAIDiarizedTranscriber,
    raw_diarized_segments,
    transcription_chunking_strategy,
)
from .processing import (
    PermanentProcessingError,
    RawTranscriptSegment,
    RetryableProcessingError,
    ScriptureReferenceResult,
    StudyArtifactResult,
    TranscriptSegment,
)
from .transcript_cleanup import (
    TranscriptCleanupOutput,
    intentional_service_segments,
)
from .provider_processor import ProviderSermonProcessor
from .magisterium_enrichment import MAGISTERIUM_ARTIFACT_KINDS
from .simpleai_artifacts import (
    GeneratedArtifacts,
    HymnVerseOutput,
    OutlinePointOutput,
    QuizQuestionOutput,
    SimpleAIArtifactGenerator,
    ScriptureReferenceOutput,
    StudyArtifactOutput,
)


def diarized_segment(
    speaker: str,
    start: float,
    end: float,
    text: str,
) -> TranscriptionDiarizedSegment:
    return TranscriptionDiarizedSegment(
        id=f"{speaker}-{start}",
        type="transcript.text.segment",
        speaker=speaker,
        start=start,
        end=end,
        text=text,
    )


def generated_artifacts() -> GeneratedArtifacts:
    return GeneratedArtifacts(
        title="Grace Welcomes Us Home",
        study_artifacts=tuple(
            StudyArtifactResult(kind=kind, content=f"Generated {kind}.")
            for kind in StudyArtifact.Kind.values
        ),
        scripture_references=(
            ScriptureReferenceResult(
                book="Luke",
                chapter_start=15,
                verse_start=11,
                verse_end=32,
            ),
        ),
        tag_suggestions=("Grace", "Welcome"),
    )


class ProviderPipelineTests(TestCase):
    def setUp(self):
        self.media_directory = TemporaryDirectory()
        self.settings_override = override_settings(MEDIA_ROOT=self.media_directory.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(self.media_directory.cleanup)
        self.user = User.objects.create_user(
            email="providers@example.com",
            password="safe-test-password",
        )

    def sermon(self, source_draft_id: str = "provider-source") -> Sermon:
        return Sermon.objects.create(
            owner=self.user,
            source_draft_id=source_draft_id,
            captured_at=timezone.now(),
            duration_seconds=120,
            audio=SimpleUploadedFile(
                f"{source_draft_id}.m4a",
                b"test audio",
                content_type="audio/mp4",
            ),
            audio_mime_type="audio/mp4",
            audio_size_bytes=10,
        )

    @staticmethod
    def fake_ffmpeg(command, **kwargs):
        output = str(command[-1])
        if "%03d" in output:
            for index in range(2):
                Path(output.replace("%03d", f"{index:03d}")).write_bytes(b"prepared")
        else:
            Path(output).write_bytes(b"prepared")
        return SimpleNamespace(returncode=0)

    def test_raw_diarized_segments_preserve_every_speaker(self):
        segments = [
            diarized_segment("A", 0, 20, "The kingdom is near."),
            diarized_segment("B", 20, 24, "Sit down kids."),
            diarized_segment("C", 24, 50, "Receive this good news."),
        ]

        raw = raw_diarized_segments(segments, offset_seconds=60)

        self.assertEqual(
            [(segment.speaker, segment.text) for segment in raw],
            [
                ("A", "The kingdom is near."),
                ("B", "Sit down kids."),
                ("C", "Receive this good news."),
            ],
        )
        self.assertEqual(raw[0].start_seconds, 60)
        self.assertEqual(raw[2].end_seconds, 110)

    def test_intentional_cleanup_drops_only_incidental_indexes(self):
        raw = (
            RawTranscriptSegment("A", 0, 20, "The kingdom is near."),
            RawTranscriptSegment("B", 20, 24, "Sit down kids."),
            RawTranscriptSegment("A", 24, 50, "Receive this good news."),
            RawTranscriptSegment("C", 50, 70, "Let us pray together."),
        )
        captured: dict[str, object] = {}

        def runner(*args, **kwargs):
            captured.update(kwargs)
            return TranscriptCleanupOutput(incidental_segment_indexes=[1])

        cleaned = intentional_service_segments(raw, runner=runner)

        self.assertEqual(captured.get("output_format"), TranscriptCleanupOutput)
        self.assertNotIn("response_model", captured)
        self.assertEqual(
            [segment.text for segment in cleaned],
            [
                "The kingdom is near.",
                "Receive this good news.",
                "Let us pray together.",
            ],
        )

    def test_intentional_cleanup_keeps_everything_when_ai_marks_all_incidental(self):
        raw = (
            RawTranscriptSegment("A", 0, 20, "The kingdom is near."),
            RawTranscriptSegment("B", 20, 40, "Mercy remakes us."),
        )

        cleaned = intentional_service_segments(
            raw,
            runner=lambda *args, **kwargs: TranscriptCleanupOutput(
                incidental_segment_indexes=[0, 1]
            ),
        )

        self.assertEqual(len(cleaned), 2)

    def test_intentional_cleanup_keeps_long_segments_even_if_marked_incidental(self):
        raw = (
            RawTranscriptSegment(
                "A",
                0,
                25,
                "In the name of the Father and of the Son and of the Holy Spirit.",
            ),
            RawTranscriptSegment("B", 25, 28, "Pass the hymnal."),
        )

        cleaned = intentional_service_segments(
            raw,
            runner=lambda *args, **kwargs: TranscriptCleanupOutput(
                incidental_segment_indexes=[0, 1]
            ),
        )

        self.assertEqual(
            [segment.text for segment in cleaned],
            [
                "In the name of the Father and of the Son and of the Holy Spirit.",
            ],
        )

    def test_intentional_cleanup_keeps_everything_when_drop_ratio_is_high(self):
        raw = (
            RawTranscriptSegment("A", 0, 10, "Grace meets us here."),
            RawTranscriptSegment("B", 10, 14, "Can you scoot over?"),
            RawTranscriptSegment("C", 14, 18, "Where is the bulletin?"),
        )

        cleaned = intentional_service_segments(
            raw,
            runner=lambda *args, **kwargs: TranscriptCleanupOutput(
                incidental_segment_indexes=[1, 2]
            ),
        )

        self.assertEqual(len(cleaned), 3)

    def test_transcriber_applies_consider_window_before_cleanup(self):
        sermon = self.sermon("windowed-source")
        sermon.consider_start_seconds = 30
        sermon.consider_end_seconds = 90
        sermon.save(
            update_fields=(
                "consider_start_seconds",
                "consider_end_seconds",
                "updated_at",
            )
        )
        client = Mock()
        client.audio.transcriptions.create.return_value = SimpleNamespace(
            segments=[
                diarized_segment("A", 0, 25, "Prelude chatter."),
                diarized_segment("A", 30, 60, "Blessed are the merciful."),
                diarized_segment("B", 60, 63, "Can you move over?"),
                diarized_segment("A", 63, 90, "Mercy remakes us."),
                diarized_segment("A", 95, 120, "Coffee after the service."),
            ]
        )
        transcriber = OpenAIDiarizedTranscriber(
            client=client,
            cleanup_runner=lambda *args, **kwargs: TranscriptCleanupOutput(
                incidental_segment_indexes=[1]
            ),
        )

        with patch(
            "sermons.audio_chunks.subprocess.run",
            side_effect=self.fake_ffmpeg,
        ):
            result = transcriber.transcribe(sermon)

        self.assertEqual(
            result.text,
            "Blessed are the merciful. Mercy remakes us.",
        )
        self.assertEqual(len(result.raw_segments), 5)
        self.assertEqual(result.raw_segments[0].text, "Prelude chatter.")

    @override_settings(
        FFMPEG_BINARY="ffmpeg-test",
        SERMON_TRANSCRIPTION_CHUNK_SECONDS=3300,
    )
    def test_large_recordings_are_compressed_into_upload_safe_chunks(self):
        sermon = self.sermon()
        sermon.audio_size_bytes = MAX_TRANSCRIPTION_UPLOAD_BYTES + 1
        sermon.save(update_fields=("audio_size_bytes", "updated_at"))

        def create_chunks(command, **kwargs):
            output_pattern = str(command[-1])
            for index in range(2):
                path = output_pattern.replace("%03d", f"{index:03d}")
                with open(path, "wb") as chunk:
                    chunk.write(b"compressed audio")
            return SimpleNamespace(returncode=0)

        with patch(
            "sermons.audio_chunks.subprocess.run",
            side_effect=create_chunks,
        ) as run:
            with prepared_audio_chunks(sermon) as chunks:
                self.assertEqual(
                    [chunk.start_seconds for chunk in chunks],
                    [0, 3300],
                )
                self.assertTrue(all(chunk.path.exists() for chunk in chunks))

        command = run.call_args.args[0]
        self.assertIn("64k", command)
        self.assertIn("loudnorm=I=-16:TP=-1.5:LRA=11", command)
        self.assertIn("3300", command)

    @override_settings(FFMPEG_BINARY="ffmpeg-test")
    def test_short_recordings_are_loudness_normalized_before_transcription(self):
        sermon = self.sermon()

        def create_normalized(command, **kwargs):
            Path(command[-1]).write_bytes(b"normalized audio")
            return SimpleNamespace(returncode=0)

        with patch(
            "sermons.audio_chunks.subprocess.run",
            side_effect=create_normalized,
        ) as run:
            with prepared_audio_chunks(sermon) as chunks:
                self.assertEqual(len(chunks), 1)
                self.assertEqual(chunks[0].start_seconds, 0)
                self.assertTrue(chunks[0].path.exists())
                self.assertNotEqual(chunks[0].path, Path(sermon.audio.path))

        command = run.call_args.args[0]
        self.assertIn("loudnorm=I=-16:TP=-1.5:LRA=11", command)
        self.assertIn("64k", command)

    @override_settings(
        OPENAI_TRANSCRIPTION_MODEL="gpt-4o-transcribe-diarize",
        OPENAI_TRANSCRIPTION_VAD_THRESHOLD=0.3,
        OPENAI_TRANSCRIPTION_VAD_PREFIX_PADDING_MS=400,
        OPENAI_TRANSCRIPTION_VAD_SILENCE_DURATION_MS=1000,
    )
    def test_openai_transcriber_requests_diarization_and_returns_cleaned_text(self):
        client = Mock()
        client.audio.transcriptions.create.return_value = SimpleNamespace(
            segments=[
                diarized_segment("A", 0, 30, "Blessed are the merciful."),
                diarized_segment("B", 30, 33, "Can you move over?"),
                diarized_segment("C", 33, 60, "Mercy remakes us."),
            ]
        )
        transcriber = OpenAIDiarizedTranscriber(
            client=client,
            cleanup_runner=lambda *args, **kwargs: TranscriptCleanupOutput(
                incidental_segment_indexes=[1]
            ),
        )

        with patch(
            "sermons.audio_chunks.subprocess.run",
            side_effect=self.fake_ffmpeg,
        ):
            result = transcriber.transcribe(self.sermon())

        self.assertEqual(
            result.text,
            "Blessed are the merciful. Mercy remakes us.",
        )
        self.assertEqual(len(result.raw_segments), 3)
        self.assertEqual(result.raw_segments[1].text, "Can you move over?")
        request = client.audio.transcriptions.create.call_args.kwargs
        self.assertEqual(request["model"], "gpt-4o-transcribe-diarize")
        self.assertEqual(request["response_format"], "diarized_json")
        self.assertEqual(
            json.loads(request["chunking_strategy"]),
            {
                "type": "server_vad",
                "threshold": 0.3,
                "prefix_padding_ms": 400,
                "silence_duration_ms": 1000,
            },
        )

    def test_transcription_chunking_strategy_uses_configured_vad(self):
        with override_settings(
            OPENAI_TRANSCRIPTION_VAD_THRESHOLD=0.25,
            OPENAI_TRANSCRIPTION_VAD_PREFIX_PADDING_MS=500,
            OPENAI_TRANSCRIPTION_VAD_SILENCE_DURATION_MS=1200,
        ):
            self.assertEqual(
                json.loads(transcription_chunking_strategy()),
                {
                    "type": "server_vad",
                    "threshold": 0.25,
                    "prefix_padding_ms": 500,
                    "silence_duration_ms": 1200,
                },
            )
            self.assertIsInstance(transcription_chunking_strategy(), str)

    def test_openai_connection_failures_are_retryable(self):
        client = Mock()
        client.audio.transcriptions.create.side_effect = APIConnectionError(
            request=httpx.Request(
                "POST", "https://api.openai.com/v1/audio/transcriptions"
            )
        )
        transcriber = OpenAIDiarizedTranscriber(client=client)

        with patch(
            "sermons.audio_chunks.subprocess.run",
            side_effect=self.fake_ffmpeg,
        ):
            with self.assertRaises(RetryableProcessingError):
                transcriber.transcribe(self.sermon())

    @override_settings(OPENAI_API_KEY="")
    def test_missing_transcription_key_fails_before_provider_work(self):
        with self.assertRaisesMessage(
            PermanentProcessingError,
            "OPENAI_API_KEY",
        ):
            OpenAIDiarizedTranscriber()

    def test_simpleai_generator_maps_structured_output_to_domain_artifacts(self):
        runner = Mock(
            return_value=StudyArtifactOutput(
                sermon_title="The Father Runs to Welcome",
                short_summary="God welcomes the lost.",
                long_summary="A longer account of welcome and repentance.",
                outline=[
                    OutlinePointOutput(text="The younger son leaves", start_seconds=0),
                    OutlinePointOutput(
                        text="The father runs to welcome him",
                        start_seconds=12,
                    ),
                ],
                practical_next_steps=[
                    "Welcome someone who expects distance.",
                    "Practice receiving grace without earning it.",
                ],
                call_to_action="Make the first move toward welcome this week.",
                quotations=[
                    "there was a father who welcomed his son home",
                ],
                adult_discussion_questions=["Where is grace difficult to receive?"],
                kids_discussion_questions=["How did the father show love?"],
                sermon_feedback=[
                    "State the invitation to receive grace earlier in the Sermon.",
                ],
                hymn_title="The Father Runs to Welcome",
                hymn_meter="CM (8.6.8.6)",
                hymn_verses=[
                    HymnVerseOutput(
                        lines=[
                            "The child had wandered far",
                            "Yet home remained in view",
                            "The father ran with open arms",
                            "And made the lost one new",
                        ]
                    ),
                    HymnVerseOutput(
                        lines=[
                            "O grace that welcomes home",
                            "Teach us to welcome too",
                            "To cross the road with open arms",
                            "As Christ has taught us to",
                        ]
                    ),
                ],
                hymn_tunes=["ST ANNE", "FOREST GREEN"],
                quiz_questions=[
                    QuizQuestionOutput(
                        question_text="What did the father do when his son returned?",
                        answer_text="He welcomed his son home.",
                    ),
                    QuizQuestionOutput(
                        question_text="What is the Sermon's central invitation?",
                        answer_text="Receive grace and extend welcome to others.",
                    ),
                ],
                scripture_references=[
                    ScriptureReferenceOutput(
                        book="Luke",
                        chapter_start=15,
                        verse_start=11,
                        verse_end=32,
                    )
                ],
                tag_suggestions=["Grace", "Homecoming"],
            )
        )
        generator = SimpleAIArtifactGenerator(runner=runner)
        transcript = CleanedTranscript(
            text="There was a father who welcomed his son home.",
            segments=(
                TranscriptSegment(
                    start_seconds=0,
                    end_seconds=5,
                    text="The younger son leaves home.",
                ),
                TranscriptSegment(
                    start_seconds=12,
                    end_seconds=18,
                    text="There was a father who welcomed his son home.",
                ),
            ),
        )

        result = generator.generate(transcript)

        self.assertEqual(result.title, "The Father Runs to Welcome")
        self.assertEqual(
            {artifact.kind for artifact in result.study_artifacts},
            set(StudyArtifact.Kind.values) - MAGISTERIUM_ARTIFACT_KINDS,
        )
        outline = next(
            artifact
            for artifact in result.study_artifacts
            if artifact.kind == StudyArtifact.Kind.OUTLINE
        )
        self.assertEqual(
            outline.content,
            "1. [00:00] The younger son leaves\n"
            "2. [00:12] The father runs to welcome him",
        )
        self.assertIn("[00:00] The younger son leaves home.", runner.call_args.args[0])
        self.assertIn(
            "[00:12] There was a father who welcomed his son home.",
            runner.call_args.args[0],
        )
        call_to_action = next(
            artifact
            for artifact in result.study_artifacts
            if artifact.kind == StudyArtifact.Kind.CALL_TO_ACTION
        )
        self.assertEqual(
            call_to_action.content,
            "Make the first move toward welcome this week.",
        )
        quotations = next(
            artifact
            for artifact in result.study_artifacts
            if artifact.kind == StudyArtifact.Kind.QUOTATIONS
        )
        self.assertEqual(
            quotations.content,
            "There was a father who welcomed his son home.",
        )  # casing + terminal period normalized
        hymn = next(
            artifact
            for artifact in result.study_artifacts
            if artifact.kind == StudyArtifact.Kind.HYMN
        )
        self.assertIn("Meter: CM (8.6.8.6)", hymn.content)
        self.assertIn("1.\nThe child had wandered far", hymn.content)
        tunes = next(
            artifact
            for artifact in result.study_artifacts
            if artifact.kind == StudyArtifact.Kind.HYMN_TUNE_SUGGESTIONS
        )
        self.assertIn("ST ANNE", tunes.content)
        quiz = next(
            artifact
            for artifact in result.study_artifacts
            if artifact.kind == StudyArtifact.Kind.QUIZ
        )
        self.assertIn(
            "Q1. What did the father do when his son returned?",
            quiz.content,
        )
        self.assertIn("A1. He welcomed his son home.", quiz.content)
        self.assertEqual(result.scripture_references[0].book, "Luke")
        self.assertEqual(result.tag_suggestions, ("Grace", "Homecoming"))

    def test_artifact_output_schema_is_openai_strict_compatible(self):
        schema = openai_response_schema(StudyArtifactOutput)

        self.assertEqual(
            set(schema["required"]),
            set(schema["properties"]),
        )

    def test_simpleai_generator_rejects_non_verbatim_quotations(self):
        runner = Mock(
            return_value=StudyArtifactOutput(
                sermon_title="Welcome Home",
                short_summary="God welcomes the lost.",
                long_summary="A longer account of welcome.",
                outline=[
                    OutlinePointOutput(
                        text="The father welcomes his son",
                        start_seconds=0,
                    )
                ],
                practical_next_steps=["Welcome someone this week."],
                call_to_action="Make the first move toward welcome.",
                quotations=["The father ran down the road."],
                adult_discussion_questions=["Where is grace difficult to receive?"],
                kids_discussion_questions=["How did the father show love?"],
                sermon_feedback=["Clarify the Sermon's account of grace."],
                hymn_title="Welcome Home",
                hymn_meter="LM (8.8.8.8)",
                hymn_verses=[
                    HymnVerseOutput(
                        lines=[
                            "A line of eight",
                            "A line of eight",
                            "A line of eight",
                            "A line of eight",
                        ]
                    ),
                    HymnVerseOutput(
                        lines=[
                            "A line of eight",
                            "A line of eight",
                            "A line of eight",
                            "A line of eight",
                        ]
                    ),
                ],
                hymn_tunes=["OLD HUNDREDTH"],
                quiz_questions=[
                    QuizQuestionOutput(
                        question_text="What did the father do?",
                        answer_text="He welcomed his son.",
                    ),
                    QuizQuestionOutput(
                        question_text="What does grace do?",
                        answer_text="Grace welcomes the lost.",
                    ),
                ],
            )
        )
        generator = SimpleAIArtifactGenerator(runner=runner)
        transcript = CleanedTranscript(
            text="There was a father who welcomed his son home.",
            segments=(
                TranscriptSegment(
                    start_seconds=0,
                    end_seconds=5,
                    text="There was a father who welcomed his son home.",
                ),
            ),
        )

        with self.assertRaisesMessage(
            RetryableProcessingError,
            "faithful Sermon quotation",
        ):
            generator.generate(transcript)

    def test_simpleai_configuration_errors_are_permanent(self):
        generator = SimpleAIArtifactGenerator(
            runner=Mock(side_effect=SettingsError("missing provider key"))
        )
        transcript = CleanedTranscript(
            text="A Transcript.",
            segments=(TranscriptSegment(0, 1, "A Transcript."),),
        )

        with self.assertRaisesMessage(PermanentProcessingError, "missing provider key"):
            generator.generate(transcript)

    def test_simpleai_provider_failures_are_retryable(self):
        generator = SimpleAIArtifactGenerator(
            runner=Mock(side_effect=ProviderError("provider unavailable"))
        )
        transcript = CleanedTranscript(
            text="A Transcript.",
            segments=(TranscriptSegment(0, 1, "A Transcript."),),
        )

        with self.assertRaisesMessage(
            RetryableProcessingError,
            "provider unavailable",
        ):
            generator.generate(transcript)

    def test_invalid_artifact_schema_is_a_permanent_failure(self):
        generator = SimpleAIArtifactGenerator(
            runner=Mock(
                side_effect=ProviderError(
                    "Invalid schema for response_format 'simpleai_output'"
                )
            )
        )
        transcript = CleanedTranscript(
            text="A Transcript.",
            segments=(TranscriptSegment(0, 1, "A Transcript."),),
        )

        with self.assertRaisesMessage(
            PermanentProcessingError,
            "Invalid schema for response_format",
        ):
            generator.generate(transcript)

    def test_provider_pipeline_suggests_only_same_owner_related_sermons(self):
        sermon = self.sermon()
        related = self.sermon("related")
        related.processing_status = Sermon.ProcessingStatus.READY
        related.save(update_fields=("processing_status", "updated_at"))
        TagSuggestion.objects.create(
            sermon=related,
            name="Grace",
            normalized_name="grace",
        )
        other_user = User.objects.create_user(
            email="other-provider@example.com",
            password="safe-test-password",
        )
        private = Sermon.objects.create(
            owner=other_user,
            source_draft_id="private",
            captured_at=timezone.now(),
            duration_seconds=120,
            audio=SimpleUploadedFile("private.m4a", b"audio", content_type="audio/mp4"),
            audio_mime_type="audio/mp4",
            audio_size_bytes=5,
            processing_status=Sermon.ProcessingStatus.READY,
        )
        TagSuggestion.objects.create(
            sermon=private,
            name="Grace",
            normalized_name="grace",
        )
        transcript = CleanedTranscript(
            text="Grace welcomes us.",
            segments=(TranscriptSegment(0, 2, "Grace welcomes us."),),
        )
        transcriber = Mock()
        transcriber.transcribe.return_value = transcript
        artifact_generator = Mock()
        artifact_generator.generate.return_value = generated_artifacts()
        processor = ProviderSermonProcessor(transcriber, artifact_generator)

        with (
            override_settings(MAGISTERIUM_API_KEY="", MAGISTERIUM_TIER=""),
            patch(
                "sermons.provider_processor.isolate_sermon_voice",
                return_value=False,
            ),
            patch(
                "sermons.provider_processor.normalize_sermon_playback_audio",
                return_value=False,
            ),
        ):
            result = processor.process(sermon)

        self.assertEqual(result.title, "Grace Welcomes Us Home")
        self.assertEqual(
            {artifact.kind for artifact in result.study_artifacts},
            set(StudyArtifact.Kind.values),
        )
        self.assertEqual(
            [suggestion.sermon_id for suggestion in result.related_sermons],
            [related.id],
        )
        self.assertNotIn(
            private.id,
            [suggestion.sermon_id for suggestion in result.related_sermons],
        )
